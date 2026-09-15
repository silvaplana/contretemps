"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py).
"""

from pydantic import BaseModel


class HoraireSupplementaire(BaseModel):
    """Créneau EN PLUS du créneau principal d'un cours (voir
    models.py:Cours.horaires_supplementaires) — rare, ex. "Éveil"
    proposé aussi un autre jour."""

    jour: str
    heure_debut: str
    heure_fin: str


class HoraireSupplementaireSortie(HoraireSupplementaire):
    id: int

    model_config = {"from_attributes": True}


class CoursCreation(BaseModel):
    nom: str
    jour: str | None = None
    heure_debut: str | None = None
    heure_fin: str | None = None
    salle: str | None = None
    descriptif: str | None = None
    horaires_supplementaires: list[HoraireSupplementaire] = []


class CoursModification(BaseModel):
    nom: str | None = None
    jour: str | None = None
    heure_debut: str | None = None
    heure_fin: str | None = None
    salle: str | None = None
    descriptif: str | None = None
    # None = pas touché (voir receiver.py:modifier, exclude_unset=True) ;
    # une liste (même vide) remplace entièrement les créneaux en plus.
    horaires_supplementaires: list[HoraireSupplementaire] | None = None


class CoursSortie(BaseModel):
    id: int
    ecole_id: int
    nom: str
    jour: str | None = None
    heure_debut: str | None = None
    heure_fin: str | None = None
    salle: str | None = None
    descriptif: str | None = None
    horaires_supplementaires: list[HoraireSupplementaireSortie] = []

    model_config = {"from_attributes": True}


class CompteResume(BaseModel):
    """Vue allégée d'un compte — utilisée pour lister les professeurs/élèves
    d'un cours sans exposer tout `comptes.schemas` (pas encore créé)."""

    id: int
    nom: str
    prenom: str
    role: str

    model_config = {"from_attributes": True}
