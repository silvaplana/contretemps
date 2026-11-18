"""Routes de la connexion HelloAsso (spec/modules/helloasso.md §2),
réservées à l'Administrateur principal et au Super User de l'école."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field
from saisons import Saison, saison_courante_id
from saisons.portee import saison_demandee
from sqlalchemy.orm import Session

from db import get_db

from . import api
from . import members as imposed_members
from .api import HelloAssoError, Organization
from .campaign import MASTER, Campaigns
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


class PlanOut(BaseModel):
    name: str
    price: int | None = None
    min_amount: int | None = None
    description: str = ""
    frequency: str = ""


class OptionOut(BaseModel):
    name: str
    price: int
    required: bool


class CodeOut(BaseModel):
    code: str
    uses: int


class PricesOut(BaseModel):
    # False : pas de campagne cette saison, l'écran Tarifs montre les nôtres.
    campaign: bool
    form_name: str | None = None
    plans: list[PlanOut] = []
    options: list[OptionOut] = []
    codes: list[CodeOut] = []
    error: str | None = None


class SyncOut(BaseModel):
    created: int
    completed: int
    updated: int
    gone: int


class MemberRowOut(BaseModel):
    # Centimes.
    amount: int
    discount_code: str | None = None
    state: str
    cancelled: bool
    photo: bool


class MembersOut(BaseModel):
    # La saison affichée a une campagne : adhérents imposés par HelloAsso
    # (spec §7), le tableau perd « + », l'import et la corbeille.
    imposed: bool
    form_name: str | None = None
    # « Rafraîchir » : la saison en cours seulement.
    can_refresh: bool = False
    # {fiche: colonnes HelloAsso}.
    members: dict[int, MemberRowOut] = {}


class FileOut(BaseModel):
    index: int
    name: str


class AnswerOut(BaseModel):
    name: str
    answer: str | int | float | bool | None = None


class MemberCardOut(BaseModel):
    tier_name: str
    amount: int
    discount_code: str | None = None
    state: str
    cancelled: bool
    order_date: str | None = None
    photo: bool
    files: list[FileOut]
    answers: list[AnswerOut]
    payer_name: str | None = None
    payer_email: str | None = None
    payments: list[dict]


class SeasonOut(BaseModel):
    """Le choix de la saison affichée (spec §8.1)."""

    connected: bool
    # `master` « HelloAsso fait tout », `payment` « L'appli fait tout,
    # HelloAsso encaisse », `none` « Sans HelloAsso ».
    mode: str = "none"
    season_name: str | None = None
    # Administrateur principal et Super User, saison en cours.
    can_change: bool = False
    form: FormOut | None = None


class SeasonIn(BaseModel):
    # « HelloAsso fait tout » se choisit avec sa campagne (PUT …/campagne).
    mode: Literal["payment", "none"]


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
        # Remplaçable dans les tests (pas d'appel réseau).
        self.fetch_file = api.file
        app.get("/ecoles/{ecole_id}/helloasso/adherents", response_model=MembersOut)(self.adherents)
        app.get("/ecoles/{ecole_id}/helloasso/adherents/{member_id}", response_model=MemberCardOut)(self.adherent)
        app.get("/ecoles/{ecole_id}/helloasso/adherents/{member_id}/photo")(self.photo)
        app.get("/ecoles/{ecole_id}/helloasso/adherents/{member_id}/fichiers/{index}")(self.fichier)
        app.post("/ecoles/{ecole_id}/helloasso/synchroniser", response_model=SyncOut)(self.synchroniser)
        app.get("/ecoles/{ecole_id}/helloasso/tarifs", response_model=PricesOut)(self.tarifs)
        owner = [Depends(self._owner)]
        app.get("/ecoles/{ecole_id}/helloasso/campagne", response_model=CampaignOut)(self.campagne)
        app.put("/ecoles/{ecole_id}/helloasso/campagne", response_model=CampaignOut, dependencies=owner)(
            self.choisir
        )
        app.delete("/ecoles/{ecole_id}/helloasso/campagne", status_code=204, dependencies=owner)(self.nos_champs)
        app.get("/ecoles/{ecole_id}/helloasso/saison", response_model=SeasonOut)(self.saison)
        app.put("/ecoles/{ecole_id}/helloasso/saison", response_model=SeasonOut, dependencies=owner)(
            self.choisir_saison
        )
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

    def saison(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """Comment la saison affichée utilise HelloAsso (tout admin le lit)."""
        rbac.require_admin(appelant, ecole_id)
        if self.client.current(db, ecole_id) is None:
            return SeasonOut(connected=False)
        season_id = saison_demandee() or saison_courante_id(db, ecole_id)
        row = self.campaigns.row(db, season_id) if season_id else None
        season = db.get(Saison, season_id) if season_id else None
        try:
            rbac.require_owner(appelant, ecole_id)
            can_change = season_id is not None and season_id == saison_courante_id(db, ecole_id)
        except HTTPException:
            can_change = False
        return SeasonOut(
            connected=True,
            mode=row.mode if row is not None else "none",
            season_name=season.nom if season else None,
            can_change=can_change,
            form=FormOut(form_type=row.form_type, form_slug=row.form_slug, name=row.form_name)
            if row is not None and row.mode == MASTER
            else None,
        )

    def choisir_saison(
        self, ecole_id: int, data: SeasonIn, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        """« L'appli fait tout, HelloAsso encaisse » ou « Sans HelloAsso »
        pour la saison en cours ; la campagne éventuelle est retirée."""
        season_id = self._courante(db, ecole_id)
        if self.client.current(db, ecole_id) is None:
            raise HTTPException(status_code=422, detail="HelloAsso n’est pas connecté")
        self.campaigns.set_payment(db, ecole_id, season_id, data.mode == "payment")
        db.commit()
        return self.saison(ecole_id, db, appelant)

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

    def tarifs(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """Les tarifs HelloAsso de la saison affichée, en lecture seule (tout admin)."""
        rbac.require_admin(appelant, ecole_id)
        season_id = saison_demandee() or saison_courante_id(db, ecole_id)
        current = self.campaigns.current(db, season_id)
        if current is None:
            return PricesOut(campaign=False)
        try:
            return PricesOut(campaign=True, **self.campaigns.prices(db, ecole_id, season_id))
        except HelloAssoError as erreur:
            return PricesOut(campaign=True, form_name=current.form_name, error=str(erreur))

    # --- Adhérents imposés par HelloAsso (spec §7.2, §7.3) : tout admin ---

    def adherents(
        self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)
    ):
        rbac.require_admin(appelant, ecole_id)
        season_id = saison_demandee() or saison_courante_id(db, ecole_id)
        current = self.campaigns.current(db, season_id) if season_id else None
        if current is None:
            return MembersOut(imposed=False)
        return MembersOut(
            imposed=True,
            form_name=current.form_name,
            can_refresh=season_id == saison_courante_id(db, ecole_id),
            members=imposed_members.table(db, ecole_id, season_id),
        )

    def _registration(self, db: Session, ecole_id: int, member_id: int, appelant: Compte):
        rbac.require_admin(appelant, ecole_id)
        season_id = saison_demandee() or saison_courante_id(db, ecole_id)
        registration = imposed_members.registration(db, ecole_id, season_id, member_id) if season_id else None
        if registration is None:
            raise HTTPException(status_code=404, detail="Pas d’adhésion HelloAsso pour cette fiche")
        return registration

    def adherent(
        self, ecole_id: int, member_id: int, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        return imposed_members.card(self._registration(db, ecole_id, member_id, appelant))

    def _file(self, db: Session, ecole_id: int, url: str) -> tuple[bytes, str]:
        connection = self.client.current(db, ecole_id)
        if connection is None:
            raise HTTPException(status_code=422, detail="HelloAsso n’est pas connecté")
        try:
            return self.fetch_file(*Campaigns._keys(connection)[:2], url)
        except HelloAssoError as erreur:
            raise HTTPException(status_code=502, detail=str(erreur)) from None

    def photo(
        self, ecole_id: int, member_id: int, size: int = Query(default=128, ge=32, le=640),
        db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant),
    ):
        """La vignette de la photo d'identité, gardée sur le disque (elle ne
        change pas) ; 404 sans photo."""
        registration = self._registration(db, ecole_id, member_id, appelant)
        index = imposed_members.photo_index(registration.answers)
        if index is None:
            raise HTTPException(status_code=404, detail="Pas de photo")
        url = registration.answers[index]["answer"]
        path = imposed_members.thumbnail_path(ecole_id, url, size)
        if path.exists():
            content = path.read_bytes()
        else:
            try:
                content = imposed_members.thumbnail(self._file(db, ecole_id, url)[0], size)
            except HTTPException:
                raise
            except Exception:
                raise HTTPException(status_code=422, detail="Cette photo ne se lit pas") from None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return Response(content=content, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=86400"})

    def fichier(
        self, ecole_id: int, member_id: int, index: int, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        """Un document déposé sur HelloAsso (certificat médical…), lu chez
        HelloAsso à chaque demande, jamais enregistré (spec §7.3)."""
        registration = self._registration(db, ecole_id, member_id, appelant)
        answers = registration.answers or []
        if not 0 <= index < len(answers) or not imposed_members.is_file_url(answers[index].get("answer")):
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        content, mime = self._file(db, ecole_id, answers[index]["answer"])
        return Response(content=content, media_type=mime, headers={"Cache-Control": "no-store"})
