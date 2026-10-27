"""Routes de la connexion HelloAsso (spec/modules/helloasso.md §2),
réservées à l'Administrateur principal et au Super User de l'école."""

from __future__ import annotations

from datetime import datetime

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException, Response
from pydantic import BaseModel, Field
from saisons import saison_courante_id
from saisons.portee import saison_demandee
from sqlalchemy.orm import Session

from db import get_db

from .api import HelloAssoError, Organization
from .campaign import Campaigns
from .connection import Connection
from .sync import Sync


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


class FormOut(BaseModel):
    form_type: str
    form_slug: str
    name: str
    state: str = ""


class CampaignOut(BaseModel):
    connected: bool
    # Administrateur principal et Super User, saison courante.
    can_change: bool = False
    form: FormOut | None = None
    forms: list[FormOut] = []
    # HelloAsso n'a pas répondu : la campagne choisie reste affichée.
    error: str | None = None
    synced_at: datetime | None = None
    # Tout admin synchronise la saison en cours.
    can_sync: bool = False


class SyncOut(BaseModel):
    created: int
    completed: int
    updated: int
    gone: int


class CampaignIn(BaseModel):
    form_type: str = Field(min_length=1, max_length=30)
    form_slug: str = Field(min_length=1, max_length=255)


def _out(organisation: Organization) -> OrganizationOut:
    return OrganizationOut(name=organisation.name, forms=organisation.forms)


class HelloAssoReceiver:
    def __init__(
        self, client: Connection, app: FastAPI, campaigns: Campaigns | None = None, sync: Sync | None = None
    ) -> None:
        self.client = client
        self.campaigns = campaigns or Campaigns()
        self.sync = sync
        app.post("/ecoles/{ecole_id}/helloasso/synchroniser", response_model=SyncOut)(self.synchroniser)
        owner = [Depends(self._owner)]
        app.get("/ecoles/{ecole_id}/helloasso/campagne", response_model=CampaignOut)(self.campagne)
        app.put("/ecoles/{ecole_id}/helloasso/campagne", response_model=CampaignOut, dependencies=owner)(
            self.choisir
        )
        app.delete("/ecoles/{ecole_id}/helloasso/campagne", status_code=204, dependencies=owner)(self.nos_champs)
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

    # --- La campagne de la saison (spec §3) ---

    @staticmethod
    def _courante(db: Session, ecole_id: int) -> int:
        """Choisir une campagne : la saison courante seulement."""
        courante = saison_courante_id(db, ecole_id)
        demandee = saison_demandee()
        if courante is None or (demandee is not None and demandee != courante):
            raise HTTPException(status_code=403, detail="Seule la saison en cours se modifie")
        return courante

    def campagne(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_admin(appelant, ecole_id)
        if self.client.current(db, ecole_id) is None:
            return CampaignOut(connected=False)
        season_id = saison_demandee() or saison_courante_id(db, ecole_id)
        try:
            rbac.require_owner(appelant, ecole_id)
            can_change = season_id == saison_courante_id(db, ecole_id)
        except HTTPException:
            can_change = False
        current = self.campaigns.current(db, season_id)
        out = CampaignOut(
            connected=True,
            can_change=can_change,
            form=FormOut(form_type=current.form_type, form_slug=current.form_slug, name=current.form_name)
            if current
            else None,
            synced_at=current.synced_at if current else None,
            can_sync=current is not None and season_id == saison_courante_id(db, ecole_id),
        )
        if can_change:
            try:
                out.forms = [FormOut(**vars(f)) for f in self.campaigns.list_forms(db, ecole_id)]
            except HelloAssoError as erreur:
                out.error = str(erreur)
        return out

    def choisir(
        self, ecole_id: int, data: CampaignIn, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        season_id = self._courante(db, ecole_id)
        try:
            self.campaigns.choose(db, ecole_id, season_id, data.form_type, data.form_slug)
        except (HelloAssoError, ValueError) as erreur:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        db.commit()
        return self.campagne(ecole_id, db, appelant)

    def nos_champs(self, ecole_id: int, db: Session = Depends(get_db)):
        self.campaigns.clear(db, ecole_id, self._courante(db, ecole_id))
        db.commit()
        return Response(status_code=204)

    def synchroniser(
        self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)
    ):
        """« Synchroniser maintenant » : tout admin, saison en cours."""
        rbac.require_admin(appelant, ecole_id)
        self._courante(db, ecole_id)
        try:
            return SyncOut(**vars(self.sync.run(db, ecole_id)))
        except HelloAssoError as erreur:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(erreur)) from None
