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

DEFAULT_CATEGORIES = [
    "Général",
    "Recherche",
    "Politique",
    "Économie",
    "Social",
    "Technologie",
]


def get_theme_categories(theme: str) -> list:
    return THEME_CATEGORIES.get(theme.lower(), DEFAULT_CATEGORIES)
