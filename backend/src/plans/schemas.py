"""Schémas des routes des tarifs (voir receiver.py). Montants en centimes."""

import datetime as dt

from pydantic import BaseModel, ConfigDict


class InstallmentIo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    # Vide : « À l'inscription ».
    due_on: dt.date | None = None
    amount: int


class PlanIn(BaseModel):
    name: str
    price: int
    active: bool = True
    installments: list[InstallmentIo] = []
    # Remettre une formule retirée à sa place (« Annuler »).
    position: int | None = None


class PlanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    price: int
    active: bool
    position: int
    installments: list[InstallmentIo]


class Previous(BaseModel):
    name: str
    plans: int


class PlansOut(BaseModel):
    # Le nom de la saison affichée, pour le titre « Tarifs 2027-2028 ».
    season: str
    # Vrai quand on regarde une ancienne saison : rien ne se modifie.
    read_only: bool
    plans: list[PlanOut]
    # La saison d'avant, pour « Reprendre ceux de… » (aucune formule cette
    # saison, et la précédente en a).
    previous: Previous | None = None
