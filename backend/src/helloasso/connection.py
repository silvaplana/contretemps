"""La connexion HelloAsso d'une organisation (spec/modules/helloasso.md §2) :
tester des clés, les enregistrer (clé secrète chiffrée), retester,
déconnecter et annuler la déconnexion. Rien ne part vers HelloAsso à part
la demande de jeton et les lectures."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from securite.chiffrement import chiffrer, dechiffrer
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import api
from .models import OrgHelloAsso


def _maintenant() -> datetime:
    return datetime.now(timezone.utc)


class Connection:
    def __init__(self, connect: Callable[[str, str], api.Organization] = api.connect) -> None:
        # Remplaçable dans les tests (pas d'appel réseau).
        self.connect = connect

    @staticmethod
    def row(db: Session, org_id: int) -> OrgHelloAsso | None:
        return db.scalar(select(OrgHelloAsso).where(OrgHelloAsso.org_id == org_id))

    def current(self, db: Session, org_id: int) -> OrgHelloAsso | None:
        """La connexion en service, ou None."""
        ligne = self.row(db, org_id)
        return ligne if ligne is not None and ligne.active else None

    def test(self, client_id: str, client_secret: str) -> api.Organization:
        return self.connect(client_id.strip(), client_secret.strip())

    def save(self, db: Session, org_id: int, client_id: str, client_secret: str) -> api.Organization:
        """Reteste les clés puis les enregistre (remplace les anciennes)."""
        organisation = self.test(client_id, client_secret)
        ligne = self.row(db, org_id) or OrgHelloAsso(org_id=org_id)
        ligne.client_id, ligne.secret_encrypted = client_id.strip(), chiffrer(client_secret.strip())
        ligne.org_name, ligne.org_slug = organisation.name, organisation.slug
        ligne.connected_at, ligne.active = _maintenant(), True
        ligne.last_test_at, ligne.last_test_ok = _maintenant(), True
        db.add(ligne)
        db.commit()
        return organisation

    def retest(self, db: Session, org_id: int) -> api.Organization:
        """« Tester la connexion » avec les clés enregistrées."""
        ligne = self.current(db, org_id)
        if ligne is None:
            raise api.HelloAssoError("HelloAsso n’est pas connecté.")
        secret = dechiffrer(ligne.secret_encrypted)
        if secret is None:
            raise api.HelloAssoError("Les clés enregistrées ne se lisent plus : changez les clés.")
        ligne.last_test_at = _maintenant()
        try:
            organisation = self.connect(ligne.client_id, secret)
        except api.HelloAssoError:
            ligne.last_test_ok = False
            db.commit()
            raise
        ligne.last_test_ok = True
        ligne.org_name = organisation.name
        db.commit()
        return organisation

    def set_active(self, db: Session, org_id: int, active: bool) -> None:
        """Déconnecter (et Annuler) : ne touche ni aux membres ni aux paiements."""
        ligne = self.row(db, org_id)
        if ligne is None:
            raise LookupError(org_id)
        ligne.active = active
        db.commit()
