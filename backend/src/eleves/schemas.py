"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py). `EleveSortie` fusionne les champs communs (Compte) et les
champs spécifiques (ProfilEleve) : côté API, un élève est vu comme un
seul objet, même si stocké dans 2 tables (voir eleves.py/receiver.py).
"""

import datetime as dt

from pydantic import BaseModel


class ContactCreation(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    lien: str | None = None
    telephone: str | None = None
    email: str | None = None


class ContactModification(ContactCreation):
    pass


class ContactSortie(BaseModel):
    id: int
    eleve_id: int
    nom: str | None = None
    prenom: str | None = None
    lien: str | None = None
    telephone: str | None = None
    email: str | None = None

    model_config = {"from_attributes": True}


class EleveCreation(BaseModel):
    nom: str
    prenom: str
    email: str | None = None
    telephone: str | None = None
    date_naissance: dt.date | None = None
    adresse: str | None = None
    allergies: str | None = None
    traitement_medical: str | None = None
    informations_importantes: str | None = None
    statut_paiement: str | None = None
    montant_total_annee: float | None = None
    montant_paye: float | None = None
    commentaire_admin: str | None = None


class EleveModification(BaseModel):
    nom: str | None = None
    prenom: str | None = None
    email: str | None = None
    telephone: str | None = None
    date_naissance: dt.date | None = None
    adresse: str | None = None
    allergies: str | None = None
    traitement_medical: str | None = None
    informations_importantes: str | None = None
    statut_paiement: str | None = None
    montant_total_annee: float | None = None
    montant_paye: float | None = None
    commentaire_admin: str | None = None


class EleveSortie(BaseModel):
    id: int
    ecole_id: int
    nom: str
    prenom: str
    email: str | None = None
    telephone: str | None = None
    date_naissance: dt.date | None = None
    age: int | None = None
    adresse: str | None = None
    allergies: str | None = None
    traitement_medical: str | None = None
    informations_importantes: str | None = None
    statut_paiement: str
    montant_total_annee: float | None = None
    montant_paye: float
    commentaire_admin: str | None = None
    contacts: list[ContactSortie] = []
