"""Routes des drives du club (spec/core.md §3, « Drives du club »).
Connecter, renommer, déconnecter : Administrateur principal ou Super User
(Admin › École › Connexions). Parcourir les dossiers d'un drive : eux, et
les personnes qui ont l'Accès au Financier (Importation automatique de pièces). Routes
synchrones (réseau bloquant) : FastAPI les exécute dans un thread à part."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from comptes import Compte, rbac, roles
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from .providers import DriveError, DriveNotFound, DriveRefused
from .service import Drives, NotConnected, google_address


class ConnectIn(BaseModel):
    provider: Literal["kdrive", "gdrive"]
    address: str = Field(min_length=3, max_length=255, pattern=r"^\s*[^@\s]+@[^@\s]+\.[^@\s]+\s*$")
    # kDrive : mot de passe d'application et numéro du kDrive.
    code: str = Field("", max_length=200)
    drive_ref: str = Field("", max_length=50, pattern=r"^\s*\d*\s*$")
    name: str = Field("", max_length=30)


class RenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)


class DriveOut(BaseModel):
    id: int
    name: str
    provider: str
    address: str
    connected_at: datetime
    cut: bool


class StatusOut(BaseModel):
    connected: bool
    can_connect: bool
    # Adresse avec laquelle partager un dossier Google ; None : Google Drive
    # pas encore proposé sur ce serveur (pas de clé).
    google_address: str | None = None
    drives: list[DriveOut] = []


class EntryOut(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int
    modified: datetime | None


def _can_connect(appelant: Compte | None) -> bool:
    return appelant is None or roles.is_superuser(appelant) or roles.is_owner(appelant)


def _owner(ecole_id: int, appelant: Compte | None = Depends(rbac.compte_appelant)) -> None:
    rbac.require_membre(appelant, ecole_id)
    if appelant is not None and not roles.is_superuser(appelant):
        rbac.require_owner(appelant, ecole_id)


def _reader(ecole_id: int, appelant: Compte | None = Depends(rbac.compte_appelant)) -> None:
    rbac.require_membre(appelant, ecole_id)
    if not (_can_connect(appelant) or roles.has_right(appelant, roles.DROIT_FINANCIER)):
        raise HTTPException(status_code=403, detail="Réservé à l'Administrateur principal et au Financier")


def drive_http_error(erreur: Exception) -> HTTPException:
    if isinstance(erreur, NotConnected):
        return HTTPException(status_code=409, detail="Ce drive n'est pas connecté")
    if isinstance(erreur, DriveNotFound):
        return HTTPException(status_code=404, detail=str(erreur))
    if isinstance(erreur, DriveRefused):
        return HTTPException(status_code=409, detail=str(erreur))
    return HTTPException(status_code=502, detail=str(erreur))


class DrivesReceiver:
    def __init__(self, drives: Drives, app: FastAPI) -> None:
        self.drives = drives
        base = "/ecoles/{ecole_id}/drives"
        owner, reader = [Depends(_owner)], [Depends(_reader)]
        app.get(base, response_model=StatusOut, dependencies=reader)(self.status)
        app.put(base, response_model=StatusOut, dependencies=owner)(self.connect)
        app.patch(base, response_model=StatusOut, dependencies=owner)(self.rename)
        app.delete(base, status_code=204, dependencies=owner)(self.disconnect)
        app.get(f"{base}/{{drive}}/list", response_model=list[EntryOut], dependencies=reader)(self.list)

    def _status(self, db: Session, ecole_id: int, appelant: Compte | None) -> StatusOut:
        drives = [
            DriveOut(id=a.id, name=a.name, provider=a.provider, address=a.address, connected_at=a.connected_at,
                     cut=a.cut_at is not None)
            for a in self.drives.accounts(db, ecole_id)
        ]
        return StatusOut(connected=bool(drives), can_connect=_can_connect(appelant),
                         google_address=google_address(), drives=drives)

    def status(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte | None = Depends(rbac.compte_appelant)):
        return self._status(db, ecole_id, appelant)

    def connect(
        self, ecole_id: int, data: ConnectIn, drive: int | None = None, db: Session = Depends(get_db),
        appelant: Compte | None = Depends(rbac.compte_appelant),
    ):
        """Sans `drive` : ajoute un drive ; avec : le reconnecte ou le remplace."""
        if data.provider == "kdrive" and not (data.code.strip() and data.drive_ref.strip()):
            raise HTTPException(status_code=422, detail="Il faut le mot de passe d'application et le numéro du kDrive")
        try:
            self.drives.connect(db, ecole_id, data.provider, data.address, data.code, data.drive_ref, drive, data.name)
        except NotConnected:
            raise HTTPException(status_code=404, detail="Drive introuvable") from None
        except DriveRefused as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        except DriveError as erreur:
            raise HTTPException(status_code=502, detail=str(erreur)) from None
        return self._status(db, ecole_id, appelant)

    def rename(
        self, ecole_id: int, drive: int, data: RenameIn, db: Session = Depends(get_db),
        appelant: Compte | None = Depends(rbac.compte_appelant),
    ):
        try:
            self.drives.rename(db, ecole_id, drive, data.name)
        except NotConnected:
            raise HTTPException(status_code=404, detail="Drive introuvable") from None
        return self._status(db, ecole_id, appelant)

    def disconnect(self, ecole_id: int, drive: int, db: Session = Depends(get_db)):
        self.drives.disconnect(db, ecole_id, drive)

    def list(self, ecole_id: int, drive: int, path: str = "", db: Session = Depends(get_db)):
        try:
            entries = self.drives.call(db, ecole_id, drive, lambda c: c.list(path))
        except (NotConnected, DriveError) as erreur:
            raise drive_http_error(erreur) from None
        return [EntryOut(**e.__dict__) for e in entries]
