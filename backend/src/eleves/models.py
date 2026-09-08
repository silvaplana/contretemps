"""Tables spécifiques aux élèves (voir spec/SPEC.md §6.4). Les champs
communs (nom, prénom, email...) restent sur `comptes.models.Compte` —
`ProfilEleve` ne porte que ce qui est propre au rôle élève.
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class ProfilEleve(Base):
    __tablename__ = "profils_eleves"

    # PK = FK vers comptes.id : un profil élève par compte, pas d'id propre
    # (voir §6.4 : "compte_id | PK, FK -> comptes").
    compte_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), primary_key=True)
    date_naissance: Mapped[dt.date | None] = mapped_column(nullable=True)
    adresse: Mapped[str | None] = mapped_column(Text, nullable=True)
    allergies: Mapped[str | None] = mapped_column(Text, nullable=True)
    traitement_medical: Mapped[str | None] = mapped_column(Text, nullable=True)
    informations_importantes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Texte, pas Enum (même choix que `comptes.role`, voir backend/README.md) :
    # seulement 2 valeurs prévues ("en_cours"/"paye") mais évite une migration
    # si un 3e statut apparaît.
    statut_paiement: Mapped[str] = mapped_column(String(20), nullable=False, default="en_cours")
    montant_total_annee: Mapped[float | None] = mapped_column(Float, nullable=True)
    montant_paye: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    commentaire_admin: Mapped[str | None] = mapped_column(Text, nullable=True)


class ContactEleve(Base):
    """Plusieurs contacts possibles par élève (voir §6.4 : remplace les
    anciens champs uniques urgence_nom/urgence_prenom/urgence_lien)."""

    __tablename__ = "contacts_eleves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eleve_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), nullable=False, index=True)
    nom: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prenom: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lien: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Texte libre volontairement non validé (voir §6.4 : peut contenir
    # plusieurs numéros, des annotations...).
    telephone: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
