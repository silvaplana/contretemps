"""Check of the members' files, the « Nouvel adhérent » notice and their
routes (spec/modules/helloasso.md §7.5). The logic is in checks.py."""

from __future__ import annotations

import threading
from collections.abc import Callable

from comptes import Compte, rbac, roles
from ecoles import Ecole
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from saisons import saison_courante_id
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import SessionLocal, get_db

from . import api, checks
from .campaign import Campaigns
from .connection import Connection
from .contact import SendMail
from .models import HelloAssoRegistration

# push(db, member id, title, text): the core's push notifications.
Push = Callable[[Session, int, str, str], None]


class SettingsIn(BaseModel):
    check_files: bool
    notify_new: bool


class SettingsOut(SettingsIn):
    pass


class RunOut(BaseModel):
    on: bool
    running: bool
    # Files not OK among the current season's members (cancelled left out).
    to_check: int
    # Dollars, all checks of the school (shown in euros).
    cost: float
    can_run: bool


def _club(db: Session, org_id: int) -> str:
    return db.get(Ecole, org_id).nom


def _contact(db: Session, org_id: int) -> str | None:
    return (db.get(Ecole, org_id).email_contact or "").strip() or None


def _admins(db: Session, org_id: int) -> list[Compte]:
    season_id = saison_courante_id(db, org_id)
    members = db.scalars(select(Compte).where(Compte.ecole_id == org_id, Compte.saison_id == season_id))
    return [c for c in members if roles.is_admin(c) or roles.is_owner(c)]


class Checker:
    """Checks files in the school's name: reads them at HelloAsso, calls the
    model, mails the school. Used by the routes and by the synchronisation
    (`Sync.on_new`, in the web app and in the worker)."""

    def __init__(
        self,
        send_mail: SendMail | None,
        push: Push | None,
        eur_per_usd: Callable[[], float] = lambda: 0.9,
        background: bool = True,
    ) -> None:
        self.send_mail = send_mail
        self.push = push
        self.eur_per_usd = eur_per_usd
        # Replaceable in the tests (no network).
        self.fetch_file = api.file
        self.inspector = checks.Inspector()
        self.background = background
        self.runs = checks.Runs(background)

    def _fetch(self, db: Session, org_id: int) -> Callable[[str], bytes]:
        keys = Campaigns._keys(Connection.row(db, org_id))[:2]
        return lambda url: self.fetch_file(*keys, url)[0]

    def check(self, db: Session, r: HelloAssoRegistration):
        return checks.check(db, r, self._fetch(db, r.org_id), self.inspector, _club(db, r.org_id))

    def _mail(self, db: Session, org_id: int, subject: str, text: str) -> None:
        to = _contact(db, org_id)
        if to is None or self.send_mail is None:
            return
        try:
            self.send_mail(db, org_id, to, subject, text, "<br>".join(text.splitlines()))
        except Exception as erreur:  # noqa: BLE001 (the check is kept all the same)
            print(f"HelloAsso, mail de vérification de l'école {org_id} : {erreur}")

    def _in_session(self, db: Session, work: Callable[[Session], None]) -> None:
        """`work` in the background with its own session (web app), or now."""
        if not self.background:
            work(db)
            return

        def run() -> None:
            own = SessionLocal()
            try:
                work(own)
            finally:
                own.close()

        threading.Thread(target=run, daemon=True).start()

    # --- New members (Sync.on_new) ---

    def on_new(self, db: Session, org_id: int, new: list[HelloAssoRegistration]) -> None:
        connection = Connection.row(db, org_id)
        if connection is None:
            return
        if connection.notify_new and self.push is not None:
            names = ", ".join(f"{r.first_name} {r.last_name}".strip() for r in new)
            title = "Nouvel adhérent" if len(new) == 1 else f"{len(new)} nouveaux adhérents"
            for admin in _admins(db, org_id):
                self.push(db, admin.id, title, names)
        if connection.check_files:
            ids = [r.id for r in new]
            self._in_session(db, lambda session: self._check_new(session, org_id, ids))

    def _check_new(self, db: Session, org_id: int, ids: list[int]) -> None:
        """Each new member is checked; a problem is mailed to the school."""
        for registration_id in ids:
            r = db.get(HelloAssoRegistration, registration_id)
            if r is None:
                continue
            found = self.check(db, r)
            db.commit()
            if not checks.is_ok(found):
                self._mail(
                    db, org_id, f"Nouvel adhérent à vérifier : {r.first_name} {r.last_name}",
                    "\n".join([
                        f"Le dossier de {r.first_name} {r.last_name}, nouvel adhérent, est à regarder :",
                        *[f"- {issue}" for issue in found.issues],
                        "",
                        "Il est dans Admin > Élèves, colonne Vérification.",
                    ]),
                )

    # --- « Vérifier les adhérents » ---

    def run(self, db: Session, org_id: int, season_id: int) -> bool:
        """Checks every member whose file is not OK, then mails the report.
        False if a check is already running for this school."""
        ids = [r.id for r in checks.to_check(db, org_id, season_id)]
        if not self.background:
            return self.runs.start(org_id, lambda: self._run(db, org_id, ids))

        def work() -> None:
            own = SessionLocal()
            try:
                self._run(own, org_id, ids)
            finally:
                own.close()

        return self.runs.start(org_id, work)

    def _run(self, db: Session, org_id: int, ids: list[int]) -> None:
        results, cost = [], 0.0
        for registration_id in ids:
            r = db.get(HelloAssoRegistration, registration_id)
            if r is None:
                continue
            previous = checks.row(db, org_id, r.item_id)
            before = previous.cost if previous is not None else 0.0
            found = self.check(db, r)
            db.commit()
            cost += found.cost - before
            results.append(found)
        if results:
            subject, text = checks.report(_club(db, org_id), results, cost, self.eur_per_usd())
            self._mail(db, org_id, subject, text)


class ChecksReceiver:
    def __init__(self, app: FastAPI, checker: Checker, registration) -> None:
        """`registration(db, ecole_id, member_id, appelant)`: the member's
        membership of the shown season, or 404 (HelloAssoReceiver)."""
        self.checker = checker
        self.registration = registration
        app.get("/ecoles/{ecole_id}/helloasso/reglages", response_model=SettingsOut)(self.reglages)
        app.put("/ecoles/{ecole_id}/helloasso/reglages", response_model=SettingsOut)(self.regler)
        app.get("/ecoles/{ecole_id}/helloasso/verification", response_model=RunOut)(self.etat)
        app.post("/ecoles/{ecole_id}/helloasso/verification", response_model=RunOut)(self.verifier)
        app.post("/ecoles/{ecole_id}/helloasso/adherents/{member_id}/valider")(self.valider)
        app.delete("/ecoles/{ecole_id}/helloasso/adherents/{member_id}/valider")(self.devalider)

    @staticmethod
    def _connection(db: Session, ecole_id: int):
        connection = Connection.row(db, ecole_id)
        if connection is None or not connection.active:
            raise HTTPException(status_code=422, detail="HelloAsso n’est pas connecté")
        return connection

    def reglages(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_owner(appelant, ecole_id)
        c = self._connection(db, ecole_id)
        return SettingsOut(check_files=c.check_files, notify_new=c.notify_new)

    def regler(
        self, ecole_id: int, data: SettingsIn, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        """Administrateur principal (spec §7.5)."""
        rbac.require_owner(appelant, ecole_id)
        c = self._connection(db, ecole_id)
        c.check_files, c.notify_new = data.check_files, data.notify_new
        db.commit()
        return SettingsOut(check_files=c.check_files, notify_new=c.notify_new)

    def _state(self, db: Session, ecole_id: int, appelant: Compte) -> RunOut:
        connection = Connection.row(db, ecole_id)
        season_id = saison_courante_id(db, ecole_id)
        on = bool(connection and connection.active and connection.check_files)
        return RunOut(
            on=on,
            running=self.checker.runs.running(ecole_id),
            to_check=len(checks.to_check(db, ecole_id, season_id)) if season_id else 0,
            cost=checks.total_cost(db, ecole_id),
            can_run=on and roles.has_right(appelant, roles.DROIT_FINANCIER),
        )

    def etat(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_admin(appelant, ecole_id)
        return self._state(db, ecole_id, appelant)

    def verifier(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """« Vérifier les adhérents » (Accès au Financier) : la saison en cours."""
        rbac.require_admin(appelant, ecole_id)
        state = self._state(db, ecole_id, appelant)
        if not state.on:
            raise HTTPException(status_code=422, detail="La vérification des dossiers n’est pas allumée")
        if not state.can_run:
            raise HTTPException(status_code=403, detail="Vérifier les adhérents demande l’accès au Financier")
        if not self.checker.run(db, ecole_id, saison_courante_id(db, ecole_id)):
            raise HTTPException(status_code=409, detail="Une vérification est déjà en cours")
        return self._state(db, ecole_id, appelant)

    def valider(
        self, ecole_id: int, member_id: int, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        """« Valider le dossier » (tout admin), défait par DELETE (Annuler 10 s)."""
        found = checks.validate(db, self.registration(db, ecole_id, member_id, appelant), True)
        db.commit()
        return checks.view(found)

    def devalider(
        self, ecole_id: int, member_id: int, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        found = checks.validate(db, self.registration(db, ecole_id, member_id, appelant), False)
        db.commit()
        return checks.view(found)
