"""Schémas des routes des tarifs (voir receiver.py). Montants en centimes."""

import datetime as dt

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


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


class AdjustmentIn(BaseModel):
    name: str
    # Négatif = en moins ; centimes (« eur ») ou centièmes de % (« pct »).
    amount: int
    unit: Literal["eur", "pct"] = "eur"
    mode: Literal["check", "code"] = "check"
    code: str | None = None
    shown: bool = False
    max_uses: int | None = Field(default=None, ge=1)
    until: dt.date | None = None
    quantity: int | None = Field(default=None, ge=1)
    active: bool = True
    # Vide : toutes les formules.
    plan_ids: list[int] = []
    position: int | None = None


class AdjustmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    amount: int
    unit: str
    mode: str
    code: str | None
    shown: bool
    max_uses: int | None
    until: dt.date | None
    quantity: int | None
    active: bool
    position: int
    plan_ids: list[int]


class Previous(BaseModel):
    name: str
    plans: int
    adjustments: int


class Taken(BaseModel):
    """Ce que « Reprendre ceux de… » a recopié (pour l'Annuler)."""

    plans: list[PlanOut]
    adjustments: list[AdjustmentOut]


class PlansOut(BaseModel):
    # Le nom de la saison affichée, pour le titre « Tarifs 2027-2028 ».
    season: str
    # Vrai quand on regarde une ancienne saison : rien ne se modifie.
    read_only: bool
    plans: list[PlanOut]
    adjustments: list[AdjustmentOut]
    # La saison d'avant, pour « Reprendre ceux de… » (aucune formule cette
    # saison, et la précédente en a).
    previous: Previous | None = None
