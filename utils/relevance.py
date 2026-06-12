from typing import List, Tuple

from utils.provenance import matched_keywords

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


def compute_relevance_score(text: str, keywords: List[str], theme: str = "") -> float:
    """Score de pertinence simple (0-1) base sur mots-cles et theme."""
    if not text.strip():
        return 0.0

    text_lower = text.lower()
    kw_matches = len(matched_keywords(text, keywords))
    kw_score = kw_matches / max(len(keywords), 1)

    theme_bonus = 0.15 if theme and theme.lower() in text_lower else 0.0
    length_bonus = min(len(text.split()) / 200, 0.15)

    return min(kw_score * 0.7 + theme_bonus + length_bonus, 1.0)


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
    min_relevance_score: float = 0.10,
) -> Tuple[List, List[dict]]:
    """Filtre pertinence, langue et boilerplate sur documents bruts."""
    kept = []
    rejected = []

    for doc in documents:
        text = doc.content
        doc_id = getattr(doc, "id", "unknown")
        source = getattr(doc, "source", "unknown")
        is_synthetic = (doc.metadata or {}).get("is_synthetic", source == "mock")

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

        matches = matched_keywords(text, keywords)
        score = compute_relevance_score(text, keywords, theme)

        if len(matches) < min_keyword_matches and score < min_relevance_score:
            rejected.append(
                {
                    "id": doc_id,
                    "stage": "relevance_filter",
                    "reason": "low_relevance",
                    "relevance_score": round(score, 4),
                    "keywords_matched": matches,
                    "source": source,
                }
            )
            continue

        kept.append(doc)

    return kept, rejected
