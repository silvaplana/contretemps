"""Table `drive_accounts` : les drives d'une organisation (spec/core.md §3).
Le mot de passe d'application kDrive est chiffré (securite/chiffrement.py).
Aucun fichier n'est gardé en base."""

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DriveAccount(Base):
    __tablename__ = "drive_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False, index=True)
    # Nom court (Club, Trésorerie…) : ce qui le désigne dans l'appli.
    name: Mapped[str] = mapped_column(String(30), nullable=False, default="Club", server_default="Club")
    # « kdrive » ou « gdrive » (providers.py).
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    # Adresse Infomaniak ou Google du club.
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    # kDrive : numéro du kDrive (dans son adresse) ; Google Drive : vide.
    drive_ref: Mapped[str] = mapped_column(String(50), nullable=False, default="", server_default="")
    # kDrive : mot de passe d'application ; Google Drive : vide (clé du serveur).
    secret_encrypted: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    connected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    # Le drive a refusé l'accès : « à reconnecter », vidé à la reconnexion.
    cut_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
