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
    def __init__(
        self,
        check: Callable[[str, str, str], None] = gmail.check,
        webmail: Callable[[str, str, str], Webmail] = open_webmail,
    ) -> None:
        # Remplaçables dans les tests (pas d'appel réseau).
        self.check = check
        self.webmail = webmail
        # Un client par école, gardé tant que la boîte ne change pas : il
        # retient les noms des dossiers Gmail (10 min, voir imap.py).
        self._clients: dict[int, tuple[tuple[str, str, str], Webmail]] = {}

    @staticmethod
    def account(db: Session, org_id: int) -> MailAccount | None:
        return db.scalar(select(MailAccount).where(MailAccount.organization_id == org_id))

    def connect(self, db: Session, org_id: int, address: str, code: str, provider: str = "gmail") -> MailAccount:
        """Teste chez le fournisseur puis enregistre (remplace l'ancienne boîte)."""
        address, password = address.strip(), normalize_code(code)
        self.check(address, password, provider)
        account = self.account(db, org_id) or MailAccount(organization_id=org_id)
        account.address, account.app_password_encrypted = address, chiffrer(password)
        account.provider = provider
        account.connected_at, account.cut_at = datetime.now(timezone.utc), None
        db.add(account)
        db.commit()
        self._clients.pop(org_id, None)
        return account

    def client(self, db: Session, org_id: int) -> Webmail:
        """Le client IMAP de la boîte de l'école (NotConnected sinon)."""
        account = self.account(db, org_id)
        if account is None or account.cut_at is not None:
            raise NotConnected()
        password = dechiffrer(account.app_password_encrypted)
        if password is None:  # secret du serveur changé : il faut reconnecter
            self.mark_cut(db, org_id)
            raise NotConnected()
        key = (account.address, password, account.provider)
        cached = self._clients.get(org_id)
        if cached is None or cached[0] != key:
            cached = (key, self.webmail(account.address, password, account.provider))
            self._clients[org_id] = cached
        return cached[1]

    def mark_cut(self, db: Session, org_id: int) -> None:
        """Google a refusé le code : bandeau « Reconnecter » (§4)."""
        account = self.account(db, org_id)
        if account is not None and account.cut_at is None:
            account.cut_at = datetime.now(timezone.utc)
            db.commit()

    def disconnect(self, db: Session, org_id: int) -> None:
        """Efface l'adresse et le code (l'Annuler de 10 s est à l'écran)."""
        account = self.account(db, org_id)
        if account is not None:
            db.delete(account)
            db.commit()
        self._clients.pop(org_id, None)
