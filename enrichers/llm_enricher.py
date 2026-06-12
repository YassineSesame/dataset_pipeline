import json
import os
from typing import Dict, List

from openai import OpenAI
import google.generativeai as genai

from configs.theme_categories import get_theme_categories


class LLMEnricher:
    """Enrichit les documents avec différentes solutions d'IA (Gemini, Ollama, OpenAI)"""
    
    def __init__(self, provider: str = "gemini", api_key: str = None, model: str = None):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model_name = model
        
        print(f"   [IA] Initialisation du moteur enrichisseur: {self.provider.upper()}")
        
        if self.provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError("Clé OpenAI manquante. Fournissez-la ou définissez la variable d'environnement OPENAI_API_KEY.")
            self.client = OpenAI(api_key=self.api_key)
            self.model_name = self.model_name or "gpt-4o-mini"
            print(f"   [IA] Modèle OpenAI sélectionné : {self.model_name}")
            
        elif self.provider == "ollama":
            # Ollama expose une API compatible OpenAI en local sur le port 11434
            self.client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama"  # Valeur bidon requise pour passer l'initialisation du client
            )
            self.model_name = self.model_name or "qwen2.5:3b"
            print(f"   [IA] Modèle Ollama local sélectionné : {self.model_name}")
            
        elif self.provider == "gemini":
            self.api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError("Clé Gemini manquante. Fournissez-la dans l'interface ou définissez la variable d'environnement GEMINI_API_KEY.")
            genai.configure(api_key=self.api_key)
            self.model_name = self.model_name or "gemini-1.5-flash"
            print(f"   [IA] Modèle Gemini sélectionné : {self.model_name}")
            
        else:
            raise ValueError(f"Fournisseur d'IA '{self.provider}' non supporté.")
    
    def enrich(self, text: str, theme: str = "général") -> Dict:
        """
        Enrichit un texte avec :
        - Résumé
        - Catégorie thématique
        - Sentiment
        - Mots-clés
        - Questions-réponses
        """
        
        categories = get_theme_categories(theme)
        categories_str = ", ".join(categories)

        prompt = f"""Analyse ce texte sur le thème "{theme}" et retourne UNIQUEMENT un JSON valide avec cette structure exacte :

{{
    "summary": "Résumé en 1 seule phrase courte et concise",
    "category": "Une catégorie parmi: {categories_str}",
    "sentiment": "Positif, Négatif ou Neutre",
    "keywords": ["mot1", "mot2", "mot3"],
    "qa_pairs": [
        {{"question": "Question courte ?", "answer": "Réponse courte"}}
    ]
}}

Texte à analyser :
{text[:3000]}
"""
        
        try:
            content = ""
            
            if self.provider == "gemini":
                model = genai.GenerativeModel(self.model_name)
                # Utilise le format de réponse JSON natif de Gemini pour garantir la validité du format
                response = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"}
                )
                content = response.text
                
            elif self.provider in ["openai", "ollama"]:
                extra_args = {}
                # Si Ollama ou OpenAI supportent le JSON structuré
                if self.provider == "openai" or self.provider == "ollama":
                    extra_args["response_format"] = {"type": "json_object"}
                
                # Timeout encore plus élevé pour Ollama local (120 secondes) vs Cloud (30 secondes)
                api_timeout = 120 if self.provider == "ollama" else 30
                    
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "Tu es un expert en analyse de texte. Tu réponds UNIQUEMENT en JSON valide."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=300,  # Réduit de 800 à 300 pour stopper le modèle plus tôt et accélérer l'inférence
                    timeout=api_timeout,
                    **extra_args
                )
                content = response.choices[0].message.content
            
            # Nettoyage classique au cas où l'un des modèles ajoute des blocs de code markdown ```json
            content = content.strip()
            if content.startswith("```json"):
                content = content[7:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()
            
            result = json.loads(content)
            return result
            
        except Exception as e:
            # Lever l'exception pour que la boucle d'exécution la capture
            raise RuntimeError(f"Erreur d'enrichissement ({self.provider}): {str(e)}")
    
    def enrich_batch(self, documents: List[Dict], theme: str = "général", max_workers: int = None, status_callback=None) -> List[Dict]:
        """Enrichit une liste de documents"""
        if max_workers is None:
            max_workers = 1 if self.provider == "ollama" else 5
            
        total = len(documents)
        
        # -------------------------------------------------------------
        # OPTION A : Mode synchrone séquentiel pur (Recommandé pour Ollama local)
        # -------------------------------------------------------------
        if max_workers == 1:
            msg = f"Démarrage de l'enrichissement de {total} documents en mode séquentiel pur (Ollama local)..."
            print(f"   [IA] {msg}")
            if status_callback:
                status_callback(msg)
                
            enriched = []
            for i, doc in enumerate(documents):
                msg = f"Enrichissement du document {i+1}/{total}..."
                print(f"   [IA] {msg}")
                if status_callback:
                    status_callback(msg)
                
                try:
                    enrichment = self.enrich(doc.get("text", ""), theme)
                    cat = enrichment.get('category', 'Non catégorisé')
                    msg = f"Document {i+1}/{total} - Succès ({cat})"
                    print(f"   ✓ {msg}")
                    if status_callback:
                        status_callback(msg)
                        
                    doc_enriched = {
                        **doc,
                        "summary": enrichment.get("summary", "Résumé non disponible"),
                        "category": enrichment.get("category", "Non catégorisé"),
                        "sentiment": enrichment.get("sentiment", "Neutre"),
                        "keywords": enrichment.get("keywords", []),
                        "qa_pairs": enrichment.get("qa_pairs", [])
                    }
                except Exception as e:
                    msg = f"Document {i+1}/{total} - Échec : {e}"
                    print(f"   ! {msg}")
                    if status_callback:
                        status_callback(msg)
                        
                    doc_enriched = {
                        **doc,
                        "summary": "Résumé non disponible (erreur d'enrichissement)",
                        "category": "Non catégorisé",
                        "sentiment": "Neutre",
                        "keywords": [],
                        "qa_pairs": []
                    }
                enriched.append(doc_enriched)
            return enriched
            
        # -------------------------------------------------------------
        # OPTION B : Mode multithread parallèle (Recommandé pour Gemini / Cloud)
        # -------------------------------------------------------------
        from concurrent.futures import ThreadPoolExecutor, as_completed
        enriched = [None] * total
        
        msg = f"Démarrage de l'enrichissement de {total} documents en mode parallèle ({max_workers} threads)..."
        print(f"   [IA] {msg}")
        if status_callback:
            status_callback(msg)
            
        def enrich_single(index, doc):
            try:
                result = self.enrich(doc.get("text", ""), theme)
                return index, result, None
            except Exception as e:
                return index, None, str(e)

        completed_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(enrich_single, i, doc) for i, doc in enumerate(documents)]
            
            for future in as_completed(futures):
                index, enrichment, error = future.result()
                completed_count += 1
                
                doc = documents[index]
                if error:
                    msg = f"Document {index+1}/{total} - Échec : {error}"
                    print(f"   ! {msg}")
                    if status_callback:
                        status_callback(msg)
                    
                    doc_enriched = {
                        **doc,
                        "summary": "Résumé non disponible (erreur d'enrichissement)",
                        "category": "Non catégorisé",
                        "sentiment": "Neutre",
                        "keywords": [],
                        "qa_pairs": []
                    }
                else:
                    cat = enrichment.get('category', 'Non catégorisé')
                    msg = f"Document {index+1}/{total} - Succès ({cat})"
                    print(f"   ✓ {msg}")
                    if status_callback:
                        status_callback(msg)
                        
                    doc_enriched = {
                        **doc,
                        "summary": enrichment.get("summary", "Résumé non disponible"),
                        "category": enrichment.get("category", "Non catégorisé"),
                        "sentiment": enrichment.get("sentiment", "Neutre"),
                        "keywords": enrichment.get("keywords", []),
                        "qa_pairs": enrichment.get("qa_pairs", [])
                    }
                
                enriched[index] = doc_enriched
        
        return enriched