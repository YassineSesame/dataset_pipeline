import streamlit as st
import json
import pandas as pd
from datetime import datetime
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import importlib
import core.pipeline
import configs.settings
import enrichers.llm_enricher

importlib.reload(core.pipeline)
importlib.reload(configs.settings)
importlib.reload(enrichers.llm_enricher)

from core.pipeline import DatasetPipeline
from configs.settings import PipelineConfig
from utils.dataset_loader import load_dataset_file
from utils.file_parser import parse_uploaded_file


st.set_page_config(
    page_title="Pipeline Dataset Intelligence",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .success-box {
        padding: 1rem;
        background-color: #d4edda;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)


# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.title("⚙️ Configuration")

st.sidebar.markdown("---")

theme = st.sidebar.selectbox(
    "🎯 Thème du dataset",
    ["sante", "finance", "technologie", "environnement", "education", "custom"],
    index=0
)

default_keywords = {
    "sante": "vaccin, immunite, virus, maladie, traitement",
    "finance": "bourse, investissement, crypto, economie",
    "technologie": "intelligence artificielle, robotique, blockchain",
    "environnement": "climat, energie, pollution, biodiversite",
    "education": "apprentissage, ecole, formation, elearning",
    "custom": ""
}

keywords_input = st.sidebar.text_area(
    "🔑 Mots-clés (séparés par des virgules)",
    value=default_keywords.get(theme, ""),
    height=80
)

st.sidebar.markdown("---")
st.sidebar.subheader("📡 Sources")

use_wikipedia = st.sidebar.checkbox(
    "Wikipédia (API — plusieurs articles)",
    value=True,
    help="Recherche plusieurs articles Wikipedia liés aux mots-clés (Tier 2).",
)
rss_url = st.sidebar.text_input(
    "Flux RSS (optionnel)",
    value="",
    placeholder="https://example.com/feed.xml",
    help="Ajoute un flux RSS/Atom comme source.",
)
uploaded_file = st.sidebar.file_uploader(
    "Import CSV/JSON (optionnel)",
    type=["csv", "json"],
    help="Colonnes CSV : text ou content. JSON : liste ou {documents: [...]}.",
)
force_refresh = st.sidebar.checkbox(
    "Forcer le rechargement (ignorer cache)",
    value=False,
)
extract_full_articles = st.sidebar.checkbox(
    "Extraire le texte complet (NewsAPI)",
    value=True,
    help="Suit les URLs des articles pour récupérer le contenu intégral via trafilatura.",
)
use_mock = st.sidebar.checkbox(
    "Données de test (mode dev uniquement)",
    value=False,
    help="Ajoute des textes SYNTHÉTIQUES si les sources réelles ne suffisent pas. "
         "Désactivé par défaut pour des datasets fiables.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("🔑 Clés API")

newsapi_key = st.sidebar.text_input(
    "NewsAPI Key (optionnel)",
    value=os.getenv("NEWSAPI_KEY", ""),
    type="password",
    help="Obtenez une clé gratuite sur newsapi.org ou définissez NEWSAPI_KEY dans .env"
)

# AJOUT DU SÉLECTEUR D'IA GRATUITE ICI
st.sidebar.markdown("---")
st.sidebar.subheader("🧠 Intelligence Artificielle")

ai_provider = st.sidebar.selectbox(
    "Moteur d'enrichissement",
    ["Désactivé (Aucune IA)", "Ollama (Local - Gratuit)", "Google Gemini (Cloud - Gratuit)"],
    index=0
)

ai_provider_code = "none"
ai_key = ""
ai_model = ""
max_enrich_docs = 10

if ai_provider == "Ollama (Local - Gratuit)":
    ai_provider_code = "ollama"
    ai_model = st.sidebar.text_input(
        "Nom du modèle Ollama",
        value="llama3.2:1b",
        help="Recommandé pour la rapidité sur CPU : llama3.2:1b (1 milliard de paramètres). Assurez-vous d'avoir lancé la commande 'ollama run <modèle>' dans votre terminal."
    )
elif ai_provider == "Google Gemini (Cloud - Gratuit)":
    ai_provider_code = "gemini"
    ai_key = st.sidebar.text_input(
        "Clé API Gemini",
        value="",
        type="password",
        help="Clé gratuite disponible sur aistudio.google.com"
    )
    ai_model = st.sidebar.selectbox(
        "Modèle Gemini",
        ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro"],
        index=0
    )

if ai_provider != "Désactivé (Aucune IA)":
    max_enrich_docs = st.sidebar.slider(
        "Max documents à enrichir par l'IA",
        min_value=1,
        max_value=200,  # Augmenté à 200 pour laisser une totale liberté de volume
        value=5,        # Par défaut à 5 pour des résultats immédiats (< 1 minute), personnalisable à volonté
        help="L'IA n'enrichira que les meilleurs documents (triés par qualité). Les autres recevront des valeurs par défaut pour optimiser le temps."
    )


st.sidebar.markdown("---")
with st.sidebar.expander("🔧 Paramètres avancés"):
    min_quality = st.slider("Seuil qualité (par document)", 0.0, 1.0, 0.10, 0.05)
    min_avg_quality = st.slider(
        "Qualité moyenne minimum",
        0.0, 1.0, 0.15, 0.05,
        help="Wikipedia seul : ~0.15. Avec NewsAPI : vous pouvez viser 0.20+.",
    )
    min_documents = st.slider("Documents minimum", 1, 20, 5)
    max_docs = st.slider("Max documents par source", 5, 100, 50)
    wiki_max_pages = st.slider("Pages Wikipedia max", 1, 10, 5)
    language = st.selectbox(
        "Langue",
        ["fr", "en"],
        index=0,
        help="Pour covid/vaccin en français, laissez **fr**.",
    )

st.sidebar.markdown("---")
run_button = st.sidebar.button("🚀 Lancer le Pipeline", type="primary", use_container_width=True)


# ============================================================
# PAGE PRINCIPALE
# ============================================================
st.markdown('<p class="main-header">🧠 Pipeline Intelligent de Datasets</p>', unsafe_allow_html=True)

st.markdown("""
Créez automatiquement des jeux de données thématiques à partir de sources variées.
Le pipeline collecte, nettoie, analyse et exporte vos données en quelques clics.
""")

if 'dataset_result' not in st.session_state:
    st.session_state.dataset_result = None
if 'dataset_meta' not in st.session_state:
    st.session_state.dataset_meta = {}
if 'logs' not in st.session_state:
    st.session_state.logs = []

# ============================================================
# LANCEMENT
# ============================================================
if run_button:
    keywords = [k.strip() for k in keywords_input.split(",") if k.strip()]
    
    sources = []
    if use_wikipedia:
        sources.append({
            "type": "wikipedia_api",
            "identifier": f"wiki_{theme}",
        })

    if rss_url.strip():
        sources.append({
            "type": "rss",
            "identifier": "rss_custom",
            "url": rss_url.strip(),
        })

    if newsapi_key:
        sources.append({
            "type": "api_news",
            "identifier": "newsapi",
            "api_key": newsapi_key,
            "url": "https://newsapi.org/v2/everything"
        })

    uploaded_docs = []
    if uploaded_file is not None:
        try:
            uploaded_docs = parse_uploaded_file(uploaded_file.getvalue(), uploaded_file.name)
            st.sidebar.success(f"📎 {len(uploaded_docs)} doc(s) importé(s)")
        except Exception as upload_err:
            st.sidebar.error(f"Import fichier : {upload_err}")
    
    config = PipelineConfig(
        theme=theme,
        keywords=keywords,
        sources=sources,
        language=language,
        min_quality=min_quality,
        min_avg_quality=min_avg_quality,
        min_documents=min_documents,
        allow_mock_fallback=use_mock,
        force_refresh=force_refresh,
        max_docs_per_source=max_docs,
        wiki_max_pages=wiki_max_pages,
        extract_full_articles=extract_full_articles,
        uploaded_documents=uploaded_docs,
        output_format="json"
    )
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    # 5 phases maintenant (avec enrichissement IA)
    phases = ["Connexion aux sources...", "Collecte des données...",
              "Filtrage pertinence...", "Traitement NLP...", "Validation qualité...",
              "Enrichissement IA...", "Export final..."]
    
    for i, phase in enumerate(phases):
        status_text.text(f"⏳ {phase}")
        progress_bar.progress((i + 1) / len(phases))
        import time
        time.sleep(0.3)
    
    status_placeholder = st.empty()
    
    def streamlit_status_callback(msg):
        status_placeholder.info(f"⚡ {msg}")
        
    try:
        # Initialisation du pipeline avec le fournisseur d'IA gratuit configuré
        pipeline = DatasetPipeline(
            config, 
            ai_provider=ai_provider_code, 
            ai_key=ai_key, 
            ai_model=ai_model,
            max_enrich_docs=max_enrich_docs
        )
        result_path = pipeline.run(status_callback=streamlit_status_callback)
        
        progress_bar.empty()
        status_placeholder.empty()
        status_text.empty()
        
        if result_path:
            st.session_state.dataset_result = result_path
            st.session_state.dataset_meta = {}
            run_dir = os.path.dirname(result_path)
            manifest_path = os.path.join(run_dir, "manifest.json")
            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    st.session_state.dataset_meta = json.load(f)
            st.session_state.logs.append(f"✅ {datetime.now().strftime('%H:%M:%S')} - Dataset créé: {result_path}")
            st.rerun()
        else:
            run_dir = pipeline.run_dir
            manifest_path = os.path.join(run_dir, "manifest.json")
            rejected_path = os.path.join(run_dir, "rejected.json")

            st.error("❌ Le pipeline a échoué — voir les détails ci-dessous.")

            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                st.session_state.dataset_meta = manifest

                errors = manifest.get("validation", {}).get("errors", [])
                stats = manifest.get("stats", {})

                if errors:
                    for err in errors:
                        st.warning(err)

                st.caption(f"Run ID : `{manifest.get('run_id', 'N/A')}`")

                if stats.get("processed_before_failure"):
                    st.info(
                        f"{stats['processed_before_failure']} document(s) ont passé le filtre NLP, "
                        f"mais la validation globale a échoué."
                    )

                if any("Qualite moyenne" in e or "Qualité moyenne" in e for e in errors):
                    st.info(
                        "**Comment corriger :**\n"
                        "- Baissez **Qualité moyenne minimum** à **0.15** (Paramètres avancés)\n"
                        "- Ou ajoutez une **clé NewsAPI** pour des articles plus longs\n"
                        "- Ou baissez **Seuil qualité (par document)** à **0.05**"
                    )
                elif any("insufficient" in e.lower() or "insuffisant" in e.lower() for e in errors):
                    cfg = manifest.get("config", {})
                    collect_details = {}
                    if os.path.exists(rejected_path):
                        with open(rejected_path, "r", encoding="utf-8") as rf:
                            for rec in json.load(rf).get("records", []):
                                if rec.get("reason") == "insufficient_real_documents":
                                    collect_details = rec.get("details", {})
                                    break

                    source_counts = collect_details.get("source_counts", {})
                    if source_counts:
                        st.write("**Documents par source :**")
                        st.json(source_counts)

                    lang = collect_details.get("language") or cfg.get("language", "fr")
                    tips = [
                        "✅ Cochez **Forcer le rechargement** (ignore le cache)",
                        "✅ **Langue = fr** pour du contenu français (vous aviez peut‑être `en`)",
                        "✅ Gardez **Wikipédia (API)** activé — c'est la source principale",
                        "✅ RSS seul ne suffit souvent pas (peu d'entrées matchent covid/vaccin)",
                    ]
                    if lang == "en":
                        tips.insert(0, "⚠️ **Langue actuelle : en** — repassez à **fr** pour covid/vaccin en français")
                    tips.append(
                        "✅ **NewsAPI** : clé gratuite sur [newsapi.org](https://newsapi.org) "
                        "(format 32 caractères, pas une clé Gemini)"
                    )
                    st.info("**Comment corriger :**\n" + "\n".join(f"- {t}" for t in tips))
                elif any("Textes trop courts" in e for e in errors):
                    st.info(
                        "**Comment corriger :** ajoutez NewsAPI ou baissez le minimum de mots "
                        "via une source avec des articles complets."
                    )

            if os.path.exists(rejected_path):
                with open(rejected_path, "r", encoding="utf-8") as f:
                    rejected_data = json.load(f)
                with st.expander(f"📋 rejected.json ({rejected_data.get('rejected_count', 0)} entrées)"):
                    st.json(rejected_data)
            
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"❌ Erreur: {str(e)}")


# ============================================================
# AFFICHAGE RÉSULTATS (AVEC ENRICHISSEMENTS)
# ============================================================
if st.session_state.dataset_result:
    result_path = st.session_state.dataset_result
    
    st.markdown("---")
    st.success("✅ Dataset créé avec succès !")
    
    try:
        data, envelope_meta = load_dataset_file(result_path)
        df = pd.DataFrame(data)

        synthetic_count = envelope_meta.get("synthetic_count", sum(
            1 for d in data if d.get("provenance", {}).get("is_synthetic")
        ))

        if synthetic_count > 0:
            st.warning(f"⚠️ Ce dataset contient {synthetic_count} document(s) synthétique(s) (mode dev).")

        run_id = envelope_meta.get("run_id", st.session_state.dataset_meta.get("run_id", "N/A"))
        st.caption(f"Run ID : `{run_id}` | Schéma : `{envelope_meta.get('schema_version', 'legacy')}`")
        
        # Métriques principales
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📄 Documents", len(data))
        with col2:
            avg_quality = envelope_meta.get("avg_quality") or (
                sum(d.get('quality_score', 0) for d in data) / len(data) if data else 0
            )
            st.metric("⭐ Qualité moyenne", f"{avg_quality:.2f}")
        with col3:
            avg_words = sum(d.get('word_count', 0) for d in data) / len(data) if data else 0
            st.metric("📝 Mots/doc", f"{avg_words:.0f}")
        with col4:
            st.metric("🎯 Thème", theme.upper())
        
        # NOUVEAU : Métriques d'enrichissement
        if data and any('category' in d for d in data):
            st.markdown("---")
            st.subheader("🧠 Enrichissements IA")
            
            col_enrich1, col_enrich2, col_enrich3 = st.columns(3)
            
            with col_enrich1:
                categories = {}
                for d in data:
                    cat = d.get('category', 'Non catégorisé')
                    categories[cat] = categories.get(cat, 0) + 1
                st.write("📊 Catégories")
                st.json(categories)
            
            with col_enrich2:
                sentiments = {}
                for d in data:
                    sent = d.get('sentiment', 'Neutre')
                    sentiments[sent] = sentiments.get(sent, 0) + 1
                st.write("😊 Sentiments")
                st.json(sentiments)
            
            with col_enrich3:
                total_qa = sum(len(d.get('qa_pairs', [])) for d in data)
                st.write("❓ Q&A générées")
                st.metric("Total", total_qa)
        
        # Onglets
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Tableau", "🔍 Aperçu", "📥 Téléchargement", "📋 Traçabilité"])
        
        with tab1:
            display_cols = ['id', 'word_count', 'quality_score', 'theme']
            if data and 'provenance' in data[0]:
                display_cols = ['id', 'word_count', 'quality_score', 'theme']
            if data and 'category' in data[0]:
                display_cols = ['id', 'word_count', 'quality_score', 'category', 'sentiment', 'theme']
            
            available_cols = [c for c in display_cols if c in df.columns]
            st.dataframe(df[available_cols].head(20), use_container_width=True, hide_index=True)
        
        with tab2:
            if len(data) > 0:
                doc_index = st.selectbox(
                    "Choisir un document",
                    range(len(data)),
                    format_func=lambda i: f"Doc {i+1} - {data[i].get('category', 'Sans catégorie')} (score: {data[i].get('quality_score', 0):.2f})"
                )
                
                doc = data[doc_index]
                
                # Résumé GPT
                if doc.get('summary'):
                    st.subheader("📝 Résumé IA")
                    st.info(doc['summary'])
                
                # Texte original
                with st.expander("📄 Texte original"):
                    st.write(doc.get('text', 'N/A'))
                
                # Entités NLP
                st.subheader("🏷️ Entités extraites (spaCy)")
                entities = doc.get('entities', [])
                if entities:
                    ent_df = pd.DataFrame(entities)
                    st.dataframe(ent_df, hide_index=True)
                else:
                    st.info("Aucune entité détectée")
                
                # Q&A GPT
                if doc.get('qa_pairs'):
                    st.subheader("❓ Questions-Réponses (GPT)")
                    for i, qa in enumerate(doc['qa_pairs']):
                        with st.expander(f"Q{i+1}: {qa.get('question', '?')}"):
                            st.write(qa.get('answer', 'Pas de réponse'))
                
                # Métadonnées
                st.subheader("📊 Métadonnées")
                meta = {
                    "id": doc.get('id'),
                    "word_count": doc.get('word_count'),
                    "quality_score": doc.get('quality_score'),
                    "theme": doc.get('theme'),
                    "category": doc.get('category', 'N/A'),
                    "sentiment": doc.get('sentiment', 'N/A'),
                    "keywords": doc.get('keywords', []),
                }
                st.json(meta)

                if doc.get("provenance"):
                    st.subheader("🔗 Provenance")
                    st.json(doc["provenance"])
        
        with tab3:
            col_dl1, col_dl2 = st.columns(2)
            
            with col_dl1:
                with open(result_path, 'rb') as f:
                    st.download_button(
                        "📥 Télécharger JSON (complet)",
                        f,
                        file_name=f"dataset_{theme}_enriched.json",
                        mime="application/json",
                        use_container_width=True
                    )
            
            csv_path = os.path.join(os.path.dirname(result_path), "dataset.csv")
            if os.path.exists(csv_path):
                with open(csv_path, 'rb') as f:
                    st.download_button(
                        "📥 Télécharger CSV (résumé)",
                        f,
                        file_name=f"dataset_{theme}_enriched.csv",
                        mime="text/csv",
                        use_container_width=True
                    )

        with tab4:
            run_dir = os.path.dirname(result_path)
            manifest_path = os.path.join(run_dir, "manifest.json")
            rejected_path = os.path.join(run_dir, "rejected.json")

            if os.path.exists(manifest_path):
                with open(manifest_path, "r", encoding="utf-8") as f:
                    st.subheader("Manifest d'exécution")
                    st.json(json.load(f))
            else:
                st.info("Manifest non disponible (dataset legacy).")

            if os.path.exists(rejected_path):
                with open(rejected_path, "r", encoding="utf-8") as f:
                    rejected_data = json.load(f)
                st.subheader(f"Documents rejetes ({rejected_data.get('rejected_count', 0)})")
                st.json(rejected_data)
        
        # Statistiques
        st.markdown("---")
        st.subheader("📈 Statistiques")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            quality_scores = [d.get('quality_score', 0) for d in data]
            chart_df = pd.DataFrame({'Qualité': quality_scores})
            st.bar_chart(chart_df)
        
        with col_chart2:
            word_counts = [d.get('word_count', 0) for d in data]
            length_df = pd.DataFrame({'Mots': word_counts})
            st.bar_chart(length_df)
            
    except Exception as e:
        st.error(f"Erreur de chargement: {e}")

else:
    st.markdown("---")
    st.info("👈 Configurez les paramètres et cliquez sur **Lancer le Pipeline**")

st.markdown("---")
st.caption("🧠 Pipeline Dataset Intelligence v3.0 | Tier 2 | Traçabilité & sources enrichies")