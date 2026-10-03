"""Discipline et niveau d'un cours, déduits de son nom (« Class Ini » :
Classique, Initiation). Sert à pré-remplir ces deux champs — à la création
d'un cours et pour les cours existants (migration) ; ils restent ensuite
modifiables dans Admin > Cours. Le sélecteur de l'écran Chorégraphie
(spec §5.3) filtre sur eux.
"""

from __future__ import annotations

_DISCIPLINES = {
    "eveil": "Éveil",
    "éveil": "Éveil",
    "class": "Classique",
    "classique": "Classique",
    "pointes": "Pointes",
    "jazz": "Jazz",
    "street": "Street",
    "contempo": "Contemporain",
    "contemporain": "Contemporain",
}

_NIVEAUX = {
    "ini": "Initiation",
    "initiation": "Initiation",
    "moy": "Moyen",
    "moyen": "Moyen",
    "inter": "Inter",
    "av": "Avancé",
    "avance": "Avancé",
    "avancé": "Avancé",
    "junior": "Junior",
    "adulte": "Adulte",
}


def classer(nom: str) -> tuple[str | None, str | None]:
    """(discipline, niveau) d'après le nom du cours ; None pour ce qui ne
    se reconnaît pas."""
    mots = (nom or "").split()
    if not mots:
        return None, None
    discipline = _DISCIPLINES.get(mots[0].lower())
    if discipline is None:
        return None, None
    niveau = " ".join(_NIVEAUX.get(mot.lower(), mot) for mot in mots[1:]) or None
    if discipline == "Éveil" and niveau is None:
        niveau = "Éveil"
    return discipline, niveau
