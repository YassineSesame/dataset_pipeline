import csv
import io
import json
from typing import List

from connectors.base import RawDocument


def parse_uploaded_file(file_bytes: bytes, filename: str) -> List[RawDocument]:
    """Parse un fichier CSV ou JSON uploade en RawDocuments."""
    name = (filename or "").lower()
    documents = []

    if name.endswith(".json"):
        payload = json.loads(file_bytes.decode("utf-8"))
        if isinstance(payload, dict) and "documents" in payload:
            items = payload["documents"]
        elif isinstance(payload, list):
            items = payload
        else:
            raise ValueError("JSON invalide : attendu une liste ou {documents: [...]}")

        for i, item in enumerate(items):
            text = item.get("text") or item.get("content") or ""
            if len(text.strip()) < 20:
                continue
            documents.append(
                RawDocument(
                    id=item.get("id", f"upload_{i+1}"),
                    source="file_upload",
                    content=text.strip(),
                    metadata={
                        "type": "file_upload",
                        "filename": filename,
                        "title": item.get("title"),
                        "url": item.get("url"),
                        "is_synthetic": False,
                    },
                )
            )

    elif name.endswith(".csv"):
        text_content = file_bytes.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text_content))
        for i, row in enumerate(reader):
            text = row.get("text") or row.get("content") or row.get("body") or ""
            if len(text.strip()) < 20:
                continue
            documents.append(
                RawDocument(
                    id=row.get("id", f"upload_{i+1}"),
                    source="file_upload",
                    content=text.strip(),
                    metadata={
                        "type": "file_upload",
                        "filename": filename,
                        "title": row.get("title"),
                        "url": row.get("url"),
                        "is_synthetic": False,
                    },
                )
            )
    else:
        raise ValueError("Format non supporte. Utilisez .json ou .csv")

    return documents
