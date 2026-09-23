"""Détermine la saison en cours (ex. "2026-2027") — règle simple : une
nouvelle saison commence en septembre (seuil choisi au 1er août, marge
avant la rentrée pour les inscriptions anticipées)."""

from __future__ import annotations

import datetime as dt


def saison_actuelle(aujourdhui: dt.date | None = None) -> str:
    aujourdhui = aujourdhui or dt.date.today()
    if aujourdhui.month >= 8:
        return f"{aujourdhui.year}-{aujourdhui.year + 1}"
    return f"{aujourdhui.year - 1}-{aujourdhui.year}"


def saison_des_inscriptions(db, ecole_id: int) -> str:
    """Libellé "AAAA-AAAA" de la saison courante de l'école (spec §2.6),
    tiré de ses DATES et non de son nom (libre, renommable) : c'est lui
    que le parcours d'inscription utilise pour les échéances, les
    documents et le fichier des nouvelles inscriptions."""
    from saisons import Saison, saison_courante_id

    saison = db.get(Saison, saison_courante_id(db, ecole_id))
    if saison is None:
        return saison_actuelle()
    annee_fin = max(saison.date_fin.year, saison.date_debut.year + 1)
    return f"{saison.date_debut.year}-{annee_fin}"
