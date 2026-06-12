import hashlib
import re
from typing import List

import requests

from .base import BaseSourceConnector, RawDocument
from utils.cache import load_cache, save_cache
from utils.relevance import is_boilerplate


WIKI_USER_AGENT = "DatasetPipeline/2.0 (https://github.com/local/dataset-pipeline; contact@example.com)"

FALLBACK_TITLES = {
    "fr": {
        "covid": ["Vaccin contre le COVID-19", "Pandémie de COVID-19", "COVID-19"],
        "vaccin": ["Vaccin", "Vaccination", "Vaccin contre la grippe"],
        "coronavirus": ["Coronavirus", "SARS-CoV-2"],
    },
    "en": {
        "covid": ["COVID-19 vaccine", "COVID-19 pandemic", "COVID-19"],
        "vaccin": ["Vaccine", "Vaccination"],
        "coronavirus": ["Coronavirus", "SARS-CoV-2"],
    },
}


class WikipediaAPIConnector(BaseSourceConnector):
    """Recupere plusieurs articles Wikipedia via l'API MediaWiki."""

    WIKI_DOMAINS = {"fr": "fr.wikipedia.org", "en": "en.wikipedia.org"}

    def __init__(self, config, language: str = "fr", max_pages: int = 5, max_docs: int = 50,
                 force_refresh: bool = False, cache_ttl_hours: float = 168):
        super().__init__(config)
        self.language = language
        self.max_pages = max_pages
        self.max_docs = max_docs
        self.force_refresh = force_refresh
        self.cache_ttl_hours = cache_ttl_hours
        self.api_url = f"https://{self.WIKI_DOMAINS.get(language, 'fr.wikipedia.org')}/w/api.php"

    def connect(self) -> bool:
        try:
            response = requests.get(
                self.api_url,
                params={"action": "query", "meta": "siteinfo", "format": "json"},
                headers={"User-Agent": WIKI_USER_AGENT},
                timeout=10,
            )
            return response.status_code == 200
        except Exception as e:
            print(f"   Erreur connexion Wikipedia API: {e}")
            return False

    def fetch(self, keywords: List[str]) -> List[RawDocument]:
        import os

        os.makedirs("data/cache", exist_ok=True)
        cache_key = hashlib.md5(
            (self.api_url + "_" + ",".join(keywords) + f"_{self.max_pages}").encode()
        ).hexdigest()
        cache_file = f"data/cache/wiki_api_{cache_key}.json"

        cached = load_cache(cache_file, self.cache_ttl_hours, self.force_refresh)
        if cached is not None:
            return self._deserialize(cached)

        search_terms = " ".join(keywords[:6])
        page_titles = self._resolve_page_titles(keywords, search_terms)

        documents = []
        for title in page_titles:
            paragraphs = self._get_page_paragraphs(title)
            for i, text in enumerate(paragraphs):
                if len(text.split()) < 40 or is_boilerplate(text):
                    continue
                if not any(kw.lower() in text.lower() for kw in keywords):
                    continue

                doc_id = hashlib.md5(text.encode()).hexdigest()[:12]
                page_url = f"https://{self.WIKI_DOMAINS.get(self.language)}/wiki/{title.replace(' ', '_')}"
                documents.append(
                    RawDocument(
                        id=f"{self.config.identifier}_{doc_id}",
                        source=self.config.identifier,
                        content=text,
                        metadata={
                            "url": page_url,
                            "title": title,
                            "source_name": "Wikipedia",
                            "word_count": len(text.split()),
                            "paragraph_index": i,
                            "type": "wikipedia_api",
                        },
                    )
                )
                if len(documents) >= self.max_docs:
                    break
            if len(documents) >= self.max_docs:
                break

        if documents:
            save_cache(cache_file, self._serialize(documents))
            print(f"   [Cache] {len(documents)} paragraphes Wikipedia API mis en cache.")

        return documents

    def _resolve_page_titles(self, keywords: List[str], search_terms: str) -> List[str]:
        titles = self._search_pages(search_terms)
        if not titles and keywords:
            titles = self._search_pages(keywords[0])

        fallbacks = self._fallback_titles(keywords)
        merged = []
        seen = set()
        for title in titles + fallbacks:
            if title and title not in seen:
                seen.add(title)
                merged.append(title)
        return merged[: max(self.max_pages + len(fallbacks), self.max_pages)]

    def _fallback_titles(self, keywords: List[str]) -> List[str]:
        lang_map = FALLBACK_TITLES.get(self.language, FALLBACK_TITLES["fr"])
        titles = []
        keywords_lower = [kw.lower() for kw in keywords]
        for key, pages in lang_map.items():
            if any(key in kw for kw in keywords_lower):
                titles.extend(pages)
        return titles

    def _search_pages(self, query: str) -> List[str]:
        try:
            response = requests.get(
                self.api_url,
                params={
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": self.max_pages,
                    "utf8": 1,
                },
                headers={"User-Agent": WIKI_USER_AGENT},
                timeout=20,
            )
            response.raise_for_status()
            results = response.json().get("query", {}).get("search", [])
            return [r["title"] for r in results]
        except Exception as e:
            print(f"   ! Erreur recherche Wikipedia: {e}")
            return []

    def _get_page_paragraphs(self, title: str) -> List[str]:
        try:
            response = requests.get(
                self.api_url,
                params={
                    "action": "query",
                    "titles": title,
                    "prop": "extracts",
                    "explaintext": 1,
                    "format": "json",
                },
                headers={"User-Agent": WIKI_USER_AGENT},
                timeout=20,
            )
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
            for page in pages.values():
                extract = page.get("extract", "")
                paragraphs = [p.strip() for p in re.split(r"\n{2,}", extract) if p.strip()]
                return paragraphs
        except Exception as e:
            print(f"   ! Erreur extraction Wikipedia ({title}): {e}")
        return []

    def _serialize(self, documents: List[RawDocument]) -> list:
        return [
            {
                "id": d.id,
                "source": d.source,
                "content": d.content,
                "metadata": d.metadata,
                "collected_at": d.collected_at.isoformat(),
            }
            for d in documents
        ]

    def _deserialize(self, cached: list) -> List[RawDocument]:
        from datetime import datetime

        docs = []
        for doc in cached:
            docs.append(
                RawDocument(
                    id=doc["id"],
                    source=doc["source"],
                    content=doc["content"],
                    metadata=doc.get("metadata", {}),
                    collected_at=datetime.fromisoformat(doc["collected_at"])
                    if doc.get("collected_at")
                    else datetime.now(),
                )
            )
        return docs
