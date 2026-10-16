"""Formes des requêtes/réponses HTTP (Pydantic)."""

from pydantic import BaseModel


class ProfCreation(BaseModel):
    nom: str
    prenom: str
    email: str | None = None
    telephone: str | None = None


class ProfModification(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    email: str | None = None
    telephone: str | None = None


class ProfSortie(BaseModel):
    id: int
    ecole_id: int
    nom: str
    prenom: str
    email: str | None = None
    # Plusieurs emails par fiche (§2.1) ; `email` les donne séparés par
    # une virgule, et accepte cette forme en entrée.
    emails: list[str] = []
    telephone: str | None = None
    # Voir §6.5 : relation, pas un champ stocké — calculé à la sortie
    # via cours.cours_du_professeur (l'assignation elle-même se fait par
    # les routes existantes /cours/{id}/professeurs/{compte_id}).
    cours_ids: list[int] = []
