from typing import List, Tuple

from configs.theme_categories import get_theme_core_terms
from utils.provenance import infer_source_type, matched_keywords

BOILERPLATE_PATTERNS = [
    "modifier le code",
    "voir aussi",
    "references",
    "article connexe",
    "click here",
    "read more",
    "subscribe",
    "cookie",
    "all rights reserved",
]


def _search_text(doc) -> str:
    metadata = getattr(doc, "metadata", None) or {}
    title = metadata.get("title", "") or ""
    content = getattr(doc, "content", "") or ""
    return f"{title}. {content}".strip()


def compute_relevance_score(text: str, keywords: List[str], theme: str = "") -> float:
    """
    Score de pertinence thématique (0-1).
    Distinct du quality_score (longueur + entités spaCy).
    """
    if not text.strip():
        return 0.0

    text_lower = text.lower()
    matches = matched_keywords(text, keywords)
    kw_score = len(matches) / max(len(keywords), 1)

    core_terms = get_theme_core_terms(theme)
    core_hits = sum(1 for term in core_terms if term.lower() in text_lower)
    core_score = min(core_hits / 3, 1.0) if core_terms else 0.0

    theme_bonus = 0.1 if theme and theme.lower() in text_lower else 0.0
    title_bonus = 0.1 if matches and text[:200].lower() != text_lower else 0.0

    if core_terms and core_hits == 0 and len(matches) < 2:
        return min(kw_score * 0.4, 0.35)

    return min(kw_score * 0.45 + core_score * 0.35 + theme_bonus + title_bonus, 1.0)


def passes_theme_relevance(
    doc,
    keywords: List[str],
    theme: str,
    min_keyword_matches: int = 1,
    min_relevance_score: float = 0.15,
    strict_news: bool = True,
) -> Tuple[bool, float, List[str], str]:
    """
    Retourne (accepté, score, mots-clés matchés, raison de rejet éventuelle).
    """
    text = _search_text(doc)
    metadata = getattr(doc, "metadata", None) or {}
    source_type = infer_source_type(getattr(doc, "source", ""), metadata)
    is_synthetic = metadata.get("is_synthetic", getattr(doc, "source", "") == "mock")

    if is_synthetic or source_type == "file_upload":
        score = compute_relevance_score(text, keywords, theme)
        return True, score, matched_keywords(text, keywords), ""

    matches = matched_keywords(text, keywords)
    score = compute_relevance_score(text, keywords, theme)

    effective_min_kw = min_keyword_matches
    if strict_news and source_type == "api_news":
        effective_min_kw = max(min_keyword_matches, 2)

    core_terms = get_theme_core_terms(theme)
    has_core = any(term.lower() in text.lower() for term in core_terms) if core_terms else True

    if len(matches) < effective_min_kw and score < min_relevance_score:
        return False, score, matches, "low_relevance"

    if core_terms and not has_core and len(matches) < 2:
        return False, score, matches, "off_topic"

    if score < min_relevance_score and len(matches) < effective_min_kw:
        return False, score, matches, "low_relevance"

    return True, score, matches, ""


def is_boilerplate(text: str) -> bool:
    text_lower = text.lower()
    return any(pattern in text_lower for pattern in BOILERPLATE_PATTERNS)


def detect_language(text: str) -> str:
    try:
        from langdetect import detect

        return detect(text[:800])
    except Exception:
        return "unknown"


def is_expected_language(text: str, expected: str) -> bool:
    lang = detect_language(text)
    if lang == "unknown":
        return True
    return lang.startswith(expected[:2])


def filter_raw_documents(
    documents: List,
    keywords: List[str],
    theme: str,
    expected_language: str = "fr",
    min_keyword_matches: int = 1,
    min_relevance_score: float = 0.15,
    strict_news: bool = True,
) -> Tuple[List, List[dict]]:
    """Filtre pertinence thématique, langue et boilerplate."""
    kept = []
    rejected = []

    for doc in documents:
        doc_id = getattr(doc, "id", "unknown")
        source = getattr(doc, "source", "unknown")
        text = _search_text(doc)
        metadata = getattr(doc, "metadata", None) or {}
        is_synthetic = metadata.get("is_synthetic", source == "mock")

        if is_synthetic:
            kept.append(doc)
            continue

        if is_boilerplate(text):
            rejected.append(
                {
                    "id": doc_id,
                    "stage": "relevance_filter",
                    "reason": "boilerplate",
                    "source": source,
                }
            )
            continue

        if not is_expected_language(text, expected_language):
            rejected.append(
                {
                    "id": doc_id,
                    "stage": "relevance_filter",
                    "reason": "wrong_language",
                    "detected": detect_language(text),
                    "expected": expected_language,
                    "source": source,
                }
            )
            continue

        ok, score, matches, reject_reason = passes_theme_relevance(
            doc,
            keywords,
            theme,
            min_keyword_matches=min_keyword_matches,
            min_relevance_score=min_relevance_score,
            strict_news=strict_news,
        )

        if not ok:
            rejected.append(
                {
                    "id": doc_id,
                    "stage": "relevance_filter",
                    "reason": reject_reason,
                    "relevance_score": round(score, 4),
                    "keywords_matched": matches,
                    "source": source,
                    "source_type": infer_source_type(source, metadata),
                }
            )
            continue

        kept.append(doc)

    return kept, rejected
