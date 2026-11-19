"""Les drives d'une organisation (spec/core.md §3) : connecter (le drive est
essayé avant tout enregistrement), renommer, déconnecter, et ouvrir un
client pour les modules qui lisent ou écrivent (`core.drives`)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from securite.chiffrement import chiffrer, dechiffrer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import DriveAccount
from .providers import DriveError, DriveRefused, GoogleDrive, KDrive, service_account

PROVIDERS = {"kdrive": "kDrive", "gdrive": "Google Drive"}


class NotConnected(Exception):
    """Pas de drive, ou coupé : rien à lire."""


def open_client(provider: str, address: str, secret: str, drive_ref: str):
    if provider == "kdrive":
        return KDrive(address, secret, drive_ref)
    key = service_account()
    if key is None:
        raise DriveError("Google Drive n'est pas encore proposé sur ce serveur.")
    return GoogleDrive(key)


def google_address() -> str | None:
    """L'adresse avec laquelle le club partage ses dossiers Google."""
    key = service_account()
    return key.get("client_email") if key else None


class Drives:
    def __init__(self, factory: Callable[[str, str, str, str], object] = open_client) -> None:
        # Remplaçable dans les tests (pas d'appel réseau).
        self.factory = factory

    @staticmethod
    def accounts(db: Session, org_id: int) -> list[DriveAccount]:
        query = select(DriveAccount).where(DriveAccount.organization_id == org_id).order_by(DriveAccount.id)
        return list(db.scalars(query))

    @staticmethod
    def account(db: Session, org_id: int, drive: int) -> DriveAccount | None:
        return db.scalar(
            select(DriveAccount).where(DriveAccount.organization_id == org_id, DriveAccount.id == drive)
        )

    def connect(
        self, db: Session, org_id: int, provider: str, address: str, code: str = "", drive_ref: str = "",
        drive: int | None = None, name: str = "",
    ) -> DriveAccount:
        """Essaie le drive puis enregistre. `drive` : remplace ou reconnecte
        ce drive ; sinon en ajoute un."""
        address, code, drive_ref = address.strip(), code.strip(), drive_ref.strip()
        self.factory(provider, address, code, drive_ref).check()
        if drive is not None:
            account = self.account(db, org_id, drive)
            if account is None:
                raise NotConnected()
        else:
            existing = self.accounts(db, org_id)
            default = "Club" if not existing else f"Drive {len(existing) + 1}"
            account = DriveAccount(organization_id=org_id, name=name.strip() or default)
        if name.strip():
            account.name = name.strip()
        account.provider, account.address, account.drive_ref = provider, address, drive_ref
        account.secret_encrypted = chiffrer(code) if code else ""
        account.connected_at, account.cut_at = datetime.now(timezone.utc), None
        db.add(account)
        db.commit()
        return account

    def rename(self, db: Session, org_id: int, drive: int, name: str) -> None:
        account = self.account(db, org_id, drive)
        if account is None:
            raise NotConnected()
        account.name = name.strip()
        db.commit()

    def disconnect(self, db: Session, org_id: int, drive: int) -> None:
        account = self.account(db, org_id, drive)
        if account is not None:
            db.delete(account)
            db.commit()

    def mark_cut(self, db: Session, org_id: int, drive: int) -> None:
        account = self.account(db, org_id, drive)
        if account is not None and account.cut_at is None:
            account.cut_at = datetime.now(timezone.utc)
            db.commit()

    def client(self, db: Session, org_id: int, drive: int):
        """Le client d'un drive de l'école (NotConnected sinon), pour les
        modules : `list(path)`, `read(path)`, `write(folder, name, content,
        mime)`. Un refus du drive le marque coupé (`call`)."""
        account = self.account(db, org_id, drive)
        if account is None or account.cut_at is not None:
            raise NotConnected()
        secret = dechiffrer(account.secret_encrypted) if account.secret_encrypted else ""
        if secret is None:  # secret du serveur changé : il faut reconnecter
            self.mark_cut(db, org_id, drive)
            raise NotConnected()
        return self.factory(account.provider, account.address, secret, account.drive_ref)

    def call(self, db: Session, org_id: int, drive: int, action: Callable[[object], object]):
        """`action(client)` ; un refus marque le drive coupé et remonte."""
        try:
            return action(self.client(db, org_id, drive))
        except DriveRefused:
            self.mark_cut(db, org_id, drive)
            raise
