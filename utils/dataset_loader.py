from typing import Any, Dict, List, Tuple


def load_dataset_file(path: str) -> Tuple[List[dict], Dict[str, Any]]:
    """
    Charge un fichier dataset JSON (format legacy liste ou enveloppe v1).
    Retourne (documents, metadata_enveloppe).
    """
    import json

    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, list):
        return payload, {}

    if isinstance(payload, dict) and "documents" in payload:
        meta = {k: v for k, v in payload.items() if k != "documents"}
        return payload["documents"], meta

    raise ValueError("Format de dataset non reconnu.")
