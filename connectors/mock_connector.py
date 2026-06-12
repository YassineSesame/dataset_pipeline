from typing import List
from .base import BaseSourceConnector, DataSourceConfig, RawDocument


class MockConnector(BaseSourceConnector):
    """Connecteur de test qui genere des donnees factices"""
    
    def connect(self) -> bool:
        return True
    
    def fetch(self, keywords: List[str]) -> List[RawDocument]:
        documents = [
            RawDocument(
                id="mock_001",
                source="mock",
                content="Le vaccin contre la grippe est un traitement preventif qui stimule le systeme immunitaire. "
                        "Il contient des antigenes qui permettent au corps de developper des anticorps specifiques. "
                        "La vaccination est recommandee chaque annee pour les populations a risque.",
                metadata={"type": "mock", "is_synthetic": True, "topic": "vaccin"}
            ),
            RawDocument(
                id="mock_002",
                source="mock",
                content="L'immunite naturelle se developpe apres une premiere exposition a un pathogene. "
                        "Le systeme immunitaire memorise l'agent infectieux et reagit plus vite lors d'une reinfection. "
                        "Cette memoire immunologique peut durer plusieurs annees voire toute la vie.",
                metadata={"type": "mock", "is_synthetic": True, "topic": "immunite"}
            ),
            RawDocument(
                id="mock_003",
                source="mock",
                content="Les maladies virales comme la grippe, la rougeole ou la COVID-19 se transmettent par contact direct. "
                        "Le traitement antiviral vise a reduire la replication du virus dans l'organisme. "
                        "La prevention reste le meilleur moyen de lutte contre ces infections.",
                metadata={"type": "mock", "is_synthetic": True, "topic": "virus"}
            ),
            RawDocument(
                id="mock_004",
                source="mock",
                content="Le traitement par antibiotiques est efficace contre les bacteries mais inefficace contre les virus. "
                        "L'antibioresistance represente un risque majeur pour la sante publique mondiale. "
                        "Les chercheurs travaillent sur de nouvelles molecules pour combattre les superbacteries.",
                metadata={"type": "mock", "is_synthetic": True, "topic": "traitement"}
            ),
            RawDocument(
                id="mock_005",
                source="mock",
                content="La recherche medicale progresse rapidement grace a l'intelligence artificielle. "
                        "Les algorithmes d'apprentissage automatique permettent de decouvrir de nouveaux medicaments. "
                        "Le diagnostic precoce des maladies grace au deep learning sauve des vies.",
                metadata={"type": "mock", "is_synthetic": True, "topic": "recherche"}
            ),
            RawDocument(
                id="mock_006",
                source="mock",
                content="Les vaccins a ARN messager representent une revolution technologique. "
                        "Ils permettent de developper des vaccins en quelques mois au lieu de plusieurs annees. "
                        "La technologie pourrait etre utilisee contre le cancer et d'autres maladies chroniques.",
                metadata={"type": "mock", "is_synthetic": True, "topic": "vaccin_arn"}
            ),
            RawDocument(
                id="mock_007",
                source="mock",
                content="L'hygiene des mains est la mesure preventive la plus efficace contre les infections nosocomiales. "
                        "Le lavage a l'eau et au savon pendant 30 secondes elimine la majorite des pathogenes. "
                        "Les solutions hydroalcooliques sont une alternative pratique en milieu hospitalier.",
                metadata={"type": "mock", "is_synthetic": True, "topic": "prevention"}
            ),
            RawDocument(
                id="mock_008",
                source="mock",
                content="Les maladies chroniques comme le diabete et l'hypertension necessitent un suivi medical regulier. "
                        "Le depistage precoce permet d'eviter les complications graves. "
                        "L'education therapeutique du patient ameliore l'observance du traitement.",
                metadata={"type": "mock", "is_synthetic": True, "topic": "chronique"}
            )
        ]
        
        print(f"   MOCK : {len(documents)} documents generes")
        return documents