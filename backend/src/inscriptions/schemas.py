"""Formes des requêtes/réponses HTTP (Pydantic) — pas les tables (voir
models.py)."""

from __future__ import annotations

import datetime as dt

from pydantic import BaseModel


class InscriptionCreation(BaseModel):
    """Tous les champs remplis par la famille dans le formulaire public.
    `saison`/tarif/`token_public`/etc. sont calculés côté serveur (voir
    inscriptions.py:creer), jamais fournis par le client."""

    eleve_nom: str
    eleve_prenom: str
    eleve_date_naissance: dt.date
    eleve_adresse: str | None = None
    eleve_telephone: str | None = None
    eleve_email: str | None = None

    cours_ids: list[int]

    allergies: str | None = None
    traitement_medical: str | None = None
    informations_importantes: str | None = None

    contact_urgence_nom: str | None = None
    contact_urgence_prenom: str | None = None
    contact_urgence_lien: str | None = None
    contact_urgence_telephone: str | None = None

    droit_image_autorise: bool = False
    droit_image_site: bool = False
    droit_image_reseaux: bool = False
    droit_image_affiches: bool = False

    reglement_lu_approuve: bool
    signataire_nom: str

    moyen_paiement: str = "cheque"


class InscriptionSortie(BaseModel):
    token_public: str
    saison: str
    eleve_nom: str
    eleve_prenom: str
    cours_choisis: list[str]

    palier_tarifaire: str
    nb_cours_semaine: int
    montant_adhesion: float
    montant_mensuel_septembre: float
    montant_trimestriel: float
    reduction_famille_appliquee: bool
    alerte_palier_mixte: bool

    doublon_possible: bool
    moyen_paiement: str
    email_envoye: bool
