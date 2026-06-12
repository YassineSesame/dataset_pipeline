import hashlib
import re
from typing import List

import requests
from bs4 import BeautifulSoup

from .base import BaseSourceConnector, RawDocument
from utils.cache import load_cache, save_cache
from utils.relevance import is_boilerplate


class WebScraperConnector(BaseSourceConnector):
    """Scraper web pour Wikipedia et sites standards (fallback)."""

    def __init__(
        self,
        config,
        max_docs: int = 50,
        force_refresh: bool = False,
        cache_ttl_hours: float = 168,
    ):
        super().__init__(config)
        self.max_docs = max_docs
        self.force_refresh = force_refresh
        self.cache_ttl_hours = cache_ttl_hours

    def connect(self) -> bool:
        try:
            response = requests.head(
                self.config.url,
                timeout=10,
                headers={"User-Agent": "Mozilla/5.0 (compatible; DatasetPipeline/2.0)"},
            )
            return response.status_code == 200
        except Exception as e:
            print(f"   Erreur connexion: {e}")
            return False

    def fetch(self, keywords: List[str]) -> List[RawDocument]:
        import os

        os.makedirs("data/cache", exist_ok=True)
        cache_key = hashlib.md5((self.config.url + "_" + ",".join(keywords)).encode()).hexdigest()
        cache_file = f"data/cache/scraper_{cache_key}.json"

        cached = load_cache(cache_file, self.cache_ttl_hours, self.force_refresh)
        if cached is not None:
            return self._deserialize(cached)

        documents = []
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; DatasetPipeline/2.0)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9",
        }

        try:
            response = requests.get(
                self.config.url, headers=headers, timeout=30, allow_redirects=True
            )
            response.raise_for_status()
        except Exception as e:
            print(f"   Erreur requete: {e}")
            return documents

        soup = BeautifulSoup(response.content, "html.parser")
        content_div = soup.find("div", {"id": "mw-content-text"})
        paragraphs = content_div.find_all("p", recursive=True) if content_div else soup.find_all("p")

        print(f"   Paragraphes trouves: {len(paragraphs)}")

        for i, element in enumerate(paragraphs):
            text = element.get_text(strip=True)
            if len(text) < 50 or is_boilerplate(text):
                continue
            if not self._is_relevant(text, keywords):
                continue

            doc_id = hashlib.md5(text.encode()).hexdigest()[:12]
            documents.append(
                RawDocument(
                    id=f"{self.config.identifier}_{doc_id}",
                    source=self.config.identifier,
                    content=text,
                    metadata={
                        "url": self.config.url,
                        "word_count": len(text.split()),
                        "paragraph_index": i,
                        "type": "web",
                    },
                )
            )
            if len(documents) >= self.max_docs:
                break

        if documents:
            save_cache(cache_file, self._serialize(documents))
            print(f"   [Cache] {len(documents)} documents scrapes mis en cache.")

        return documents

    def _is_relevant(self, text: str, keywords: List[str]) -> bool:
        text_lower = text.lower()
        return any(kw.lower() in text_lower for kw in keywords)

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
