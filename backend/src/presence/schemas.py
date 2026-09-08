"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py).
"""

import datetime as dt

from pydantic import BaseModel


class SeanceCreation(BaseModel):
    date: dt.date


class SeanceSortie(BaseModel):
    id: int
    cours_id: int
    date: dt.date

    model_config = {"from_attributes": True}


class PresenceEleveModification(BaseModel):
    statut: str  # 'present' | 'absent' | 'retard'


class PresenceEleveSortie(BaseModel):
    id: int
    seance_id: int
    eleve_id: int
    statut: str

    model_config = {"from_attributes": True}


class PresenceProfModification(BaseModel):
    heure_debut_reelle: str | None = None
    heure_fin_reelle: str | None = None
    depassement_minutes: int | None = None


class PresenceProfSortie(BaseModel):
    id: int
    seance_id: int
    professeur_id: int
    heure_debut_reelle: str | None = None
    heure_fin_reelle: str | None = None
    depassement_minutes: int
    # Calculé, pas stocké (voir §6.6) — ajouté par le receiver.
    statut: str


class HeuresSortie(BaseModel):
    minutes_total: int
    minutes_depassement: int
