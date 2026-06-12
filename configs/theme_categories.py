THEME_CATEGORIES = {
    "sante": [
        "Prévention",
        "Traitement",
        "Recherche",
        "Politique",
        "Économie",
        "Social",
    ],
    "education": [
        "Pédagogie",
        "Politique éducative",
        "Recherche",
        "Formation professionnelle",
        "Technologie éducative",
        "Social",
    ],
    "finance": [
        "Marchés",
        "Investissement",
        "Régulation",
        "Crypto",
        "Économie",
        "Entreprises",
    ],
    "technologie": [
        "Intelligence artificielle",
        "Innovation",
        "Cybersécurité",
        "Politique",
        "Économie",
        "Recherche",
    ],
    "environnement": [
        "Climat",
        "Énergie",
        "Biodiversité",
        "Politique",
        "Économie",
        "Recherche",
    ],
    "custom": [
        "Général",
        "Recherche",
        "Politique",
        "Économie",
        "Social",
        "Technologie",
    ],
}

# Termes « noyau » par thème — au moins un doit apparaître (sauf mock/upload)
THEME_CORE_TERMS = {
    "sante": [
        "santé", "sante", "médical", "medical", "maladie", "vaccin", "vaccination",
        "covid", "coronavirus", "virus", "traitement", "immunisation", "immunization",
        "patient", "hopital", "hôpital", "epidemie", "épidémie",
    ],
    "education": [
        "éducation", "education", "école", "ecole", "enseignement", "formation",
        "pédagogie", "pedagogie", "apprentissage", "université", "universite", "élève", "eleve",
    ],
    "finance": [
        "finance", "bourse", "investissement", "économie", "economie", "marché", "marche",
        "crypto", "banque", "trading", "inflation",
    ],
    "technologie": [
        "technologie", "technology", "intelligence artificielle", "ia", "software",
        "informatique", "robotique", "blockchain", "digital",
    ],
    "environnement": [
        "environnement", "climat", "climatique", "biodiversité", "biodiversite",
        "pollution", "energie", "énergie", "carbone", "ecologie", "écologie",
    ],
    "custom": [],
}

DEFAULT_CATEGORIES = [
    "Général",
    "Recherche",
    "Politique",
    "Économie",
    "Social",
    "Technologie",
]

GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.5-pro",
]


def get_theme_categories(theme: str) -> list:
    return THEME_CATEGORIES.get(theme.lower(), DEFAULT_CATEGORIES)


def get_theme_core_terms(theme: str) -> list:
    return THEME_CORE_TERMS.get(theme.lower(), [])
