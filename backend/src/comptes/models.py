"""Tables des comptes (voir spec/SPEC.md §6.2, §6.3 et §6.3bis) : `Famille`
(profils familiaux façon Netflix, §2.1), `Compte` (champs communs
Admin/Prof/Élève — les champs spécifiques à un rôle vivent dans les modules
eleves/profs) et `RoleCompte` (rôles cumulables d'un compte).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Famille(Base):
    """Regroupe les comptes reliés de proche en proche par un email commun,
    DANS une même école (voir §6.2) — recalculée automatiquement à chaque
    changement d'emails (Comptes.recalculer_familles), jamais éditée
    directement."""

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
    # Fiche de la même personne dans la saison précédente, quand celle-ci a
    # été recopiée à la création d'une saison (§2.6). Sert à basculer en
    # douceur une personne restée connectée sur son ancienne fiche (voir
    # Comptes.fiche_courante et comptes/rbac.py : compte_appelant).
    compte_precedent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comptes.id"), nullable=True, index=True
    )

    nom: Mapped[str] = mapped_column(String(100), nullable=False)
    prenom: Mapped[str] = mapped_column(String(100), nullable=False)
    # Texte libre, sans validation de format (voir §6.4bis : le fichier
    # réel contient des cas qu'une validation stricte rejetterait).
    telephone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Fonctions au bureau de l'association (spec/core.md §6.4) : titres sans
    # aucun droit, voir administrateurs/schemas.py:BUREAU_FUNCTIONS. Recopiées avec la fiche.
    bureau_functions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list, server_default="[]")
    # Emails : table `emails_compte` (plusieurs par fiche, §2.1, décision
    # du 2026-10-16), voir `adresses` et `emails` ci-dessous. Aucun mot de
    # passe ici : il appartient à l'adresse email (table acces_emails,
    # spec §2.2 et §6.3ter).
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

    # Emails de la fiche (§2.1, 2026-10-16) : tous équivalents, aucun
    # « principal ». Toujours écrits par `definir_emails`.
    adresses: Mapped[list["EmailCompte"]] = relationship(
        "EmailCompte",
        back_populates="compte",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="EmailCompte.id",
    )

    @property
    def emails(self) -> list[str]:
        return [a.email for a in self.adresses]

    @property
    def email(self) -> str | None:
        """Pour l'AFFICHAGE seulement (tableaux, exports, schémas d'API) :
        les adresses séparées par une virgule. Jamais pour reconnaître une
        personne : utiliser `emails`."""
        return ", ".join(self.emails) or None

    def a_l_email(self, email: str | None) -> bool:
        from acces import normaliser_email

        email = normaliser_email(email)
        return email is not None and email in self.emails

    def definir_emails(self, emails) -> bool:
        """Remplace les emails de la fiche (ordre et doublons ignorés,
        minuscules). True si quelque chose a changé : il faut alors
        recalculer les familles (Comptes.recalculer_familles)."""
        voulus = separer_emails(emails)
        if voulus == self.emails:
            return False
        gardes = [a for a in self.adresses if a.email in voulus]
        deja = {a.email for a in gardes}
        self.adresses = gardes + [EmailCompte(email=e) for e in voulus if e not in deja]
        return True

    # Lus par les schémas d'API (CompteSortie...), qui exposent à la fois
    # la liste `roles` et un `role` principal pour l'affichage.
    @property
    def noms_roles(self) -> list[str]:
        from .roles import noms_roles

        return noms_roles(self)

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


def separer_emails(valeur) -> list[str]:
    """Une ou plusieurs adresses (liste, ou texte séparé par « ; », « , »
    ou des espaces, comme dans une cellule Excel, §6.4bis) : liste sans
    doublon, en minuscules, dans l'ordre de saisie."""
    import re

    if valeur is None:
        return []
    morceaux = [valeur] if isinstance(valeur, str) else list(valeur)
    resultat: list[str] = []
    for morceau in morceaux:
        for email in re.split(r"[;,\s]+", morceau or ""):
            email = email.strip().lower()
            if email and email not in resultat:
                resultat.append(email)
    return resultat


class EmailCompte(Base):
    """Un email d'une fiche (§6.3, décision du 2026-10-16) : zéro, une ou
    plusieurs lignes par compte. Les fiches qui partagent un email sont de
    la même famille (§6.2) ; chaque email a son mot de passe
    (acces_emails, §6.3ter)."""

    __tablename__ = "emails_compte"
    __table_args__ = (UniqueConstraint("compte_id", "email", name="uq_email_compte"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    compte_id: Mapped[int] = mapped_column(ForeignKey("comptes.id"), nullable=False, index=True)
    # En minuscules (separer_emails).
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    compte: Mapped[Compte] = relationship("Compte", back_populates="adresses")
