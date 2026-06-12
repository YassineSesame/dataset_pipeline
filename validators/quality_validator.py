from typing import Tuple, List


class QualityValidator:
    """Verifie la qualite globale du dataset."""

    def __init__(
        self,
        min_documents: int = 5,
        min_avg_quality: float = 0.20,
        min_avg_length: int = 50,
        min_avg_relevance: float = 0.12,
    ):
        self.rules = {
            "min_documents": min_documents,
            "min_avg_quality": min_avg_quality,
            "min_avg_length": min_avg_length,
            "min_avg_relevance": min_avg_relevance,
        }

    def validate(self, documents: List) -> Tuple[bool, List[str]]:
        errors = []

        if len(documents) < self.rules["min_documents"]:
            errors.append(
                f"Trop peu de documents: {len(documents)} < {self.rules['min_documents']}"
            )

        if documents:
            avg_quality = sum(d.quality_score for d in documents) / len(documents)
            if avg_quality < self.rules["min_avg_quality"]:
                errors.append(
                    f"Qualite moyenne trop faible: {avg_quality:.2f} < {self.rules['min_avg_quality']:.2f}"
                )

        if documents:
            avg_relevance = sum(getattr(d, "relevance_score", 0) for d in documents) / len(documents)
            if avg_relevance < self.rules["min_avg_relevance"]:
                errors.append(
                    f"Pertinence moyenne trop faible: {avg_relevance:.2f} < {self.rules['min_avg_relevance']:.2f}"
                )

        if documents:
            avg_length = sum(d.word_count for d in documents) / len(documents)
            if avg_length < self.rules["min_avg_length"]:
                errors.append(
                    f"Textes trop courts: {avg_length:.0f} mots en moyenne "
                    f"(minimum {self.rules['min_avg_length']})"
                )

        return len(errors) == 0, errors
