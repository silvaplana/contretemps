"""Routes of the FFST module (spec/modules/ffst.md). The club login:
Administrateur principal and Super User. The lists and the members' FFST
status: every admin of the school."""

from __future__ import annotations

from datetime import datetime

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db

from . import site
from .club import Club, _school_town


class LoginIn(BaseModel):
    part1: str = Field(min_length=1, max_length=20)
    part2: str = Field(min_length=1, max_length=20)
    part3: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=200)

    def login(self) -> site.Login:
        return site.Login(self.part1.strip(), self.part2.strip(), self.part3.strip(), self.password)


class SettingsIn(BaseModel):
    discipline: str = Field(default="", max_length=60)
    default_birth_town: str = Field(default="", max_length=100)
    image_rights: bool = True


class StatusOut(BaseModel):
    connected: bool
    # « 21 / 13 / 1230 »: the login, never the password.
    login: str | None = None
    connected_at: datetime | None = None
    settings: SettingsIn | None = None
    # The school's town, used when the default birth town is empty.
    school_town: str | None = None


class RequestIn(BaseModel):
    fonction: str = Field(default=site.PRATIQUANT, max_length=60)
    # « H » or « F », chosen on screen when HelloAsso has no gender.
    gender: str | None = Field(default=None, max_length=10)


class RequestOut(BaseModel):
    warnings: list[str] = []


class TestOut(BaseModel):
    licensees: int


class ListsOut(BaseModel):
    connected: bool
    # None: never read.
    read_at: datetime | None = None
    # {licensees, validated, drafts}: rows as read on the site.
    lists: dict[str, list[dict]] = {}
    # The site did not answer: the previous copy is shown.
    error: str | None = None


class MembersOut(BaseModel):
    connected: bool
    read_at: datetime | None = None
    # {member card: {status}}.
    members: dict[int, dict] = {}


def _unprocessable(error: site.FfstError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(error))


class FfstReceiver:
    def __init__(self, club: Club, app: FastAPI) -> None:
        self.club = club
        owner = [Depends(self._owner)]
        admin = [Depends(self._admin)]
        app.get("/ecoles/{ecole_id}/ffst", response_model=StatusOut, dependencies=owner)(self.etat)
        app.post("/ecoles/{ecole_id}/ffst/tester", response_model=TestOut, dependencies=owner)(self.tester)
        app.post("/ecoles/{ecole_id}/ffst/retester", response_model=TestOut, dependencies=owner)(self.retester)
        app.put("/ecoles/{ecole_id}/ffst", response_model=TestOut, dependencies=owner)(self.enregistrer)
        app.get("/ecoles/{ecole_id}/ffst/listes", response_model=ListsOut, dependencies=admin)(self.listes)
        app.post("/ecoles/{ecole_id}/ffst/lire", response_model=ListsOut, dependencies=admin)(self.lire)
        app.get("/ecoles/{ecole_id}/ffst/adherents", response_model=MembersOut, dependencies=admin)(self.adherents)
        app.put("/ecoles/{ecole_id}/ffst/reglages", response_model=StatusOut, dependencies=owner)(self.reglages)
        app.get("/ecoles/{ecole_id}/ffst/fonctions", response_model=list[str], dependencies=admin)(self.fonctions)
        app.post(
            "/ecoles/{ecole_id}/ffst/adherents/{member_id}/demande", response_model=RequestOut, dependencies=admin
        )(self.demander)
        app.delete(
            "/ecoles/{ecole_id}/ffst/adherents/{member_id}/demande", status_code=204, dependencies=admin
        )(self.retirer)

    def _owner(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_owner(appelant, ecole_id)

    def _admin(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    # --- The club login (spec §2) ---

    def etat(self, ecole_id: int, db: Session = Depends(get_db)):
        row = self.club.row(db, ecole_id)
        if row is None:
            return StatusOut(connected=False)
        login = f"{row.login_part1} / {row.login_part2} / {row.login_part3}"
        settings = SettingsIn(
            discipline=row.discipline, default_birth_town=row.default_birth_town, image_rights=row.image_rights
        )
        return StatusOut(
            connected=True,
            login=login,
            connected_at=row.connected_at,
            settings=settings,
            school_town=_school_town(db, ecole_id),
        )

    def reglages(self, ecole_id: int, data: SettingsIn, db: Session = Depends(get_db)):
        row = self.club.row(db, ecole_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Le site de la FFST n’est pas connecté.")
        row.discipline, row.default_birth_town = data.discipline.strip(), data.default_birth_town.strip()
        row.image_rights = data.image_rights
        db.commit()
        return self.etat(ecole_id, db)

    def tester(self, ecole_id: int, data: LoginIn):
        try:
            return TestOut(licensees=self.club.test(data.login()))
        except site.FfstError as error:
            raise _unprocessable(error) from None

    def retester(self, ecole_id: int, db: Session = Depends(get_db)):
        try:
            return TestOut(licensees=self.club.retest(db, ecole_id))
        except site.FfstError as error:
            raise _unprocessable(error) from None

    def enregistrer(self, ecole_id: int, data: LoginIn, db: Session = Depends(get_db)):
        try:
            count = self.club.save(db, ecole_id, data.login())
        except site.FfstError as error:
            raise _unprocessable(error) from None
        # First reading right away: the FFST tab opens filled.
        try:
            self.club.refresh(db, ecole_id)
        except site.FfstError:
            pass
        return TestOut(licensees=count)

    # --- The three lists (spec §3) ---

    def _lists_out(self, db: Session, ecole_id: int, error: str | None = None) -> ListsOut:
        if self.club.row(db, ecole_id) is None:
            return ListsOut(connected=False)
        lists, read_at = self.club.lists(db, ecole_id)
        return ListsOut(connected=True, read_at=read_at, lists=lists, error=error)

    def listes(self, ecole_id: int, db: Session = Depends(get_db)):
        return self._lists_out(db, ecole_id)

    def lire(self, ecole_id: int, db: Session = Depends(get_db)):
        """« Rafraîchir »: reads the site again; if it fails, the previous copy
        comes back with the error."""
        if self.club.row(db, ecole_id) is None:
            return ListsOut(connected=False)
        try:
            self.club.refresh(db, ecole_id)
        except site.FfstError as error:
            db.rollback()
            return self._lists_out(db, ecole_id, error=str(error))
        return self._lists_out(db, ecole_id)

    # --- Column « Statut FFST » of the members table (spec §4) ---

    def adherents(self, ecole_id: int, db: Session = Depends(get_db)):
        if self.club.row(db, ecole_id) is None:
            return MembersOut(connected=False)
        lists, read_at = self.club.lists(db, ecole_id)
        people = db.execute(select(Compte.id, Compte.nom, Compte.prenom).where(Compte.ecole_id == ecole_id)).all()
        statuses = self.club.statuses(lists, [tuple(p) for p in people])
        known = self.club.gender_known(db, ecole_id, list(statuses))
        return MembersOut(
            connected=True,
            read_at=read_at,
            members={
                member_id: {"status": status, "gender_known": known[member_id]}
                for member_id, status in statuses.items()
            },
        )

    # --- Actions FFST (spec §5): a real browser, up to 30 seconds ---

    def fonctions(self, ecole_id: int):
        return site.FONCTIONS

    def demander(self, ecole_id: int, member_id: int, data: RequestIn, db: Session = Depends(get_db)):
        if self.club.row(db, ecole_id) is None:
            raise HTTPException(status_code=404, detail="Le site de la FFST n’est pas connecté.")
        try:
            return RequestOut(warnings=self.club.request(db, ecole_id, member_id, data.fonction, data.gender))
        except LookupError:
            raise HTTPException(status_code=404, detail="Fiche introuvable") from None
        except site.FfstError as error:
            db.rollback()
            raise _unprocessable(error) from None

    def retirer(self, ecole_id: int, member_id: int, db: Session = Depends(get_db)):
        if self.club.row(db, ecole_id) is None:
            raise HTTPException(status_code=404, detail="Le site de la FFST n’est pas connecté.")
        try:
            self.club.remove(db, ecole_id, member_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Fiche introuvable") from None
        except site.FfstError as error:
            db.rollback()
            raise _unprocessable(error) from None
