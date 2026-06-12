import hashlib
import re
from typing import List, Tuple


def normalize_text(text: str) -> str:
    """Normalise le texte pour la détection de doublons."""
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def content_hash(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def deduplicate_documents(documents: List, content_attr: str = "content") -> Tuple[List, List[dict]]:
    """
    Supprime les doublons exacts (contenu normalisé identique).
    Conserve le premier document rencontré.
    """
    seen = {}
    unique = []
    rejected = []

    for doc in documents:
        text = getattr(doc, content_attr, "")
        key = content_hash(text)

        if key in seen:
            rejected.append({
                "id": getattr(doc, "id", "unknown"),
                "duplicate_of": seen[key],
                "reason": "duplicate_content",
                "content_hash": key[:16],
            })
            continue

        seen[key] = getattr(doc, "id", "unknown")
        unique.append(doc)

    return unique, rejected
