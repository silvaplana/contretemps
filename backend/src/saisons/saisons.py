"""Règles de base des saisons (voir spec/SPEC.md §2.6).

La saison courante d'une école n'est stockée nulle part : c'est la plus
récemment créée (plus grand id). Seule elle est modifiable.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session

from .models import Saison


def requete_saison_courante_id(ecole_id: int):
    return select(func.max(Saison.id)).where(Saison.ecole_id == ecole_id)


def saison_courante_id(db: Session | Connection, ecole_id: int) -> int | None:
    return db.execute(requete_saison_courante_id(ecole_id)).scalar()


def saison_par_defaut(aujourdhui: dt.date | None = None) -> tuple[str, dt.date, dt.date]:
    """Nom et dates de la première saison d'une école toute neuve : de
    septembre à fin août, la bascule se faisant au 1er août (même seuil que
    inscriptions/saison.py : saison_actuelle)."""
    aujourdhui = aujourdhui or dt.date.today()
    annee = aujourdhui.year if aujourdhui.month >= 8 else aujourdhui.year - 1
    return f"{annee}-{annee + 1}", dt.date(annee, 9, 1), dt.date(annee + 1, 8, 31)
