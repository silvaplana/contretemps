"""Table `org_helloasso` : la connexion HelloAsso d'une organisation (une
ligne au plus). La clé secrète est chiffrée (securite/chiffrement.py)."""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OrgHelloAsso(Base):
    __tablename__ = "org_helloasso"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, unique=True)
    client_id: Mapped[str] = mapped_column(String(200), nullable=False)
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    # L'association trouvée par le test (nom affiché, slug des appels).
    org_name: Mapped[str] = mapped_column(String(255), nullable=False)
    org_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    # « Déconnecter » garde la ligne (Annuler 10 s) : seulement éteinte.
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_test_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class SeasonHelloAsso(Base):
    """La campagne HelloAsso d'une saison (spec/modules/helloasso.md §3) :
    le formulaire dont les questions sont les champs de la fiche."""

    __tablename__ = "season_helloasso"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), nullable=False, unique=True)
    # Nature HelloAsso (`Membership`, `Event`...) et identifiant du formulaire.
    form_type: Mapped[str] = mapped_column(String(30), nullable=False)
    form_slug: Mapped[str] = mapped_column(String(255), nullable=False)
    form_name: Mapped[str] = mapped_column(String(255), nullable=False)
    chosen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    # Étape 3 (synchronisation).
    synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class HelloAssoRegistration(Base):
    """Un inscrit de la campagne (une ligne de commande HelloAsso) et la
    fiche de la saison qu'il est devenu (spec/modules/helloasso.md §4).
    L'identifiant HelloAsso évite de recopier deux fois ; la formule, le
    code promo et les paiements sont gardés tels que HelloAsso les donne."""

    __tablename__ = "helloasso_registrations"
    __table_args__ = (UniqueConstraint("season_id", "item_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), nullable=False, index=True)
    item_id: Mapped[str] = mapped_column(String(40), nullable=False)
    order_id: Mapped[str] = mapped_column(String(40), nullable=False)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("comptes.id"), nullable=True, index=True)
    first_name: Mapped[str] = mapped_column(String(255), nullable=False)
    last_name: Mapped[str] = mapped_column(String(255), nullable=False)
    payer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tier_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    # Centimes.
    amount: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    discount_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="")
    order_date: Mapped[str | None] = mapped_column(String(40), nullable=True)
    # [{amount (centimes), date, state, means, installment}] : payés ou à venir.
    payments: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    # « Plus sur HelloAsso » : la ligne a disparu ou a été annulée ; la
    # fiche reste, l'admin décide.
    gone_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
