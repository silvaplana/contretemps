"""Routes de la boîte mail de l'école (spec/modules/mail.md §3 et §4).
Lire l'état : droit « Boîte mail du club ». Connecter et déconnecter :
l'Administrateur principal qui a ce droit (et le Super User)."""

from __future__ import annotations

from datetime import datetime

from comptes import Compte, rbac, roles
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from .connection import Connection
from .gmail import MailError, MailRefused

RIGHT = "mail.read"


class ConnectIn(BaseModel):
    address: str = Field(min_length=3, max_length=255, pattern=r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$")
    code: str = Field(min_length=1, max_length=100)


class StatusOut(BaseModel):
    connected: bool
    address: str | None = None
    connected_at: datetime | None = None
    # Google a coupé l'accès : bandeau « Reconnecter ».
    cut: bool = False
    # Administrateur principal (ou Super User) : connecter, déconnecter.
    can_connect: bool = False


def _reader(ecole_id: int, appelant: Compte | None = Depends(rbac.compte_appelant)) -> None:
    rbac.require_membre(appelant, ecole_id)
    if appelant is not None and not roles.has_right(appelant, RIGHT):
        raise HTTPException(status_code=403, detail="Réservé aux personnes qui ont le droit « Boîte mail du club »")


def _owner(ecole_id: int, appelant: Compte | None = Depends(rbac.compte_appelant)) -> None:
    _reader(ecole_id, appelant)
    if appelant is not None:
        rbac.require_owner(appelant, ecole_id)


def _can_connect(appelant: Compte | None) -> bool:
    return appelant is None or roles.is_superuser(appelant) or roles.is_owner(appelant)


class MailReceiver:
    def __init__(self, connection: Connection, app: FastAPI) -> None:
        self.connection = connection
        app.get("/ecoles/{ecole_id}/mail", response_model=StatusOut, dependencies=[Depends(_reader)])(self.status)
        owner = [Depends(_owner)]
        app.put("/ecoles/{ecole_id}/mail", response_model=StatusOut, dependencies=owner)(self.connect)
        app.delete("/ecoles/{ecole_id}/mail", status_code=204, dependencies=owner)(self.disconnect)

    def _status(self, db: Session, ecole_id: int, appelant: Compte | None) -> StatusOut:
        account = self.connection.account(db, ecole_id)
        if account is None:
            return StatusOut(connected=False, can_connect=_can_connect(appelant))
        return StatusOut(
            connected=True, address=account.address, connected_at=account.connected_at,
            cut=account.cut_at is not None, can_connect=_can_connect(appelant),
        )

    def status(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte | None = Depends(rbac.compte_appelant)):
        return self._status(db, ecole_id, appelant)

    def connect(
        self, ecole_id: int, data: ConnectIn, db: Session = Depends(get_db),
        appelant: Compte | None = Depends(rbac.compte_appelant),
    ):
        try:
            self.connection.connect(db, ecole_id, data.address, data.code)
        except MailRefused as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        except MailError as erreur:
            raise HTTPException(status_code=502, detail=str(erreur)) from None
        return self._status(db, ecole_id, appelant)

    def disconnect(self, ecole_id: int, db: Session = Depends(get_db)):
        self.connection.disconnect(db, ecole_id)
