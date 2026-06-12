import os
from dataclasses import dataclass, field
from typing import List, Any

from dotenv import load_dotenv

load_dotenv()


@dataclass
class PipelineConfig:
    theme: str
    keywords: List[str]
    sources: List[dict] = field(default_factory=list)
    language: str = "fr"
    min_quality: float = 0.15
    min_avg_quality: float = 0.15
    min_documents: int = 5
    min_avg_length: int = 50
    allow_mock_fallback: bool = False
    output_format: str = "json"
    # Tier 2
    force_refresh: bool = False
    max_docs_per_source: int = 50
    wiki_max_pages: int = 5
    extract_full_articles: bool = True
    min_keyword_matches: int = 1
    min_relevance_score: float = 0.10
    cache_ttl_hours_web: float = 168
    cache_ttl_hours_news: float = 24
    cache_ttl_hours_rss: float = 24
    uploaded_documents: List[Any] = field(default_factory=list)


def _newsapi_source(identifier: str = "newsapi_sante") -> dict:
    api_key = os.getenv("NEWSAPI_KEY", "")
    if not api_key:
        return {}
    return {
        "type": "api_news",
        "identifier": identifier,
        "api_key": api_key,
        "url": "https://newsapi.org/v2/everything",
    }


_sante_sources = [
    {
        "type": "wikipedia_api",
        "identifier": "wiki_vaccin",
    }
]
_news_source = _newsapi_source()
if _news_source:
    _sante_sources.append(_news_source)

SANTE_CONFIG = PipelineConfig(
    theme="sante",
    keywords=["vaccin", "immunite", "virus", "maladie", "traitement"],
    sources=_sante_sources,
    allow_mock_fallback=False,
)
