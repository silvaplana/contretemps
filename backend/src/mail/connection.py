"""La boîte mail (Gmail ou Infomaniak) d'une organisation (spec/modules/mail.md §4) : la
connecter (Google teste le code avant tout enregistrement), la lire, la
déconnecter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from securite.chiffrement import chiffrer, dechiffrer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import gmail
from .imap import Webmail
from .models import MailAccount


class NotConnected(Exception):
    """Pas de boîte, ou coupée par Google : rien à lire."""


def normalize_code(code: str) -> str:
    """Google affiche le code en quatre groupes : « abcd efgh ijkl mnop ».
    Sans espaces aussi pour Infomaniak : le client IMAP les retire (imap.py)."""
    return "".join(code.split())


def open_webmail(address: str, password: str, provider: str) -> Webmail:
    p = gmail.PROVIDERS[provider]
    return Webmail(address, password, imap_host=p.imap_host, smtp_host=p.smtp_host)


class Connection:
    """Les boîtes d'une école (plusieurs depuis le 18 novembre 2026, §4 bis).
    `box` : le numéro d'une boîte ; absent, la première connectée."""

    def __init__(
        self,
        check: Callable[[str, str, str], None] = gmail.check,
        webmail: Callable[[str, str, str], Webmail] = open_webmail,
    ) -> None:
        # Remplaçables dans les tests (pas d'appel réseau).
        self.check = check
        self.webmail = webmail
        # Un client par boîte, gardé tant qu'elle ne change pas : il retient
        # les noms des dossiers Gmail (10 min, voir imap.py).
        self._clients: dict[int, tuple[tuple[str, str, str], Webmail]] = {}

    @staticmethod
    def accounts(db: Session, org_id: int) -> list[MailAccount]:
        query = select(MailAccount).where(MailAccount.organization_id == org_id).order_by(MailAccount.id)
        return list(db.scalars(query))

    @staticmethod
    def account(db: Session, org_id: int, box: int | None = None) -> MailAccount | None:
        query = select(MailAccount).where(MailAccount.organization_id == org_id)
        if box is not None:
            query = query.where(MailAccount.id == box)
        return db.scalar(query.order_by(MailAccount.id).limit(1))

    def connect(
        self, db: Session, org_id: int, address: str, code: str, provider: str = "gmail",
        box: int | None = None, name: str = "",
    ) -> MailAccount:
        """Teste chez le fournisseur puis enregistre. `box` : remplace ou
        reconnecte cette boîte ; sinon ajoute une boîte (ou reconnecte celle
        qui a la même adresse)."""
        address, password = address.strip(), normalize_code(code)
        self.check(address, password, provider)
        if box is not None:
            account = self.account(db, org_id, box)
            if account is None:
                raise NotConnected()
        else:
            existing = self.accounts(db, org_id)
            account = next((a for a in existing if a.address.lower() == address.lower()), None)
            if account is None:
                default = "Club" if not existing else f"Boîte {len(existing) + 1}"
                account = MailAccount(organization_id=org_id, name=name.strip() or default)
        if name.strip():
            account.name = name.strip()
        account.address, account.app_password_encrypted = address, chiffrer(password)
        account.provider = provider
        account.connected_at, account.cut_at = datetime.now(timezone.utc), None
        db.add(account)
        db.commit()
        self._clients.pop(account.id, None)
        return account

    def rename(self, db: Session, org_id: int, box: int, name: str) -> None:
        account = self.account(db, org_id, box)
        if account is None:
            raise NotConnected()
        account.name = name.strip()
        db.commit()

    def client(self, db: Session, org_id: int, box: int | None = None) -> Webmail:
        """Le client IMAP d'une boîte de l'école (NotConnected sinon)."""
        account = self.account(db, org_id, box)
        if account is None or account.cut_at is not None:
            raise NotConnected()
        password = dechiffrer(account.app_password_encrypted)
        if password is None:  # secret du serveur changé : il faut reconnecter
            self.mark_cut(db, org_id, account.id)
            raise NotConnected()
        key = (account.address, password, account.provider)
        cached = self._clients.get(account.id)
        if cached is None or cached[0] != key:
            cached = (key, self.webmail(account.address, password, account.provider))
            self._clients[account.id] = cached
        return cached[1]

    def mark_cut(self, db: Session, org_id: int, box: int | None = None) -> None:
        """Le fournisseur a refusé le code : bandeau « Reconnecter » (§4)."""
        account = self.account(db, org_id, box)
        if account is not None and account.cut_at is None:
            account.cut_at = datetime.now(timezone.utc)
            db.commit()

    def disconnect(self, db: Session, org_id: int, box: int | None = None) -> None:
        """Efface l'adresse et le code (l'Annuler de 10 s est à l'écran)."""
        account = self.account(db, org_id, box)
        if account is not None:
            self._clients.pop(account.id, None)
            db.delete(account)
            db.commit()
