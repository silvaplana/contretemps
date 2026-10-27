"""Table `org_helloasso` : la connexion HelloAsso d'une organisation (une
ligne au plus). La clé secrète est chiffrée (securite/chiffrement.py)."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
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
