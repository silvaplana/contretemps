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


# --- Import Excel (voir §6.4bis et import_excel.py) ---


class LigneApercuSortie(BaseModel):
    numero_ligne: int
    nom: str
    prenom: str
    email: str | None = None
    telephone: str | None = None
    telephone_suspect: bool
    adresse: str | None = None
    date_naissance: dt.date | None = None
    contact_parent_brut: str | None = None
    cours_ids: list[int] = []
    colonnes_non_reconnues: list[str] = []
    eleve_existant_id: int | None = None
    action: str

    # Lu depuis les dataclasses `LigneApercu`/`ApercuImport` de
    # import_excel.py, pas des objets Pydantic/SQLAlchemy.
    model_config = {"from_attributes": True}


class ApercuImportSortie(BaseModel):
    lignes: list[LigneApercuSortie]
    colonnes_non_reconnues_globales: list[str]

    model_config = {"from_attributes": True}


class LigneValidationEntree(BaseModel):
    """Reprend les champs de `LigneApercuSortie` — l'admin peut avoir
    corrigé `action` (et n'importe quel autre champ) à la relecture avant
    de poster ceci (voir §6.4bis)."""

    numero_ligne: int
    nom: str
    prenom: str
    email: str | None = None
    telephone: str | None = None
    adresse: str | None = None
    date_naissance: dt.date | None = None
    contact_parent_brut: str | None = None
    cours_ids: list[int] = []
    eleve_existant_id: int | None = None
    action: str


class ValidationImportEntree(BaseModel):
    lignes: list[LigneValidationEntree]


class ResultatImportSortie(BaseModel):
    crees: int
    mis_a_jour: int
    ignores: int


class MappingColonneEntree(BaseModel):
    en_tete_excel: str
    cours_id: int


class MappingColonneSortie(BaseModel):
    id: int
    ecole_id: int
    en_tete_excel: str
    cours_id: int

    model_config = {"from_attributes": True}
