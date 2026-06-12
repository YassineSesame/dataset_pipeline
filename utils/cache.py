from datetime import datetime, timedelta
import json
import os
from typing import Any, Optional


def load_cache(cache_file: str, ttl_hours: float, force_refresh: bool = False) -> Optional[Any]:
    """Charge le cache si present et non expire."""
    if force_refresh or not os.path.exists(cache_file):
        return None

    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            payload = json.load(f)
        cached_at = datetime.fromisoformat(payload["cached_at"])
        if datetime.now() - cached_at > timedelta(hours=ttl_hours):
            print(f"   [Cache] Expire ({ttl_hours}h) — rechargement...")
            return None
        print(f"   [Cache] Hit ({cache_file})")
        return payload["data"]
    except Exception as e:
        print(f"   ! Erreur lecture cache: {e}")
        return None


def save_cache(cache_file: str, data: Any) -> None:
    os.makedirs(os.path.dirname(cache_file) or ".", exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(
            {"cached_at": datetime.now().isoformat(), "data": data},
            f,
            ensure_ascii=False,
            indent=2,
        )
