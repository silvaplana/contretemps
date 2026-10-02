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
    # Obligatoire pour une famille (voir FormulaireInscription.jsx) : sert
    # à recevoir la confirmation ET, si HelloAsso est choisi, à payer (voir
    # inscriptions.py:initier_paiement_helloasso — payer.email), ce que
    # vérifie receiver.py:creer. Facultatif seulement pour une fiche
    # papier saisie par un admin (receiver.py:enregistrer_eleve).
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
    # 1 (comptant) ou 3 (une échéance par trimestre) — voir
    # tarifs.py:calculer_echeances_helloasso. Sans effet si
    # moyen_paiement != "helloasso".
    paiement_nb_echeances: int = 1

    # Auto-déclarée par la famille (case à cocher, voir
    # FormulaireInscription.jsx) — un frère/sœur déjà inscrit cette
    # saison, éventuellement PAS via ce formulaire en ligne (donc
    # invisible à la détection automatique, voir
    # inscriptions.py:_detecter_doublon_et_famille, qui ne connaît que
    # les inscriptions déjà passées par ici). Combinée en "OU" avec la
    # détection automatique — jamais bloquante, l'admin vérifie à la
    # fusion Excel comme pour doublon_possible.
    reduction_famille_demandee: bool = False
    # Remplace la case ci-dessus (décision du 2026-10-02) : 1 = pas de
    # réduction, 2 ou 3 = nombre de membres de la famille inscrits (voir
    # tarifs.py:ADHESION_PAR_FAMILLE). L'ancienne case reste lue (elle vaut
    # 2) pour une page pas encore rechargée.
    famille_membres: int = 1


class InscriptionSortie(BaseModel):
    token_public: str
    saison: str
    eleve_nom: str
    eleve_prenom: str
    # Renvoyé pour que l'écran de confirmation puisse afficher à quelle
    # adresse la confirmation a (ou n'a pas pu) été envoyée (voir
    # Confirmation.jsx) — jamais utilisé pour autre chose côté client.
    eleve_email: str | None
    cours_choisis: list[str]

    palier_tarifaire: str
    nb_cours_semaine: int
    montant_adhesion: float
    montant_mensuel_septembre: float
    montant_trimestriel: float
    reduction_famille_appliquee: bool
    famille_membres: int
    alerte_palier_mixte: bool

    doublon_possible: bool
    moyen_paiement: str
    paiement_nb_echeances: int
    statut_paiement: str
    email_envoye: bool


class PaiementChoixEntree(BaseModel):
    """Étape 2 du flux (voir spec/SPEC-inscription.md) : choix du moyen
    de paiement, envoyé séparément de InscriptionCreation (l'étape 1 ne
    le connaît pas encore)."""

    moyen_paiement: str
    # 1 (comptant) ou 3 (une échéance par trimestre) — chèque ET
    # HelloAsso (voir tarifs.py:calculer_echeances_helloasso).
    paiement_nb_echeances: int = 1


class PaiementHelloAssoSortie(BaseModel):
    """Réponse de l'initiation du paiement HelloAsso (voir
    receiver.py:initier_paiement_helloasso) — rediriger le navigateur
    vers `redirect_url` pour que la famille paie."""

    redirect_url: str


class PaiementHelloAssoEntree(BaseModel):
    """URL de la page à laquelle revenir après le paiement (voir
    FormulaireInscription.jsx — dépend de l'origine appelante, jamais
    codée en dur côté serveur)."""

    retour_url: str


class FicheLueSortie(BaseModel):
    """Ce que reçoit l'admin après la lecture d'une fiche papier (voir
    fiches.py) : le jeton du brouillon, et ce que la lecture a coûté."""

    jeton: str
    nb_pages: int
    nb_champs_douteux: int
    cout_usd: float
    jetons_entree: int
    jetons_sortie: int


class FicheBrouillonSortie(BaseModel):
    """Le brouillon, tel que le formulaire en ligne le pré-remplit."""

    jeton: str
    ecole_id: int
    donnees: dict
    champs_douteux: list[str]
    remarques: str | None
    types_pages: list[str]
    cout_usd: float


class EleveEnregistreSortie(BaseModel):
    """Élève ajouté à la liste officielle à partir d'une fiche papier
    (voir fiches.py:enregistrer_eleve)."""

    eleve_id: int
    eleve_nom: str
    eleve_prenom: str
    saison: str
    mail_envoye: bool
    mail_adresse: str | None
    cout_usd: float
