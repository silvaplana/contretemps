"""Tables des comptes (voir spec/SPEC.md §6.2, §6.3 et §6.3bis) : `Famille`
(profils familiaux façon Netflix, §2.1), `Compte` (champs communs
Admin/Prof/Élève — les champs spécifiques à un rôle vivent dans les modules
eleves/profs) et `RoleCompte` (rôles cumulables d'un compte).
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
    # Regroupement familial à l'intérieur d'une même saison (§2.6, §6.1bis).
    saison_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), nullable=False, index=True)
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
        Index("ix_compte_dedup", "ecole_id", "nom", "prenom"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Vides UNIQUEMENT pour le Superuser (§2.5), qui n'appartient à aucune
    # école ni famille. Tout autre compte a toujours les deux.
    ecole_id: Mapped[int | None] = mapped_column(ForeignKey("ecoles.id"), nullable=True, index=True)
    famille_id: Mapped[int | None] = mapped_column(ForeignKey("familles.id"), nullable=True, index=True)
    # Une fiche par personne ET par saison (§2.6) : seuls les comptes de la
    # saison courante peuvent se connecter. Vide pour le Superuser (sans
    # école). Rempli automatiquement, voir saisons/automatique.py.
    saison_id: Mapped[int | None] = mapped_column(ForeignKey("saisons.id"), nullable=True, index=True)

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
    # "Dernière connexion" (voir messagerie/connexions.py) — mis à jour
    # seulement à la FERMETURE du dernier flux SSE ouvert de ce compte,
    # jamais pendant qu'il est en ligne (l'état "en ligne maintenant",
    # lui, n'est jamais persisté ici : voir connexions.py pour pourquoi).
    derniere_activite_le: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    famille: Mapped[Famille | None] = relationship("Famille", back_populates="comptes")
    # Rôles cumulables (§6.3bis) — ne JAMAIS les lire directement, passer
    # par comptes/roles.py (is_admin, is_prof...). `selectin` : chargés en
    # UNE requête pour toute une liste de comptes, pas une par compte (voir
    # le N+1 corrigé le 2026-09-19 sur Admin > Élèves). Supprimer un
    # compte supprime ses rôles (delete-orphan).
    roles: Mapped[list["RoleCompte"]] = relationship(
        "RoleCompte",
        back_populates="compte",
        lazy="selectin",
        cascade="all, delete-orphan",
    )

    # Lus par les schémas d'API (CompteSortie...), qui exposent à la fois
    # la liste `roles` et un `role` principal pour l'affichage.
    @property
    def noms_roles(self) -> list[str]:
        from .roles import noms_roles

        return noms_roles(self)

    @property
    def code_recuperation_defini(self) -> bool:
        return bool((self.code_recuperation or "").strip())

    @property
    def role_principal(self) -> str:
        from .roles import role_principal

        return role_principal(r.role for r in self.roles)


class RoleCompte(Base):
    """Un rôle détenu par un compte (voir §6.3bis) : une ligne par rôle,
    clé primaire (compte, rôle) donc jamais deux fois le même. Texte
    simple plutôt qu'un Enum SQLAlchemy, comme l'ancien `comptes.role` :
    la liste des rôles valides vit dans roles.py, pas dans le schéma."""

    __tablename__ = "roles_compte"

    compte_id: Mapped[int] = mapped_column(
        ForeignKey("comptes.id"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    compte: Mapped[Compte] = relationship("Compte", back_populates="roles")
