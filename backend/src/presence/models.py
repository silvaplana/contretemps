"""Tables de présence (voir spec/SPEC.md §6.6). Séparées entre élèves et
professeurs : leurs données de présence sont de nature différente
(statut coché à la main vs. heures réelles saisies).
"""

from __future__ import annotations

import datetime as dt

from sqlalchemy import ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class SeancePresence(Base):
    """Création MANUELLE par le prof/admin (bouton "+ nouvelle séance") —
    jamais créée automatiquement à l'ouverture de l'onglet (voir §6.6)."""

    __tablename__ = "seances_presence"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cours_id: Mapped[int] = mapped_column(ForeignKey("cours.id"), nullable=False, index=True)
    date: Mapped[dt.date] = mapped_column(nullable=False)


class PresenceEleve(Base):
    """Une ligne par élève présent à la séance, statut saisi manuellement."""

    __tablename__ = "presences_eleves"
    __table_args__ = (UniqueConstraint("seance_id", "eleve_id", name="uq_presence_eleve"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seance_id: Mapped[int] = mapped_column(
        ForeignKey("seances_presence.id"), nullable=False, index=True
    )
    eleve_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), nullable=False, index=True)
    # 'present' | 'absent' | 'retard' — texte, pas Enum (même choix que
    # comptes.role, voir backend/README.md).
    statut: Mapped[str] = mapped_column(String(20), nullable=False, default="present")


class PresenceProf(Base):
    """Une ligne PAR PROFESSEUR (plusieurs profs peuvent co-enseigner un
    même cours, chacun avec ses propres horaires réels, voir §6.6).
    PAS de statut stocké : déduit des heures (voir presence.py :
    `statut_prof`)."""

    __tablename__ = "presences_profs"
    __table_args__ = (UniqueConstraint("seance_id", "professeur_id", name="uq_presence_prof"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    seance_id: Mapped[int] = mapped_column(
        ForeignKey("seances_presence.id"), nullable=False, index=True
    )
    professeur_id: Mapped[int] = mapped_column(
        ForeignKey("comptes.id"), nullable=False, index=True
    )
    heure_debut_reelle: Mapped[str | None] = mapped_column(String(10), nullable=True)
    heure_fin_reelle: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Inclus dans l'intervalle début/fin réel, pas ajouté en plus (voir
    # §6.6 : heures normales = (fin - début) - depassement_minutes).
    depassement_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
