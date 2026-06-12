import hashlib
import re
from typing import List

import requests

from .base import BaseSourceConnector, RawDocument
from utils.cache import load_cache, save_cache
from utils.relevance import is_boilerplate


class NewsAPIConnector(BaseSourceConnector):
    """Connecteur NewsAPI avec extraction d'articles complets."""

    BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(
        self,
        config,
        extract_full_articles: bool = True,
        max_articles: int = 20,
        force_refresh: bool = False,
        cache_ttl_hours: float = 24,
        language: str = "fr",
    ):
        super().__init__(config)
        self.api_key = config.api_key
        self.extract_full_articles = extract_full_articles
        self.max_articles = max_articles
        self.force_refresh = force_refresh
        self.cache_ttl_hours = cache_ttl_hours
        self.language = language

    def connect(self) -> bool:
        if not self.api_key:
            print("   ! Cle API manquante")
            return False

        try:
            params = {"q": "test", "pageSize": 1, "apiKey": self.api_key}
            response = requests.get(self.BASE_URL, params=params, timeout=10)
            data = response.json()
            if data.get("status") == "ok":
                return True
            print(f"   ! Erreur API: {data.get('message', 'Inconnue')}")
            return False
        except Exception as e:
            print(f"   ! Erreur connexion: {e}")
            return False

    def fetch(self, keywords: List[str]) -> List[RawDocument]:
        import os

        os.makedirs("data/cache", exist_ok=True)
        cache_key = hashlib.md5(
            ("news_" + ",".join(keywords) + f"_{self.extract_full_articles}").encode()
        ).hexdigest()
        cache_file = f"data/cache/newsapi_{cache_key}.json"

        cached = load_cache(cache_file, self.cache_ttl_hours, self.force_refresh)
        if cached is not None:
            return self._deserialize(cached)

        documents = []
        query = " OR ".join(keywords)
        params = {
            "q": query,
            "language": self.language,
            "pageSize": min(self.max_articles, 50),
            "sortBy": "relevancy",
            "apiKey": self.api_key,
        }

        try:
            print(f"   Recherche NewsAPI: '{query}'")
            response = requests.get(self.BASE_URL, params=params, timeout=30)
            data = response.json()

            if data.get("status") != "ok":
                print(f"   ! Erreur: {data.get('message', 'Inconnue')}")
                return documents

            articles = data.get("articles", [])
            print(f"   Articles trouves: {len(articles)}")

            for article in articles[: self.max_articles]:
                url = article.get("url", "")
                title = article.get("title", "")
                description = article.get("description", "")

                text = self._build_article_text(article, url, title, description)
                text = re.sub(r"\[\+\d+ chars\]", "", text).strip()

                if len(text.split()) < 40:
                    continue

                doc_id = hashlib.md5(url.encode() if url else text.encode()).hexdigest()[:12]
                documents.append(
                    RawDocument(
                        id=f"news_{doc_id}",
                        source="newsapi",
                        content=text,
                        metadata={
                            "url": url,
                            "title": title,
                            "author": article.get("author"),
                            "published_at": article.get("publishedAt"),
                            "source_name": article.get("source", {}).get("name"),
                            "word_count": len(text.split()),
                            "full_text_extracted": self.extract_full_articles and len(text.split()) > 80,
                            "type": "api_news",
                        },
                    )
                )

        except Exception as e:
            print(f"   ! Erreur requete: {e}")

        if documents:
            save_cache(cache_file, self._serialize(documents))
            print(f"   [Cache] {len(documents)} articles NewsAPI mis en cache.")

        return documents

    def _build_article_text(self, article: dict, url: str, title: str, description: str) -> str:
        if self.extract_full_articles and url:
            from utils.article_extractor import extract_article_text

            full_text = extract_article_text(url)
            if full_text and len(full_text.split()) > 60:
                return f"{title}. {full_text}" if title else full_text

        content_parts = [title, description, article.get("content", "")]
        return " ".join(p for p in content_parts if p)

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
