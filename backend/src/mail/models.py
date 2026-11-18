"""Table `mail_accounts` : les boîtes mail d'une organisation (plusieurs
depuis le 18 novembre 2026, spec/modules/mail.md §4 bis). Le mot de passe d'application est chiffré (securite/chiffrement.py).
Aucun mail n'est gardé en base (spec/modules/mail.md §9)."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MailAccount(Base):
    __tablename__ = "mail_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    # Nom court de la boîte (Club, Trésorerie…) : sa puce dans Messages quand
    # l'école en a plusieurs.
    name: Mapped[str] = mapped_column(String(30), nullable=False, default="Club", server_default="Club")
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    # « gmail » ou « infomaniak » (mail/gmail.py, PROVIDERS).
    provider: Mapped[str] = mapped_column(String(20), nullable=False, default="gmail", server_default="gmail")
    app_password_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    # Google a refusé le mot de passe (changé ou révoqué) : bandeau
    # « La boîte mail n'est plus connectée », vidé à la reconnexion.
    cut_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
