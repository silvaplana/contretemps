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
