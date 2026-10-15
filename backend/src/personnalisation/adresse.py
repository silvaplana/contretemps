"""Adresse web d'une école : le sous-domaine de
`https://<adresse>.contretemps.silvaplana.cloud` (spec §2.7).

Même règle côté écran (frontend/src/utils/adresseEcole.js) : la saisie est
normalisée en direct, le serveur revérifie.
"""

from __future__ import annotations

import re
import unicodedata

LONGUEUR_MIN = 3
LONGUEUR_MAX = 40
# `app` porte la page générique du produit (connexion toutes écoles,
# création d'école, Superuser) ; `contretemps` est le nom du produit.
RESERVES = frozenset({"www", "api", "admin", "app", "mail", "contretemps"})
GENERIQUE = "app"

_VALIDE = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


class AdresseInvalide(ValueError):
    """`raison` : 'invalide' ou 'reserve' ; le message est montrable."""

    def __init__(self, raison: str, message: str) -> None:
        super().__init__(message)
        self.raison = raison


def normaliser(texte: str) -> str:
    """« Danse Lyon 3e » -> « danse-lyon-3e » : minuscules sans accent,
    espaces et ponctuation en tirets, ni tiret double ni aux bords."""
    sans_accent = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode("ascii")
    tirets = re.sub(r"[^a-z0-9]+", "-", sans_accent.lower())
    return tirets.strip("-")[:LONGUEUR_MAX].strip("-")


def verifier(adresse: str) -> str:
    """L'adresse normalisée, ou AdresseInvalide."""
    propre = normaliser(adresse)
    if len(propre) < LONGUEUR_MIN or not _VALIDE.match(propre):
        raise AdresseInvalide(
            "invalide", f"L'adresse doit compter {LONGUEUR_MIN} à {LONGUEUR_MAX} lettres, chiffres ou tirets."
        )
    if propre in RESERVES:
        raise AdresseInvalide("reserve", "Ce nom est réservé.")
    return propre
