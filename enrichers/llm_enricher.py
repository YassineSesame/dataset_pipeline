import json
import os
from typing import Dict, List

from openai import OpenAI
import google.generativeai as genai

from configs.theme_categories import get_theme_categories, GEMINI_MODELS


class LLMEnricher:
    """Enrichit les documents avec Gemini, Ollama ou OpenAI."""

    def __init__(self, provider: str = "gemini", api_key: str = None, model: str = None):
        self.provider = provider.lower()
        self.api_key = api_key
        self.model_name = model
        self.last_batch_stats: Dict = {}
        self.init_error: str = ""

        print(f"   [IA] Initialisation du moteur enrichisseur: {self.provider.upper()}")

        if self.provider == "openai":
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "Cle OpenAI manquante. Definissez OPENAI_API_KEY ou fournissez-la dans l'interface."
                )
            self.client = OpenAI(api_key=self.api_key)
            self.model_name = self.model_name or "gpt-4o-mini"
            print(f"   [IA] Modele OpenAI selectionne : {self.model_name}")

        elif self.provider == "ollama":
            self.client = OpenAI(
                base_url="http://localhost:11434/v1",
                api_key="ollama",
            )
            self.model_name = self.model_name or "qwen2.5:3b"
            print(f"   [IA] Modele Ollama local selectionne : {self.model_name}")

        elif self.provider == "gemini":
            self.api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not self.api_key:
                raise ValueError(
                    "Cle Gemini manquante. Definissez GEMINI_API_KEY ou fournissez-la dans l'interface."
                )
            genai.configure(api_key=self.api_key)
            requested = self.model_name or GEMINI_MODELS[0]
            if requested not in GEMINI_MODELS:
                print(f"   ! Modele '{requested}' inconnu — utilisation de {GEMINI_MODELS[0]}")
                requested = GEMINI_MODELS[0]
            self.model_name = requested
            print(f"   [IA] Modele Gemini selectionne : {self.model_name}")

        else:
            raise ValueError(f"Fournisseur d'IA '{self.provider}' non supporte.")

    def enrich(self, text: str, theme: str = "general") -> Dict:
        categories = get_theme_categories(theme)
        categories_str = ", ".join(categories)

        prompt = f"""Analyse ce texte sur le theme "{theme}" et retourne UNIQUEMENT un JSON valide :

{{
    "summary": "Resume en 1 seule phrase courte",
    "category": "Une categorie parmi: {categories_str}",
    "sentiment": "Positif, Negatif ou Neutre",
    "keywords": ["mot1", "mot2", "mot3"],
    "qa_pairs": [
        {{"question": "Question courte ?", "answer": "Reponse courte"}}
    ]
}}

Texte :
{text[:3000]}
"""

        if self.provider == "gemini":
            return self._enrich_gemini(prompt)
        return self._enrich_openai_compatible(prompt)

    def _enrich_gemini(self, prompt: str) -> Dict:
        models_to_try = [self.model_name] + [m for m in GEMINI_MODELS if m != self.model_name]
        last_error = None

        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                response = model.generate_content(
                    prompt,
                    generation_config={"response_mime_type": "application/json"},
                )
                result = self._parse_json_response(response.text)
                self.model_name = model_name
                return result
            except Exception as e:
                last_error = str(e)
                if "404" in last_error or "not found" in last_error.lower():
                    print(f"   ! Modele {model_name} indisponible, essai suivant...")
                    continue
                raise RuntimeError(f"Erreur d'enrichissement (gemini/{model_name}): {last_error}") from e

        raise RuntimeError(
            f"Erreur d'enrichissement (gemini): aucun modele disponible. "
            f"Derniere erreur: {last_error}. Modeles testes: {models_to_try}"
        )

    def _enrich_openai_compatible(self, prompt: str) -> Dict:
        extra_args = {"response_format": {"type": "json_object"}}
        api_timeout = 120 if self.provider == "ollama" else 30

        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[
                {
                    "role": "system",
                    "content": "Tu es un expert en analyse de texte. Reponds UNIQUEMENT en JSON valide.",
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=400,
            timeout=api_timeout,
            **extra_args,
        )
        return self._parse_json_response(response.choices[0].message.content)

    def _parse_json_response(self, content: str) -> Dict:
        content = (content or "").strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        return json.loads(content)

    def _apply_enrichment(self, doc: Dict, enrichment: Dict) -> Dict:
        return {
            **doc,
            "summary": enrichment.get("summary", "Resume non disponible"),
            "category": enrichment.get("category", "Non categorise"),
            "sentiment": enrichment.get("sentiment", "Neutre"),
            "keywords": enrichment.get("keywords", []),
            "qa_pairs": enrichment.get("qa_pairs", []),
            "enrichment_status": "success",
            "enrichment_error": None,
        }

    def _apply_enrichment_failure(self, doc: Dict, error: str) -> Dict:
        return {
            **doc,
            "summary": "",
            "category": "Non categorise",
            "sentiment": "Neutre",
            "keywords": [],
            "qa_pairs": [],
            "enrichment_status": "failed",
            "enrichment_error": error[:500],
        }

    def enrich_batch(
        self,
        documents: List[Dict],
        theme: str = "general",
        max_workers: int = None,
        status_callback=None,
    ) -> List[Dict]:
        if max_workers is None:
            max_workers = 1 if self.provider == "ollama" else 5

        total = len(documents)
        success_count = 0
        failed_count = 0
        errors_log: List[dict] = []

        if max_workers == 1:
            enriched = []
            for i, doc in enumerate(documents):
                msg = f"Enrichissement du document {i + 1}/{total}..."
                print(f"   [IA] {msg}")
                if status_callback:
                    status_callback(msg)

                try:
                    enrichment = self.enrich(doc.get("text", ""), theme)
                    doc_enriched = self._apply_enrichment(doc, enrichment)
                    success_count += 1
                    cat = enrichment.get("category", "Non categorise")
                    print(f"   ✓ Document {i + 1}/{total} - Succes ({cat})")
                except Exception as e:
                    error_msg = str(e)
                    doc_enriched = self._apply_enrichment_failure(doc, error_msg)
                    failed_count += 1
                    errors_log.append({"document_index": i + 1, "id": doc.get("id"), "error": error_msg[:300]})
                    print(f"   ! Document {i + 1}/{total} - Echec : {error_msg}")
                    if status_callback:
                        status_callback(f"Document {i + 1}/{total} - Echec")

                enriched.append(doc_enriched)
        else:
            from concurrent.futures import ThreadPoolExecutor, as_completed

            enriched = [None] * total
            print(f"   [IA] Enrichissement parallele ({max_workers} threads) de {total} documents...")

            def enrich_single(index, doc):
                try:
                    result = self.enrich(doc.get("text", ""), theme)
                    return index, result, None
                except Exception as e:
                    return index, None, str(e)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(enrich_single, i, doc) for i, doc in enumerate(documents)]

                for future in as_completed(futures):
                    index, enrichment, error = future.result()
                    doc = documents[index]

                    if error:
                        enriched[index] = self._apply_enrichment_failure(doc, error)
                        failed_count += 1
                        errors_log.append({"document_index": index + 1, "id": doc.get("id"), "error": error[:300]})
                        print(f"   ! Document {index + 1}/{total} - Echec : {error}")
                    else:
                        enriched[index] = self._apply_enrichment(doc, enrichment)
                        success_count += 1
                        cat = enrichment.get("category", "Non categorise")
                        print(f"   ✓ Document {index + 1}/{total} - Succes ({cat})")

        self.last_batch_stats = {
            "requested": total,
            "success": success_count,
            "failed": failed_count,
            "model": self.model_name,
            "provider": self.provider,
            "errors": errors_log[:10],
        }
        return enriched
