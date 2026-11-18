"""La boîte Gmail d'une organisation (spec/modules/mail.md §4) : la
connecter (Google teste le code avant tout enregistrement), la lire, la
déconnecter."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from securite.chiffrement import chiffrer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import gmail
from .models import MailAccount


def normalize_code(code: str) -> str:
    """Google affiche le code en quatre groupes : « abcd efgh ijkl mnop »."""
    return "".join(code.split())


class Connection:
    def __init__(self, check: Callable[[str, str], None] = gmail.check) -> None:
        # Remplaçable dans les tests (pas d'appel réseau).
        self.check = check

    @staticmethod
    def account(db: Session, org_id: int) -> MailAccount | None:
        return db.scalar(select(MailAccount).where(MailAccount.organization_id == org_id))

    def connect(self, db: Session, org_id: int, address: str, code: str) -> MailAccount:
        """Teste chez Google puis enregistre (remplace l'ancienne boîte)."""
        address, password = address.strip(), normalize_code(code)
        self.check(address, password)
        account = self.account(db, org_id) or MailAccount(organization_id=org_id)
        account.address, account.app_password_encrypted = address, chiffrer(password)
        account.connected_at, account.cut_at = datetime.now(timezone.utc), None
        db.add(account)
        db.commit()
        return account

    def disconnect(self, db: Session, org_id: int) -> None:
        """Efface l'adresse et le code (l'Annuler de 10 s est à l'écran)."""
        account = self.account(db, org_id)
        if account is not None:
            db.delete(account)
            db.commit()
