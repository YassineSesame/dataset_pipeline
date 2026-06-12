import requests


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; DatasetPipeline/2.0; +https://github.com/local/dataset-pipeline)"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}


def extract_article_text(url: str, timeout: int = 15) -> str:
    """Extrait le texte principal d'une page web avec trafilatura."""
    if not url:
        return ""

    try:
        import trafilatura

        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            response = requests.get(url, headers=DEFAULT_HEADERS, timeout=timeout)
            response.raise_for_status()
            downloaded = response.text

        text = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=False,
            favor_precision=True,
        )
        return (text or "").strip()
    except Exception:
        return ""
