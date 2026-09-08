"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py).
"""

from pydantic import BaseModel


class CoursCreation(BaseModel):
    nom: str
    jour: str | None = None
    heure_debut: str | None = None
    heure_fin: str | None = None
    salle: str | None = None
    descriptif: str | None = None


class CoursModification(BaseModel):
    nom: str | None = None
    jour: str | None = None
    heure_debut: str | None = None
    heure_fin: str | None = None
    salle: str | None = None
    descriptif: str | None = None


class CoursSortie(BaseModel):
    id: int
    ecole_id: int
    nom: str
    jour: str | None = None
    heure_debut: str | None = None
    heure_fin: str | None = None
    salle: str | None = None
    descriptif: str | None = None

    model_config = {"from_attributes": True}


class CompteResume(BaseModel):
    """Vue allégée d'un compte — utilisée pour lister les professeurs/élèves
    d'un cours sans exposer tout `comptes.schemas` (pas encore créé)."""

    id: int
    nom: str
    prenom: str
    role: str

    model_config = {"from_attributes": True}
