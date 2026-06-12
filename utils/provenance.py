from datetime import datetime
from typing import Any, Dict, List, Optional


def infer_source_type(source_id: str, metadata: Optional[Dict[str, Any]] = None) -> str:
    metadata = metadata or {}
    meta_type = metadata.get("type", "")
    if metadata.get("is_synthetic") or meta_type == "mock" or source_id == "mock":
        return "mock"
    if meta_type in ("api_news", "rss", "wikipedia_api", "web", "file_upload"):
        return meta_type if meta_type != "web" else "web"
    if source_id.startswith("news") or meta_type == "api_news":
        return "api_news"
    if source_id.startswith("wiki") or metadata.get("url"):
        return "wikipedia_api" if meta_type == "wikipedia_api" else "web"
    if source_id == "file_upload":
        return "file_upload"
    return "unknown"


def matched_keywords(text: str, keywords: List[str]) -> List[str]:
    text_lower = text.lower()
    return [kw for kw in keywords if kw.lower() in text_lower]


def build_provenance(
    *,
    source_id: str,
    metadata: Dict[str, Any],
    keywords: List[str],
    text: str,
    collected_at: datetime,
    pipeline_run_id: str,
    is_synthetic: bool = False,
) -> Dict[str, Any]:
    source_type = infer_source_type(source_id, metadata)
    return {
        "source_type": source_type,
        "source_id": source_id,
        "source_url": metadata.get("url"),
        "source_name": metadata.get("source_name") or metadata.get("title"),
        "author": metadata.get("author"),
        "published_at": metadata.get("published_at"),
        "collected_at": collected_at.isoformat() if collected_at else None,
        "pipeline_run_id": pipeline_run_id,
        "keywords_matched": matched_keywords(text, keywords),
        "is_synthetic": is_synthetic,
    }
