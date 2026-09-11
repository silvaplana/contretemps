"""Table `inscriptions` (voir spec/SPEC-inscription.md) : une soumission
du formulaire d'inscription public (`contretemps-inscription`), VOLONTAIREMENT
isolée de `comptes`/`eleves` — aucune FK vers ces tables. Explicitement hors
scope (voir spec/SPEC-inscription.md §2, commentaire) : cette inscription
n'implique pas la création d'un élève dans la vraie base de l'appli
principale, seulement l'enregistrement de la demande + son suivi
(PDF/Excel/email générés). Un admin qui valide une inscription crée
l'élève lui-même, à la main, comme aujourd'hui.
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Cours choisis — table de jointure brute, même style que eleves_cours
# (voir cours/models.py). Pas de FK stricte côté `cours_id` vers `cours.id`
# malgré l'apparence : voir Inscription.cours_id ci-dessous, en réalité
# la contrainte EST posée (les cours viennent de la même école, résolus
# via GET /cours?ecole_id=), mais volontairement pas de ON DELETE CASCADE
# particulier : une inscription reste lisible même si le cours choisi est
# supprimé plus tard (ex. saison suivante).
inscriptions_cours = Table(
    "inscriptions_cours",
    Base.metadata,
    Column("inscription_id", ForeignKey("inscriptions.id"), primary_key=True),
    Column("cours_id", ForeignKey("cours.id"), primary_key=True),
)


class Inscription(Base):
    __tablename__ = "inscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    # UUID4 — sert aux routes de téléchargement (dossier/facture PDF) sans
    # exposer l'id séquentiel (voir receiver.py).
    token_public: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    saison: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    ip_soumission: Mapped[str | None] = mapped_column(String(45), nullable=True)

    # --- Élève ---
    eleve_nom: Mapped[str] = mapped_column(String(150), nullable=False)
    eleve_prenom: Mapped[str] = mapped_column(String(150), nullable=False)
    eleve_date_naissance: Mapped[dt.date] = mapped_column(nullable=False)
    eleve_adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    eleve_telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    eleve_email: Mapped[str | None] = mapped_column(String(150), nullable=True)
    # Chemin relatif (voir stockage.py:chemin_relatif) — comme
    # pdf_dossier_chemin/pdf_facture_chemin ci-dessous, jamais le fichier
    # lui-même en base. Optionnelle : uploadée séparément après la
    # création (voir receiver.py : POST /inscriptions/{token}/photo),
    # jamais bloquante si absente ou en échec (voir inscriptions.py).
    eleve_photo_chemin: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # --- Infos médicales (même nommage que profils_eleves, voir eleves/models.py) ---
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    traitement_medical: Mapped[str | None] = mapped_column(Text, nullable=True)
    informations_importantes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Contact d'urgence (un seul bloc, comme le PDF papier) ---
    contact_urgence_nom: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_urgence_prenom: Mapped[str | None] = mapped_column(String(150), nullable=True)
    contact_urgence_lien: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_urgence_telephone: Mapped[str | None] = mapped_column(String(30), nullable=True)

    # --- Droit à l'image ---
    droit_image_autorise: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    droit_image_site: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    droit_image_reseaux: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    droit_image_affiches: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Règlement + signature électronique (case à cocher + nom tapé,
    # voir spec/SPEC-inscription.md — décision prise avec l'utilisateur :
    # pas de canvas de signature dessinée). L'horodatage/IP réutilisent
    # created_at/ip_soumission ci-dessus, pas dupliqués.
    reglement_lu_approuve: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    signataire_nom: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # --- Paiement ---
    moyen_paiement: Mapped[str] = mapped_column(String(20), nullable=False, default="cheque")
    # "en_attente" (par défaut, chèque ou HelloAsso pas encore payé) /
    # "paye" (HelloAsso confirmé, voir helloasso.py) / "echec".
    statut_paiement: Mapped[str] = mapped_column(String(20), nullable=False, default="en_attente")
    # 1 (comptant) ou 3 (une échéance par trimestre) — choisi par la
    # famille, uniquement significatif si moyen_paiement == "helloasso"
    # (voir spec/SPEC-inscription.md, décision : 1x ou 3x au choix).
    paiement_nb_echeances: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # Id du Checkout Intent HelloAsso (voir helloasso.py) — sert à
    # ré-interroger l'état du paiement (GET .../checkout-intents/{id}),
    # jamais fait confiance à un simple retour navigateur ou webhook non
    # signé (la vérification de signature webhook est réservée aux
    # comptes "partenaire" HelloAsso, pas notre cas).
    helloasso_checkout_intent_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # --- Tarif, FIGÉ à la soumission (jamais recalculé si le barème
    # change plus tard, voir tarifs.py) ---
    palier_tarifaire: Mapped[str] = mapped_column(String(30), nullable=False)
    nb_cours_semaine: Mapped[int] = mapped_column(Integer, nullable=False)
    montant_adhesion: Mapped[float] = mapped_column(Float, nullable=False)
    montant_mensuel_septembre: Mapped[float] = mapped_column(Float, nullable=False)
    montant_trimestriel: Mapped[float] = mapped_column(Float, nullable=False)
    reduction_famille_appliquee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Cours choisis touchant plusieurs paliers à la fois (cas rare) — le
    # tarif retient le palier le plus cher, l'admin doit vérifier à la
    # main (voir tarifs.py:calculer_tarif). Acceptable en phase 1 : le
    # paiement réel reste par chèque, toujours validé par un humain.
    alerte_palier_mixte: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # --- Suivi ---
    # Doublon détecté (même nom/prénom/email, même école+saison) — juste
    # un signal pour l'admin, jamais bloquant (voir inscriptions.py).
    doublon_possible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pdf_dossier_chemin: Mapped[str | None] = mapped_column(String(500), nullable=True)
    pdf_facture_chemin: Mapped[str | None] = mapped_column(String(500), nullable=True)
    email_envoye: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_erreur: Mapped[str | None] = mapped_column(Text, nullable=True)
