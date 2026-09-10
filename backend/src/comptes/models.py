"""Tables des comptes (voir spec/SPEC.md §6.2 et §6.3) : `Famille` (profils
familiaux façon Netflix, §2.1) et `Compte` (champs communs Admin/Prof/Élève
— les champs spécifiques à un rôle vivent dans les modules eleves/profs).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Famille(Base):
    """Regroupe les comptes qui partagent le même email, DANS une même
    école (voir §6.2) — calculée automatiquement à la création d'un
    compte, jamais éditée directement."""

    __tablename__ = "familles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    comptes: Mapped[list["Compte"]] = relationship("Compte", back_populates="famille")


class Compte(Base):
    """Champs COMMUNS aux 3 rôles (voir §6.3). Un compte appartient à une
    seule école — l'isolation multi-écoles (§2.1) passe par ecole_id sur
    (quasiment) toutes les tables du projet."""

    __tablename__ = "comptes"
    __table_args__ = (
        # PAS unique : plusieurs comptes (frères/sœurs, voir §6.2) peuvent
        # légitimement partager le même email dans une même école — c'est
        # justement ce que `get_or_create_famille` détecte pour les
        # regrouper. Un bug antérieur avait une UniqueConstraint ici, qui
        # empêchait cet usage prévu par la spec (trouvé en import Excel :
        # 80 élèves fictifs avec des emails partagés entre frères/sœurs).
        Index("ix_compte_ecole_email", "ecole_id", "email"),
        Index("ix_compte_ecole_role", "ecole_id", "role"),
        Index("ix_compte_dedup", "ecole_id", "nom", "prenom"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ecole_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    famille_id: Mapped[int] = mapped_column(ForeignKey("familles.id"), nullable=False, index=True)

    # 'admin' | 'professeur' | 'eleve' (voir §2.1) — texte simple plutôt
    # qu'un Enum SQLAlchemy : évite une migration de type de colonne si un
    # jour la spec ajoute un rôle, la validation se fait côté application.
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Texte libre, sans validation de format (voir §6.4bis : le fichier
    # réel contient des cas qu'une validation stricte rejetterait).
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    hashed_password_ou_code: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Réponse à "nom de votre 1er animal de compagnie" (voir "Code oublié ?"
    # à l'écran de connexion) — demandée à la création d'un compte Admin
    # (voir NouvelleEcoleModal). Champ commun (comme le reste de `Compte`)
    # même s'il n'a de sens que pour un admin aujourd'hui : pas de table
    # séparée pour un unique champ, contrairement à eleves/profs qui en ont
    # bien plus. Stocké en clair pour l'instant (comme les codes d'accès
    # école, voir ecoles.py) — à revoir si un vrai usage sensible apparaît.
    code_recuperation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    famille: Mapped[Famille] = relationship("Famille", back_populates="comptes")
