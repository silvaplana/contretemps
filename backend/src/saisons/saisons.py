"""Règles de base des saisons (voir spec/SPEC.md §2.6).

La saison courante d'une école n'est stockée nulle part : c'est celle qui
commence le plus tard (à égalité, la dernière créée). Une saison passée
peut donc être créée après coup sans prendre sa place. Seule la courante
est modifiable, plus une ancienne saison ouverte exceptionnellement
(`Saison.ouverte`).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.orm import Session, aliased

from .models import Saison


def requete_saison_courante_id(ecole_id):
    """`ecole_id` : un entier, ou une colonne pour une sous-requête liée
    (voir portee.py). Alias : la requête englobante peut viser `saisons`."""
    s = aliased(Saison)
    return select(s.id).where(s.ecole_id == ecole_id).order_by(s.date_debut.desc(), s.id.desc()).limit(1)


def saison_courante_id(db: Session | Connection, ecole_id: int) -> int | None:
    return db.execute(requete_saison_courante_id(ecole_id)).scalar()


def saison_par_defaut(aujourdhui: dt.date | None = None) -> tuple[str, dt.date, dt.date]:
    """Nom et dates de la première saison d'une école toute neuve : de
    septembre à fin août, la bascule se faisant au 1er août (même seuil que
    inscriptions/saison.py : saison_actuelle)."""
    aujourdhui = aujourdhui or dt.date.today()
    annee = aujourdhui.year if aujourdhui.month >= 8 else aujourdhui.year - 1
    return f"{annee}-{annee + 1}", dt.date(annee, 9, 1), dt.date(annee + 1, 8, 31)
