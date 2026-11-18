"""Tables du module Essai (spec/modules/essai.md §7), préfixées `trial_`,
toutes rattachées à une organisation. Pas de `saison_id` : un élève à
l'essai n'est pas un membre de la saison."""

from datetime import date, datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TrialTerms(Base):
    """Une version des textes acceptés (décharge, autorisation parentale) :
    chaque inscription garde la sienne (§5)."""

    __tablename__ = "trial_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    waiver: Mapped[str] = mapped_column(Text, nullable=False)
    parental_consent: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)


class TrialSettings(Base):
    """La page d'essai de l'école (§5). Pas de ligne : les textes par défaut."""

    __tablename__ = "trial_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subtitle: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    intro: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Listes : règles (texte), horaires {day, time, course, place}, salles
    # {name, address}, contacts {name, phone}.
    rules: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    min_age: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    schedule: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    places: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    contacts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    certificate_hint: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    terms_id: Mapped[int] = mapped_column(ForeignKey("trial_terms.id"), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)


class TrialStudent(Base):
    """Un élève à l'essai. Le certificat médical n'est jamais gardé (§6) :
    seulement la date à laquelle il a été fourni."""

    __tablename__ = "trial_students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Âge d'un mineur ; None pour un majeur.
    age: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    parent_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Les personnes inscrites dans la même demande partagent ce numéro.
    family: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Contenu du QR code, tiré au hasard.
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    terms_id: Mapped[int] = mapped_column(ForeignKey("trial_terms.id"), nullable=False)
    waiver_accepted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    certificate_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    # Les deux cours d'essai : date et façon de les noter (« qr » ou « manual »).
    course1_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    course1_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    course2_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    course2_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)


class TrialSignature(Base):
    """La signature au doigt d'une demande : la 1re personne majeure, ou un
    parent (elle vaut alors autorisation parentale)."""

    __tablename__ = "trial_signatures"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    signer_name: Mapped[str] = mapped_column(String(200), nullable=False)
    # Les enfants pour qui cette signature vaut autorisation parentale.
    children: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    png: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    terms_id: Mapped[int] = mapped_column(ForeignKey("trial_terms.id"), nullable=False)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
