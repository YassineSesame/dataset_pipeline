import json
import os
import uuid
import pandas as pd
from datetime import datetime
from typing import List, Optional, Tuple

from connectors.web_scraper import WebScraperConnector
from connectors.wikipedia_api_connector import WikipediaAPIConnector
from connectors.rss_connector import RSSConnector
from connectors.news_api_connector import NewsAPIConnector
from connectors.mock_connector import MockConnector
from processors.nlp_processor import ProcessedDocument
from processors.nlp_processor import NLPProcessor
from validators.quality_validator import QualityValidator
from enrichers.llm_enricher import LLMEnricher
from utils.deduplication import deduplicate_documents
from utils.provenance import build_provenance
from utils.relevance import filter_raw_documents

SCHEMA_VERSION = "1.2"


class DatasetPipeline:
    def __init__(
        self,
        config,
        ai_provider: str = "none",
        ai_key: str = None,
        ai_model: str = None,
        max_enrich_docs: int = 10,
    ):
        self.config = config
        self.processor = NLPProcessor(language=config.language)
        self.validator = QualityValidator(
            min_documents=config.min_documents,
            min_avg_quality=config.min_avg_quality,
            min_avg_length=config.min_avg_length,
            min_avg_relevance=getattr(config, "min_avg_relevance", 0.12),
        )
        self.ai_provider = ai_provider or "none"
        self.ai_key = ai_key
        self.ai_model = ai_model
        self.max_enrich_docs = max_enrich_docs
        self.enricher = None
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:8]
        self.run_dir = os.path.join("data", "runs", self.run_id)
        self.started_at = datetime.now()
        self.rejected_records: List[dict] = []
        self.run_stats = {}
        self.source_counts: dict = {}
        self.pipeline_flow: dict = {}

        if self.ai_provider.lower() != "none":
            try:
                self.enricher = LLMEnricher(
                    provider=self.ai_provider, api_key=self.ai_key, model=self.ai_model
                )
                print(f"   ✓ Enrichisseur IA ({self.ai_provider}) initialise")
            except Exception as e:
                print(f"   ! Impossible d'initialiser l'enrichisseur IA ({self.ai_provider}): {e}")

    def run(self, status_callback=None) -> Optional[str]:
        print(f"\n{'='*50}")
        print(f"DEMARRAGE DU PIPELINE : {self.config.theme.upper()}")
        print(f"Run ID : {self.run_id}")
        print(f"{'='*50}")

        os.makedirs(self.run_dir, exist_ok=True)

        msg_collecte = "\n[1/5] Collecte des donnees..."
        print(msg_collecte)
        if status_callback:
            status_callback(msg_collecte)

        raw_docs = self._collect_data()
        if self.config.uploaded_documents:
            raw_docs.extend(self.config.uploaded_documents)
            print(f"   -> +{len(self.config.uploaded_documents)} document(s) importe(s)")
        raw_count = len(raw_docs)
        self.pipeline_flow["raw_collected"] = raw_count
        print(f"   -> {raw_count} documents bruts trouves")

        if raw_count < self.config.min_documents:
            if self.config.allow_mock_fallback:
                print(f"\n   ! Seulement {raw_count} documents reels")
                print("   ! Mode dev : ajout de donnees SYNTHETIQUES (is_synthetic=true)")
                mock = MockConnector(config=None)
                mock_docs = mock.fetch(self.config.keywords)
                raw_docs.extend(mock_docs)
                print(f"   -> Total apres mock : {len(raw_docs)} documents")
            else:
                self._record_rejection(
                    stage="collect",
                    reason="insufficient_real_documents",
                    details={
                        "found": raw_count,
                        "required": self.config.min_documents,
                        "source_counts": self.source_counts,
                        "language": self.config.language,
                        "hint": (
                            "Verifiez : Langue=fr, cochez 'Forcer le rechargement', "
                            "cle NewsAPI valide (newsapi.org), ou reduisez Documents minimum."
                        ),
                    },
                )
                self._finalize_failed_run(
                    [f"Documents reels insuffisants ({raw_count}/{self.config.min_documents})"],
                    status_callback,
                )
                return None

        msg_dedup = "\n[1b/5] Deduplication..."
        print(msg_dedup)
        if status_callback:
            status_callback(msg_dedup)

        raw_docs, duplicate_rejects = deduplicate_documents(raw_docs, content_attr="content")
        self.rejected_records.extend(duplicate_rejects)
        self.pipeline_flow["after_dedup"] = len(raw_docs)
        print(f"   -> {len(raw_docs)} documents uniques ({len(duplicate_rejects)} doublons supprimes)")

        msg_rel = "\n[1c/5] Filtrage pertinence et langue..."
        print(msg_rel)
        if status_callback:
            status_callback(msg_rel)

        raw_docs, relevance_rejects = filter_raw_documents(
            raw_docs,
            keywords=self.config.keywords,
            theme=self.config.theme,
            expected_language=self.config.language,
            min_keyword_matches=self.config.min_keyword_matches,
            min_relevance_score=self.config.min_relevance_score,
            strict_news=getattr(self.config, "strict_news_relevance", True),
        )
        self.rejected_records.extend(relevance_rejects)
        self.pipeline_flow["after_relevance"] = len(raw_docs)
        self.pipeline_flow["relevance_rejected"] = len(relevance_rejects)
        print(
            f"   -> {len(raw_docs)} documents pertinents "
            f"({len(relevance_rejects)} rejetes par pertinence/langue)"
        )

        if len(raw_docs) < self.config.min_documents:
            self._record_rejection(
                stage="relevance_filter",
                reason="insufficient_documents_after_filter",
                details={"found": len(raw_docs), "required": self.config.min_documents},
            )
            self._finalize_failed_run(
                [f"Documents insuffisants apres filtrage: {len(raw_docs)}"],
                status_callback,
            )
            return None

        msg_nlp = "\n[2/5] Traitement NLP..."
        print(msg_nlp)
        if status_callback:
            status_callback(msg_nlp)

        processed_docs, processing_rejects = self._process_documents(raw_docs)
        self.rejected_records.extend(processing_rejects)
        self.pipeline_flow["after_nlp"] = len(processed_docs)
        self.pipeline_flow["nlp_rejected"] = len(processing_rejects)
        print(f"   -> {len(processed_docs)} documents retenus ({len(processing_rejects)} rejetes au filtre)")

        msg_val = "\n[3/5] Validation qualite..."
        print(msg_val)
        if status_callback:
            status_callback(msg_val)

        is_valid, errors = self.validator.validate(processed_docs)
        if not is_valid:
            print("   ! Validation echouee :")
            for error in errors:
                print(f"      - {error}")
            self._record_rejection(
                stage="validate",
                reason="dataset_validation_failed",
                details={"errors": errors},
            )
            self._finalize_failed_run(errors, status_callback, processed_docs=processed_docs)
            return None

        print("   -> Dataset valide !")

        enriched_records = self._enrich_documents(processed_docs, status_callback)
        output_path = self._export(enriched_records, validation_errors=[])

        print(f"\n{'='*50}")
        print("✅ PIPELINE TERMINE AVEC SUCCES !")
        print(f"{'='*50}")

        return output_path

    def _collect_data(self) -> List:
        all_docs = []
        self.source_counts = {}

        for source_config in self.config.sources:
            source_type = source_config["type"]
            identifier = source_config["identifier"]
            cfg = type("Config", (), source_config)()
            docs = []

            if source_type == "wikipedia_api":
                connector = WikipediaAPIConnector(
                    config=cfg,
                    language=self.config.language,
                    max_pages=source_config.get("max_pages", self.config.wiki_max_pages),
                    max_docs=self.config.max_docs_per_source,
                    force_refresh=self.config.force_refresh,
                    cache_ttl_hours=self.config.cache_ttl_hours_web,
                )
                if connector.connect():
                    docs = connector.fetch(self.config.keywords)
                    all_docs.extend(docs)
                    print(f"   ✓ {identifier} (API) : {len(docs)} docs")
                else:
                    print(f"   ✗ {identifier} (API) : inaccessible")

            elif source_type == "web":
                connector = WebScraperConnector(
                    config=cfg,
                    max_docs=self.config.max_docs_per_source,
                    force_refresh=self.config.force_refresh,
                    cache_ttl_hours=self.config.cache_ttl_hours_web,
                )
                if connector.connect():
                    docs = connector.fetch(self.config.keywords)
                    all_docs.extend(docs)
                    print(f"   ✓ {identifier} : {len(docs)} docs")
                else:
                    print(f"   ✗ {identifier} : inaccessible")

            elif source_type == "rss":
                connector = RSSConnector(
                    config=cfg,
                    max_entries=self.config.max_docs_per_source,
                    force_refresh=self.config.force_refresh,
                    cache_ttl_hours=self.config.cache_ttl_hours_rss,
                )
                if connector.connect():
                    docs = connector.fetch(self.config.keywords)
                    all_docs.extend(docs)
                    print(f"   ✓ {identifier} (RSS) : {len(docs)} docs")
                else:
                    print(f"   ✗ {identifier} (RSS) : URL manquante")

            elif source_type == "api_news":
                connector = NewsAPIConnector(
                    config=cfg,
                    extract_full_articles=self.config.extract_full_articles,
                    max_articles=self.config.max_docs_per_source,
                    force_refresh=self.config.force_refresh,
                    cache_ttl_hours=self.config.cache_ttl_hours_news,
                    language=self.config.language,
                )
                if connector.connect():
                    docs = connector.fetch(self.config.keywords)
                    all_docs.extend(docs)
                    print(f"   ✓ {identifier} : {len(docs)} docs")
                else:
                    print(f"   ✗ {identifier} : connexion impossible")

            self.source_counts[identifier] = len(docs)

        return all_docs

    def _process_documents(self, raw_docs: List) -> Tuple[List[ProcessedDocument], List[dict]]:
        processed = []
        rejected = []

        for doc in raw_docs:
            try:
                proc = self.processor.process(doc, self.config.keywords, self.config.theme)
                min_rel = getattr(self.config, "min_relevance", 0.12)

                if proc.relevance_score < min_rel:
                    rejected.append(
                        {
                            "id": doc.id,
                            "stage": "nlp_filter",
                            "reason": "relevance_below_threshold",
                            "relevance_score": proc.relevance_score,
                            "threshold": min_rel,
                            "quality_score": round(proc.quality_score, 4),
                            "source": doc.source,
                            "is_synthetic": proc.is_synthetic,
                        }
                    )
                elif proc.quality_score >= self.config.min_quality:
                    processed.append(proc)
                else:
                    rejected.append(
                        {
                            "id": doc.id,
                            "stage": "nlp_filter",
                            "reason": "quality_below_threshold",
                            "quality_score": round(proc.quality_score, 4),
                            "relevance_score": proc.relevance_score,
                            "threshold": self.config.min_quality,
                            "source": doc.source,
                            "is_synthetic": proc.is_synthetic,
                        }
                    )
            except Exception as e:
                rejected.append(
                    {
                        "id": doc.id,
                        "stage": "nlp_filter",
                        "reason": "processing_error",
                        "error": str(e),
                        "source": doc.source,
                    }
                )
                print(f"   ! Erreur sur {doc.id}: {e}")

        return processed, rejected

    def _build_base_record(self, doc: ProcessedDocument) -> dict:
        provenance = build_provenance(
            source_id=doc.source,
            metadata=doc.metadata,
            keywords=self.config.keywords,
            text=doc.cleaned_text,
            collected_at=doc.collected_at,
            pipeline_run_id=self.run_id,
            is_synthetic=doc.is_synthetic,
        )
        return {
            "id": doc.id,
            "text": doc.cleaned_text,
            "word_count": doc.word_count,
            "entities": doc.entities,
            "quality_score": doc.quality_score,
            "relevance_score": doc.relevance_score,
            "keywords_matched": doc.keywords_matched,
            "theme": self.config.theme,
            "provenance": provenance,
            "summary": "",
            "category": "Non catégorisé",
            "sentiment": "Neutre",
            "keywords": [],
            "qa_pairs": [],
        }

    def _enrich_documents(self, processed_docs: List[ProcessedDocument], status_callback=None) -> List[dict]:
        if self.enricher and len(processed_docs) > 0:
            sorted_docs = sorted(
                processed_docs,
                key=lambda d: (d.relevance_score, d.quality_score),
                reverse=True,
            )
            to_enrich = sorted_docs[: self.max_enrich_docs]
            skipped = sorted_docs[self.max_enrich_docs :]

            msg = (
                f"\n[4/5] Enrichissement IA ({self.ai_provider.upper()}) sur "
                f"les {len(to_enrich)} meilleurs documents (sur {len(processed_docs)} au total)..."
            )
            print(msg)
            if status_callback:
                status_callback(msg)

            records = [self._build_base_record(doc) for doc in to_enrich]
            enriched_records = self.enricher.enrich_batch(
                records, self.config.theme, status_callback=status_callback
            )
            enrichment_stats = getattr(self.enricher, "last_batch_stats", {})
            self.run_stats["enrichment"] = enrichment_stats
            print(
                f"   -> Enrichissement : {enrichment_stats.get('success', 0)} succes, "
                f"{enrichment_stats.get('failed', 0)} echecs "
                f"(modele: {enrichment_stats.get('model', 'N/A')})"
            )

            for doc in skipped:
                record = self._build_base_record(doc)
                record.update(
                    {
                        "summary": "Non enrichi (limite de documents atteinte)",
                        "category": "Non catégorisé",
                        "sentiment": "Neutre",
                        "keywords": [],
                        "qa_pairs": [],
                        "enrichment_status": "skipped",
                        "enrichment_error": None,
                    }
                )
                enriched_records.append(record)

            return enriched_records

        msg = "\n[4/5] Enrichissement IA (SKIP - pas de moteur ou pas de documents)"
        print(msg)
        if status_callback:
            status_callback(msg)

        return [
            {**self._build_base_record(doc), "enrichment_status": "disabled", "enrichment_error": None}
            for doc in processed_docs
        ]

    def _export(self, documents: List[dict], validation_errors: List[str]) -> str:
        print("\n[5/5] Export...")

        synthetic_count = sum(1 for d in documents if d.get("provenance", {}).get("is_synthetic"))
        avg_quality = (
            sum(d.get("quality_score", 0) for d in documents) / len(documents) if documents else 0
        )
        avg_relevance = (
            sum(d.get("relevance_score", 0) for d in documents) / len(documents) if documents else 0
        )

        envelope = {
            "schema_version": SCHEMA_VERSION,
            "run_id": self.run_id,
            "created_at": datetime.now().isoformat(),
            "theme": self.config.theme,
            "document_count": len(documents),
            "synthetic_count": synthetic_count,
            "avg_quality": round(avg_quality, 4),
            "avg_relevance": round(avg_relevance, 4),
            "documents": documents,
        }

        json_path = os.path.join(self.run_dir, "dataset.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(envelope, f, ensure_ascii=False, indent=2)

        csv_records = []
        for doc in documents:
            prov = doc.get("provenance", {})
            csv_records.append(
                {
                    "id": doc.get("id"),
                    "text": doc.get("text", "")[:500] + "...",
                    "word_count": doc.get("word_count"),
                    "quality_score": doc.get("quality_score"),
                    "relevance_score": doc.get("relevance_score"),
                    "theme": doc.get("theme"),
                    "source_type": prov.get("source_type"),
                    "source_url": prov.get("source_url"),
                    "is_synthetic": prov.get("is_synthetic"),
                    "summary": doc.get("summary", ""),
                    "category": doc.get("category", ""),
                    "sentiment": doc.get("sentiment", ""),
                    "keywords": ", ".join(doc.get("keywords", [])),
                    "qa_count": len(doc.get("qa_pairs", [])),
                }
            )

        csv_path = os.path.join(self.run_dir, "dataset.csv")
        pd.DataFrame(csv_records).to_csv(csv_path, index=False, encoding="utf-8")

        self.run_stats = {
            "documents_exported": len(documents),
            "synthetic_documents": synthetic_count,
            "rejected_total": len(self.rejected_records),
            "avg_quality": round(avg_quality, 4),
            "avg_relevance": round(avg_relevance, 4),
            "pipeline_flow": self.pipeline_flow,
            "source_counts": self.source_counts,
        }

        self._write_rejected_report()
        self._write_manifest(
            status="success",
            validation_errors=validation_errors,
            output_files={"dataset_json": json_path, "dataset_csv": csv_path},
        )

        categories = {}
        sentiments = {}
        for doc in documents:
            cat = doc.get("category", "Non catégorisé")
            categories[cat] = categories.get(cat, 0) + 1
            sent = doc.get("sentiment", "Neutre")
            sentiments[sent] = sentiments.get(sent, 0) + 1

        print(f"\n   📊 APERCU DU DATASET :")
        print(f"      - {len(documents)} documents ({synthetic_count} synthetiques)")
        print(f"      - Qualite moyenne: {avg_quality:.2f}")
        print(f"      - Pertinence moyenne: {avg_relevance:.2f}")
        print(f"      - Categories: {categories}")
        print(f"      - Sentiments: {sentiments}")
        print(f"      - Manifest : {os.path.join(self.run_dir, 'manifest.json')}")
        print(f"   -> Sauvegarde dans : {json_path}")

        return json_path

    def _record_rejection(self, stage: str, reason: str, details: dict = None):
        self.rejected_records.append(
            {
                "stage": stage,
                "reason": reason,
                "details": details or {},
                "timestamp": datetime.now().isoformat(),
            }
        )

    def _write_rejected_report(self):
        rejected_path = os.path.join(self.run_dir, "rejected.json")
        with open(rejected_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "run_id": self.run_id,
                    "rejected_count": len(self.rejected_records),
                    "records": self.rejected_records,
                },
                f,
                ensure_ascii=False,
                indent=2,
            )

    def _sanitize_sources(self, sources: List[dict]) -> List[dict]:
        sanitized = []
        for source in sources:
            copy = dict(source)
            if copy.get("api_key"):
                copy["api_key"] = "***"
            sanitized.append(copy)
        return sanitized

    def _write_manifest(
        self,
        status: str,
        validation_errors: List[str],
        output_files: dict = None,
        processed_docs: List[ProcessedDocument] = None,
    ):
        processed_docs = processed_docs or []
        manifest = {
            "run_id": self.run_id,
            "status": status,
            "started_at": self.started_at.isoformat(),
            "completed_at": datetime.now().isoformat(),
            "theme": self.config.theme,
            "keywords": self.config.keywords,
            "sources": self._sanitize_sources(self.config.sources),
            "config": {
                "language": self.config.language,
                "min_quality": self.config.min_quality,
                "min_relevance": getattr(self.config, "min_relevance", 0.12),
                "min_avg_quality": self.config.min_avg_quality,
                "min_avg_relevance": getattr(self.config, "min_avg_relevance", 0.12),
                "min_documents": self.config.min_documents,
                "min_avg_length": self.config.min_avg_length,
                "allow_mock_fallback": self.config.allow_mock_fallback,
                "force_refresh": self.config.force_refresh,
                "max_docs_per_source": self.config.max_docs_per_source,
                "wiki_max_pages": self.config.wiki_max_pages,
                "extract_full_articles": self.config.extract_full_articles,
                "min_keyword_matches": self.config.min_keyword_matches,
                "min_relevance_score": self.config.min_relevance_score,
                "strict_news_relevance": getattr(self.config, "strict_news_relevance", True),
            },
            "stats": self.run_stats,
            "pipeline_flow": self.pipeline_flow,
            "validation": {"passed": status == "success", "errors": validation_errors},
            "output_files": output_files or {},
            "rejected_report": os.path.join(self.run_dir, "rejected.json"),
        }

        manifest_path = os.path.join(self.run_dir, "manifest.json")
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)

    def _finalize_failed_run(
        self,
        errors: List[str],
        status_callback=None,
        processed_docs: List[ProcessedDocument] = None,
    ):
        self.run_stats = {
            "documents_exported": 0,
            "rejected_total": len(self.rejected_records),
            "processed_before_failure": len(processed_docs or []),
            "pipeline_flow": self.pipeline_flow,
            "source_counts": self.source_counts,
        }
        self._write_rejected_report()
        self._write_manifest(
            status="failed",
            validation_errors=errors,
            processed_docs=processed_docs,
        )
        rejected_path = os.path.join(self.run_dir, "rejected.json")
        print(f"\n   📋 Rapport de rejets : {rejected_path}")
        print(f"   📋 Manifest d'execution : {os.path.join(self.run_dir, 'manifest.json')}")
        if status_callback:
            status_callback("Pipeline echoue — consultez rejected.json et manifest.json")
