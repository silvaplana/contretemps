"""Routes de la connexion HelloAsso (spec/modules/helloasso.md §2),
réservées à l'Administrateur principal et au Super User de l'école."""

from __future__ import annotations

from datetime import datetime

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from .api import HelloAssoError, Organization
from .connection import Connection


class KeysIn(BaseModel):
    client_id: str = Field(min_length=1, max_length=200)
    client_secret: str = Field(min_length=1, max_length=500)


class OrganizationOut(BaseModel):
    name: str
    forms: list[str]


class StatusOut(BaseModel):
    connected: bool
    org_name: str | None = None
    connected_at: datetime | None = None


def _out(organisation: Organization) -> OrganizationOut:
    return OrganizationOut(name=organisation.name, forms=organisation.forms)


class HelloAssoReceiver:
    def __init__(self, client: Connection, app: FastAPI) -> None:
        self.client = client
        owner = [Depends(self._owner)]
        app.get("/ecoles/{ecole_id}/helloasso", response_model=StatusOut, dependencies=owner)(self.etat)
        app.post("/ecoles/{ecole_id}/helloasso/tester", response_model=OrganizationOut, dependencies=owner)(
            self.tester
        )
        app.post("/ecoles/{ecole_id}/helloasso/retester", response_model=OrganizationOut, dependencies=owner)(
            self.retester
        )
        app.put("/ecoles/{ecole_id}/helloasso", response_model=OrganizationOut, dependencies=owner)(
            self.enregistrer
        )
        app.delete("/ecoles/{ecole_id}/helloasso", status_code=204, dependencies=owner)(self.deconnecter)
        app.post("/ecoles/{ecole_id}/helloasso/reprendre", status_code=204, dependencies=owner)(self.reprendre)

    def _owner(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_owner(appelant, ecole_id)

    def etat(self, ecole_id: int, db: Session = Depends(get_db)):
        ligne = self.client.current(db, ecole_id)
        if ligne is None:
            return StatusOut(connected=False)
        return StatusOut(connected=True, org_name=ligne.org_name, connected_at=ligne.connected_at)

    def tester(self, ecole_id: int, data: KeysIn):
        try:
            return _out(self.client.test(data.client_id, data.client_secret))
        except HelloAssoError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None

    def retester(self, ecole_id: int, db: Session = Depends(get_db)):
        try:
            return _out(self.client.retest(db, ecole_id))
        except HelloAssoError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None

    def enregistrer(self, ecole_id: int, data: KeysIn, db: Session = Depends(get_db)):
        try:
            return _out(self.client.save(db, ecole_id, data.client_id, data.client_secret))
        except HelloAssoError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None

    def deconnecter(self, ecole_id: int, db: Session = Depends(get_db)):
        try:
            self.client.set_active(db, ecole_id, False)
        except LookupError:
            raise HTTPException(status_code=404, detail="HelloAsso n’est pas connecté") from None

    def reprendre(self, ecole_id: int, db: Session = Depends(get_db)):
        try:
            self.client.set_active(db, ecole_id, True)
        except LookupError:
            raise HTTPException(status_code=404, detail="HelloAsso n’est pas connecté") from None
