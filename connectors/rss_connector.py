import hashlib
from typing import List

import feedparser

from .base import BaseSourceConnector, RawDocument
from utils.cache import load_cache, save_cache
from utils.relevance import is_boilerplate


class RSSConnector(BaseSourceConnector):
    """Recupere des articles depuis un flux RSS/Atom."""

    def __init__(
        self,
        config,
        max_entries: int = 30,
        force_refresh: bool = False,
        cache_ttl_hours: float = 24,
    ):
        super().__init__(config)
        self.max_entries = max_entries
        self.force_refresh = force_refresh
        self.cache_ttl_hours = cache_ttl_hours

    def connect(self) -> bool:
        return bool(self.config.url)

    def fetch(self, keywords: List[str]) -> List[RawDocument]:
        import os

        if not self.config.url:
            return []

        os.makedirs("data/cache", exist_ok=True)
        cache_key = hashlib.md5(self.config.url.encode()).hexdigest()
        cache_file = f"data/cache/rss_{cache_key}.json"

        cached = load_cache(cache_file, self.cache_ttl_hours, self.force_refresh)
        if cached is not None:
            return self._deserialize(cached)

        feed = feedparser.parse(self.config.url)
        documents = []

        for i, entry in enumerate(feed.entries[: self.max_entries]):
            title = entry.get("title", "")
            summary = entry.get("summary", "") or entry.get("description", "")
            content = f"{title}. {summary}".strip()

            if len(content.split()) < 30 or is_boilerplate(content):
                continue
            if keywords and not any(kw.lower() in content.lower() for kw in keywords):
                continue

            link = entry.get("link", self.config.url)
            doc_id = hashlib.md5(link.encode()).hexdigest()[:12]

            documents.append(
                RawDocument(
                    id=f"{self.config.identifier}_{doc_id}",
                    source=self.config.identifier,
                    content=content,
                    metadata={
                        "url": link,
                        "title": title,
                        "source_name": feed.feed.get("title", "RSS"),
                        "published_at": entry.get("published"),
                        "author": entry.get("author"),
                        "type": "rss",
                    },
                )
            )

        if documents:
            save_cache(cache_file, self._serialize(documents))
            print(f"   [Cache] {len(documents)} entrees RSS mises en cache.")

        return documents

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
