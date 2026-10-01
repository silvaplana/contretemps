"""Limitation des essais (voir spec/SPEC.md §2.2 et §2.5) : après 5 mots de
passe faux, blocage 15 minutes. Un mot de passe ne doit pas pouvoir être
deviné en boucle. Sert aussi à espacer les demandes de « Mot de passe
oublié ? ».

Chaque chose surveillée a sa CLÉ (ex. "connexion:<email>",
"oubli:<email>") : les compteurs sont indépendants.

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
_echecs: dict[str, list[float]] = {}
_bloque_jusqu_a: dict[str, float] = {}


def est_bloque(cle: str, maintenant: float | None = None) -> bool:
    maintenant = time.time() if maintenant is None else maintenant
    with _verrou:
        return _bloque_jusqu_a.get(cle, 0) > maintenant


def noter_echec(cle: str, maintenant: float | None = None) -> None:
    maintenant = time.time() if maintenant is None else maintenant
    with _verrou:
        # Seuls les échecs des 15 dernières minutes comptent.
        recents = [t for t in _echecs.get(cle, []) if t > maintenant - BLOCAGE_SECONDES]
        recents.append(maintenant)
        if len(recents) >= ESSAIS_MAX:
            _bloque_jusqu_a[cle] = maintenant + BLOCAGE_SECONDES
            recents = []
        _echecs[cle] = recents


def noter_succes(cle: str) -> None:
    with _verrou:
        _echecs.pop(cle, None)
        _bloque_jusqu_a.pop(cle, None)


def reinitialiser() -> None:
    """Pour les tests."""
    with _verrou:
        _echecs.clear()
        _bloque_jusqu_a.clear()
