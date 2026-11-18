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
from .club import Club


class LoginIn(BaseModel):
    part1: str = Field(min_length=1, max_length=20)
    part2: str = Field(min_length=1, max_length=20)
    part3: str = Field(min_length=1, max_length=20)
    password: str = Field(min_length=1, max_length=200)

    def login(self) -> site.Login:
        return site.Login(self.part1.strip(), self.part2.strip(), self.part3.strip(), self.password)


class StatusOut(BaseModel):
    connected: bool
    # « 21 / 13 / 1230 »: the login, never the password.
    login: str | None = None
    connected_at: datetime | None = None


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
        return StatusOut(connected=True, login=login, connected_at=row.connected_at)

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
        return MembersOut(
            connected=True,
            read_at=read_at,
            members={member_id: {"status": status} for member_id, status in statuses.items()},
        )
