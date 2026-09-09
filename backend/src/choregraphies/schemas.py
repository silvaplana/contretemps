"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py).
"""

from pydantic import BaseModel


class ChoregraphieCreation(BaseModel):
    nom: str
    horaire_repetition: str | None = None
    costume: str | None = None


class ChoregraphieModification(BaseModel):
    nom: str | None = None
    horaire_repetition: str | None = None
    costume: str | None = None


class ChoregraphieSortie(BaseModel):
    id: int
    cours_id: int
    nom: str
    horaire_repetition: str | None = None
    costume: str | None = None

    model_config = {"from_attributes": True}


class EleveParticipant(BaseModel):
    id: int
    nom: str
    prenom: str

    model_config = {"from_attributes": True}
