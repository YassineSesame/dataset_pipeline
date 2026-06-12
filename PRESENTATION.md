# Pipeline Intelligent de Datasets
### Automatiser la collecte, l'analyse et l'export de jeux de données thématiques

**Projet :** Dataset Pipeline  
**Version :** 3.0 (Tier 1 + Tier 2)  
**Stack :** Python · Streamlit · spaCy · Gemini

---

## Slide 1 — Titre

# 🧠 Pipeline Intelligent de Datasets

**Créer automatiquement des jeux de données fiables à partir du Web**

- Collecte multi-sources  
- Traitement NLP  
- Enrichissement IA (optionnel)  
- Export JSON / CSV avec traçabilité complète  

*Présentation du projet — 2026*

---

## Slide 2 — Problématique

### Pourquoi ce projet ?

La création manuelle de datasets pour l'IA ou la recherche est :

| Problème | Conséquence |
|----------|-------------|
| **Chronophage** | Copier-coller article par article |
| **Peu reproductible** | Difficile de refaire la même collecte |
| **Peu traçable** | Source, date, auteur souvent perdus |
| **Qualité inégale** | Doublons, textes courts, hors-sujet |

> **Objectif :** automatiser la chaîne complète tout en gardant un niveau de confiance proche d'une curation manuelle.

---

## Slide 3 — Solution proposée

### Une usine à datasets en 5 étapes

```
Sources Web  →  Collecte  →  NLP  →  Validation  →  Enrichissement IA  →  Export
```

**Ce que le pipeline produit :**
- Des documents nettoyés et scorés  
- Des métadonnées de provenance (URL, source, date)  
- Des labels IA optionnels (résumé, catégorie, sentiment, Q&A)  
- Un rapport d'exécution (`manifest.json`) et de rejets (`rejected.json`)  

**Interface :** application web Streamlit — configuration en quelques clics.

---

## Slide 4 — Architecture du projet

```
dataset-pipeline/
├── app.py                    # Interface Streamlit
├── core/pipeline.py          # Orchestrateur principal
├── connectors/               # Sources de données
│   ├── wikipedia_api_connector.py
│   ├── news_api_connector.py
│   ├── rss_connector.py
│   └── web_scraper.py
├── processors/nlp_processor.py   # spaCy
├── validators/quality_validator.py
├── enrichers/llm_enricher.py     # Gemini / Ollama
├── utils/                    # Cache, dédup, pertinence
└── data/runs/{run_id}/       # Exports + audit
```

**Principe :** architecture modulaire — chaque source est un connecteur interchangeable.

---

## Slide 5 — Les sources de données (Tier 2)

| Source | Rôle | Exemple d'usage |
|--------|------|-----------------|
| **Wikipedia API** | Plusieurs articles par thème | COVID, éducation, vaccins |
| **NewsAPI** | Actualités + texte complet | Articles récents en français |
| **Flux RSS** | Flux structurés | éduscol, Franceinfo Santé |
| **Import CSV/JSON** | Données déjà possédées | Curation hybride |
| **Mock (dev only)** | Tests | Désactivé par défaut en production |

**Extraction avancée :** trafilatura suit les URLs NewsAPI pour récupérer l'article intégral (plus de `[+5720 chars]`).

---

## Slide 6 — Étape 1 : Collecte

**Ce qui se passe :**
1. Connexion à chaque source configurée  
2. Récupération des documents bruts (`RawDocument`)  
3. Métadonnées attachées : URL, titre, auteur, date  
4. **Cache TTL** : Wikipedia 7 jours · News/RSS 24 h  
5. Option **Forcer le rechargement** pour ignorer le cache  

**Exemple concret (thème COVID / santé) :**
- 49 paragraphes Wikipedia  
- 43 articles NewsAPI  
- **92 documents bruts** en une exécution  

---

## Slide 7 — Étape 2 : Filtrage & déduplication

### Déduplication
- Hash du contenu normalisé  
- Suppression des doublons exacts  
- Rapport dans `rejected.json`

### Filtrage pertinence (Tier 2)
- **Langue** détectée (langdetect) — ex. rejeter le français si langue = `en`  
- **Boilerplate** — « voir aussi », « références », etc.  
- **Score de pertinence** — mots-clés + thème + longueur  

> Sépare **qualité du texte** et **pertinence au sujet** — deux critères distincts.

---

## Slide 8 — Étape 3 : Traitement NLP (spaCy)

**Modèles :** `fr_core_news_sm` · `en_core_web_sm`

| Traitement | Détail |
|------------|--------|
| Nettoyage | URLs, emails, espaces superflus |
| Entités nommées | PERSON, ORG, LOC, MISC… |
| Score de qualité | Longueur (60 %) + entités (40 %) |
| Filtre | Seuil configurable par document |

**Score de qualité :** note automatique de 0 à 1 — **pas** une note humaine.

---

## Slide 9 — Étape 4 : Validation qualité

**Contrôles globaux (sans triche) :**
- Minimum de documents (ex. 5)  
- Qualité moyenne minimum (ex. 0,15)  
- Longueur moyenne minimum (ex. 50 mots)  

**Si échec :** le pipeline **s'arrête** et écrit un manifest d'échec — pas de baisse silencieuse des seuils.

**Tier 1 — Confiance :**
- Aucune donnée synthétique mélangée sans label `is_synthetic: true`  
- Provenance complète sur chaque document exporté  

---

## Slide 10 — Étape 5 : Enrichissement IA (optionnel)

**Moteurs supportés :**

| Moteur | Type | Usage recommandé |
|--------|------|------------------|
| **Google Gemini** | Cloud | Rapide, bon JSON structuré |
| **Ollama** | Local | Gratuit, offline, plus lent |
| **Désactivé** | — | Dataset brut NLP seulement |

**Par document enrichi :**
- Résumé en 1 phrase  
- Catégorie thématique (adaptée au thème : santé, éducation…)  
- Sentiment (Positif / Négatif / Neutre)  
- Mots-clés  
- Paires question / réponse  

**Limite configurable :** seuls les N meilleurs documents (par score) sont enrichis pour économiser les tokens API.

---

## Slide 11 — Traçabilité & export (Tier 1)

### Structure d'un run

```
data/runs/20260612_184813_ae0c2767/
├── dataset.json      # Export principal (schéma v1.1)
├── dataset.csv       # Vue tabulaire résumée
├── manifest.json     # Config, stats, validation
└── rejected.json     # Doublons + rejets + raisons
```

### Provenance par document

```json
{
  "source_type": "wikipedia_api",
  "source_url": "https://fr.wikipedia.org/wiki/...",
  "source_name": "Wikipedia",
  "collected_at": "2026-06-12T18:48:13",
  "pipeline_run_id": "20260612_184813_ae0c2767",
  "keywords_matched": ["covid", "vaccin"],
  "is_synthetic": false
}
```

---

## Slide 12 — Interface Streamlit

**Sidebar — configuration :**
- Thème : santé, éducation, finance, technologie…  
- Mots-clés personnalisables  
- Sources : Wikipedia API, RSS, NewsAPI, import fichier  
- IA : Gemini / Ollama / désactivé  
- Paramètres avancés : seuils, langue, cache  

**Page principale — résultats :**
- Métriques : documents, qualité moyenne, mots/doc  
- Onglets : Tableau · Aperçu · Téléchargement · **Traçabilité**  
- Provenance et métadonnées par document  

---

## Slide 13 — Démo : cas d'usage COVID / vaccins

**Configuration type :**

| Paramètre | Valeur |
|-----------|--------|
| Thème | `sante` |
| Mots-clés | covid, vaccin, coronavirus, immunisation, mrna… |
| Sources | Wikipedia API + NewsAPI + RSS (optionnel) |
| Langue | **fr** (recommandé) |
| Mock | **OFF** |

**Résultats observés :**
- ~92 documents réels  
- Qualité moyenne ~0,76  
- 0 document synthétique  
- ~88 % des docs contiennent des termes COVID/vaccin  

---

## Slide 14 — Résultats & métriques

### Comparaison avant / après Tier 2

| Métrique | Avant (1 page Wiki) | Après (Wikipedia API) |
|----------|---------------------|------------------------|
| Documents | ~11 | ~50–92 |
| Qualité moyenne | ~0,16 | ~0,56–0,76 |
| Sources | 1 page fixe | Multi-articles |
| Échecs validation | Fréquents | Rares |

### Ce qui fonctionne bien ✅
- Volume et qualité textuelle  
- Traçabilité complète  
- Pas de données fake en mode production  
- Export reproductible  

---

## Slide 15 — Limites actuelles

| Limite | Impact |
|--------|--------|
| Score qualité ≠ pertinence thématique | Articles hors-sujet possibles (~10 %) |
| NewsAPI bruité si requête trop large | Ex. articles non liés au COVID |
| Modèles Gemini 1.5 dépréciés | Utiliser **gemini-2.5-flash** |
| Clés API visibles dans manifest | À redacter (amélioration prévue) |
| Pas de relecture humaine intégrée | Tier 3 prévu |

> Un score de **1,0** ne garantit pas que le document est **on-topic** — toujours vérifier la provenance.

---

## Slide 16 — Feuille de route

### ✅ Tier 1 — Confiance (implémenté)
Provenance · Pas de mock silencieux · Déduplication · Validation honnête · Secrets `.env`

### ✅ Tier 2 — Meilleures données (implémenté)
Wikipedia API · RSS · Extraction articles · Cache TTL · Filtres pertinence/langue · Catégories IA par thème

### 🔜 Tier 3 — Production
- Relecture humaine avant export  
- Filtre thématique strict (ex. COVID **ET** vaccin)  
- Masquage des clés API dans les manifests  
- Tests automatisés · README · Planification des runs  

---

## Slide 17 — Stack technique

| Composant | Technologie |
|-----------|-------------|
| Langage | Python 3.12 |
| Interface | Streamlit |
| NLP | spaCy (`fr_core_news_sm`) |
| Scraping / extraction | BeautifulSoup, trafilatura |
| Actualités | NewsAPI |
| Flux | feedparser |
| Langue | langdetect |
| IA | google-generativeai, Ollama |
| Données | pandas, JSON, CSV |
| Config | python-dotenv |

---

## Slide 18 — Comment lancer le projet

```powershell
# 1. Installer les dépendances
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m spacy download fr_core_news_sm

# 2. Configurer les clés (optionnel)
copy .env.example .env
# NEWSAPI_KEY=...  GEMINI_API_KEY=...

# 3. Lancer l'interface
.\venv\Scripts\python.exe -m streamlit run app.py
```

**CLI (sans interface) :**
```powershell
.\venv\Scripts\python.exe run.py
```

---

## Slide 19 — Conclusion

### En résumé

Le **Pipeline Intelligent de Datasets** transforme une tâche manuelle fastidieuse en un **processus automatisé, traçable et reproductible**.

**Points forts :**
- Architecture modulaire et extensible  
- Multi-sources (Web, API, RSS, fichiers)  
- Audit complet de chaque exécution  
- Enrichissement IA optionnel  

**Vision :** devenir un outil de référence pour construire des datasets **dignes de confiance** — pas seulement volumineux.

---

## Slide 20 — Questions & démo live

# Merci pour votre attention 🙏

**Démonstration live suggérée :**
1. Thème **santé** · mots-clés COVID/vaccin  
2. Wikipedia API + Gemini 2.5 Flash  
3. Explorer un document : texte · provenance · enrichissements IA  
4. Télécharger le JSON · ouvrir `manifest.json` et `rejected.json`  

**Contact / repo :** [chemin du projet local ou GitHub]

---

## Annexe — Glossaire

| Terme | Définition |
|-------|------------|
| **Document brut** | Texte collecté avant NLP |
| **Score de qualité** | Note 0–1 basée sur longueur + entités spaCy |
| **Provenance** | Origine vérifiable du document |
| **Run ID** | Identifiant unique d'une exécution du pipeline |
| **is_synthetic** | `true` = donnée de test générée (mode dev) |
| **Enrichissement** | Labels IA ajoutés post-NLP (résumé, catégorie…) |

---

## Annexe — Exemple de configuration éducation

```
Thème          : education
Mots-clés      : éducation, enseignement, école, formation, apprentissage
Wikipedia API  : ON
Flux RSS       : https://eduscol.education.fr/rid271/toute-l-actualite-du-site.rss
Langue         : fr
Qualité moy.   : 0,15
IA             : Gemini 2.5 Flash · 5 documents max
```

---

*Document généré pour la présentation du projet Dataset Pipeline — utilisable avec Marp, PowerPoint (copier les slides), ou Canva.*
