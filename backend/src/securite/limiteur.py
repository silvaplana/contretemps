"""Limitation des essais de connexion Superuser (voir spec/SPEC.md §2.5) :
après 5 mots de passe faux, blocage 15 minutes. Ce mot de passe est la
seule barrière devant tous les droits : il ne doit pas pouvoir être deviné
en boucle.

En mémoire du processus : un redémarrage du backend remet les compteurs à
zéro. Acceptable ici (un seul processus, redémarrages rares) ; à déplacer
en base si l'appli passe un jour à plusieurs processus.
"""

from __future__ import annotations

import threading
import time

ESSAIS_MAX = 5
BLOCAGE_SECONDES = 15 * 60

_verrou = threading.Lock()
_echecs: dict[int, list[float]] = {}
_bloque_jusqu_a: dict[int, float] = {}


def est_bloque(compte_id: int, maintenant: float | None = None) -> bool:
    maintenant = time.time() if maintenant is None else maintenant
    with _verrou:
        return _bloque_jusqu_a.get(compte_id, 0) > maintenant


def noter_echec(compte_id: int, maintenant: float | None = None) -> None:
    maintenant = time.time() if maintenant is None else maintenant
    with _verrou:
        # Seuls les échecs des 15 dernières minutes comptent.
        recents = [t for t in _echecs.get(compte_id, []) if t > maintenant - BLOCAGE_SECONDES]
        recents.append(maintenant)
        if len(recents) >= ESSAIS_MAX:
            _bloque_jusqu_a[compte_id] = maintenant + BLOCAGE_SECONDES
            recents = []
        _echecs[compte_id] = recents


def noter_succes(compte_id: int) -> None:
    with _verrou:
        _echecs.pop(compte_id, None)
        _bloque_jusqu_a.pop(compte_id, None)


def reinitialiser() -> None:
    """Pour les tests."""
    with _verrou:
        _echecs.clear()
        _bloque_jusqu_a.clear()
