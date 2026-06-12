# Pipeline Intelligent de Datasets

Automatise la collecte, le traitement NLP, l'enrichissement IA et l'export de jeux de données thématiques.

## Fonctionnalités

- Sources : Wikipedia API, NewsAPI, RSS, import CSV/JSON
- NLP avec spaCy (entités, score de qualité)
- Enrichissement optionnel : Gemini / Ollama
- Traçabilité : provenance, `manifest.json`, `rejected.json`
- Interface Streamlit

## Installation

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m spacy download fr_core_news_sm
copy .env.example .env
```

## Lancement

```powershell
.\venv\Scripts\python.exe -m streamlit run app.py
```

## Configuration

Définissez vos clés dans `.env` :

```
NEWSAPI_KEY=
GEMINI_API_KEY=
```

## Présentation

Voir [PRESENTATION.md](PRESENTATION.md) pour une présentation complète du projet.

## Branches

- `main` — version stable
- `develop` — développement actif
