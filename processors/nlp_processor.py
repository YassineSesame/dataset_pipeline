import spacy
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass, field

from utils.provenance import infer_source_type, matched_keywords


@dataclass
class ProcessedDocument:
    """Document apres traitement NLP."""
    id: str
    original_id: str
    cleaned_text: str
    entities: List[Dict] = field(default_factory=list)
    word_count: int = 0
    quality_score: float = 0.0
    source: str = ""
    source_type: str = ""
    metadata: Dict = field(default_factory=dict)
    collected_at: datetime = field(default_factory=datetime.now)
    keywords_matched: List[str] = field(default_factory=list)
    is_synthetic: bool = False


class NLPProcessor:
    """Traite le texte avec spaCy."""

    _models = {}

    def __init__(self, language: str = "fr"):
        self.language = language
        model_name = "fr_core_news_sm" if language == "fr" else "en_core_web_sm"

        if model_name not in NLPProcessor._models:
            print(f"   [NLP] Chargement du modele spaCy '{model_name}' (premiere fois)...")
            NLPProcessor._models[model_name] = spacy.load(model_name)
        else:
            print(f"   [NLP] Utilisation du modele spaCy '{model_name}' en cache local...")

        self.nlp = NLPProcessor._models[model_name]

    def process(self, raw_doc, keywords: List[str] = None) -> ProcessedDocument:
        keywords = keywords or []
        cleaned = self._clean_text(raw_doc.content)
        doc = self.nlp(cleaned)

        entities = [{"text": ent.text, "label": ent.label_} for ent in doc.ents]
        quality = self._calculate_quality(cleaned, entities)
        metadata = raw_doc.metadata or {}
        is_synthetic = metadata.get("is_synthetic", raw_doc.source == "mock")

        return ProcessedDocument(
            id=f"proc_{raw_doc.id}",
            original_id=raw_doc.id,
            cleaned_text=cleaned,
            entities=entities,
            word_count=len(cleaned.split()),
            quality_score=quality,
            source=raw_doc.source,
            source_type=infer_source_type(raw_doc.source, metadata),
            metadata=metadata,
            collected_at=raw_doc.collected_at,
            keywords_matched=matched_keywords(cleaned, keywords),
            is_synthetic=is_synthetic,
        )

    def _clean_text(self, text: str) -> str:
        import re

        text = re.sub(r"http\S+", "", text)
        text = re.sub(r"\S+@\S+", "", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _calculate_quality(self, text: str, entities: List) -> float:
        if len(text.split()) < 20:
            return 0.1
        if len(text.split()) > 500:
            length_score = 1.0
        else:
            length_score = len(text.split()) / 500

        entity_score = min(len(entities) / 5, 1.0)
        return length_score * 0.6 + entity_score * 0.4
