"""Routes du module Essai (spec/modules/essai.md) : la page publique (sans
compte, `/trials/public/...`, listées dans comptes/rbac.py ROUTES_PUBLIQUES)
et Admin > Essais (administrateurs de l'école)."""

from __future__ import annotations

import base64
import threading
import time
from datetime import date, datetime

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field
from registry.activation import disabled
from sqlalchemy.orm import Session

from db import get_db
from ecoles.models import Ecole

from . import content
from .trials import Person, Registration, RegistrationError, TrialError, Trials

MODULE_KEY = "trials"
# Page publique : 10 demandes par heure au plus depuis la même connexion.
RATE_LIMIT, RATE_WINDOW = 10, 3600


class RateLimiter:
    def __init__(self, limit: int, window: int) -> None:
        self.limit, self.window = limit, window
        self.calls: dict[str, list[float]] = {}
        self.lock = threading.Lock()

    def allow(self, key: str) -> bool:
        now = time.time()
        with self.lock:
            recent = [t for t in self.calls.get(key, []) if t > now - self.window]
            if len(recent) >= self.limit:
                self.calls[key] = recent
                return False
            self.calls[key] = [*recent, now]
            return True


class SlotIO(BaseModel):
    day: str = ""
    time: str = ""
    course: str = ""
    place: str = ""


class PlaceIO(BaseModel):
    name: str = ""
    address: str = ""


class ContactIO(BaseModel):
    name: str = ""
    phone: str = ""


class SettingsIO(BaseModel):
    title: str = Field(max_length=200)
    subtitle: str = Field("", max_length=300)
    intro: str = ""
    rules: list[str] = []
    min_age: int
    schedule: list[SlotIO] = []
    places: list[PlaceIO] = []
    contacts: list[ContactIO] = []
    certificate_hint: str = Field("", max_length=300)
    waiver: str
    parental_consent: str


class SettingsOut(SettingsIO):
    terms_id: int
    terms_number: int
    link: str


class PublicPageOut(SettingsOut):
    club: str
    privacy: str


class StudentOut(BaseModel):
    id: int
    first_name: str
    last_name: str
    age: int | None
    email: str
    phone: str | None
    parent_name: str | None
    comment: str
    created_at: datetime
    certificate_at: datetime | None
    course1_date: date | None
    course1_mode: str | None
    course2_date: date | None
    course2_mode: str | None
    # Déjà élève de l'école (même prénom et nom) : caché par « Pas encore adhérents ».
    member: bool = False


class SignatureOut(BaseModel):
    signer_name: str
    children: list[str]
    created_at: datetime
    png: str  # data:image/png;base64,…


class StudentCardOut(StudentOut):
    terms_number: int
    waiver: str
    parental_consent: str
    family: list[str]
    signatures: list[SignatureOut]


class StudentIn(BaseModel):
    first_name: str | None = Field(None, max_length=100)
    last_name: str | None = Field(None, max_length=100)
    age: int | None = None
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=40)
    parent_name: str | None = Field(None, max_length=200)
    comment: str | None = None
    course1_date: date | None = None
    course2_date: date | None = None


class RegisteredOut(BaseModel):
    first_name: str
    last_name: str
    status: str
    qr: str  # data:image/png;base64,…


class RegistrationOut(BaseModel):
    people: list[RegisteredOut]


def _data_url(png: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(png).decode()


def _student_out(row, member: bool = False) -> StudentOut:
    return StudentOut(**{k: getattr(row, k) for k in StudentOut.model_fields if k != "member"}, member=member)


class TrialsReceiver:
    def __init__(self, client: Trials, app: FastAPI) -> None:
        self.client = client
        self.limiter = RateLimiter(RATE_LIMIT, RATE_WINDOW)
        app.get("/trials/public/orgs/{org_id}/page", response_model=PublicPageOut)(self.public_page)
        app.post("/trials/public/orgs/{org_id}/registrations", response_model=RegistrationOut, status_code=201)(
            self.register
        )
        admin = [Depends(self._admin)]
        base = "/ecoles/{ecole_id}/trials"
        app.get(f"{base}/settings", response_model=SettingsOut, dependencies=admin)(self.get_settings)
        app.put(f"{base}/settings", response_model=SettingsOut, dependencies=admin)(self.put_settings)
        app.get(f"{base}/students", response_model=list[StudentOut], dependencies=admin)(self.students)
        app.get(f"{base}/students/{{student_id}}", response_model=StudentCardOut, dependencies=admin)(self.student)
        app.patch(f"{base}/students/{{student_id}}", response_model=StudentOut, dependencies=admin)(self.update)
        app.delete(f"{base}/students/{{student_id}}", status_code=204, dependencies=admin)(self.remove)
        app.post(f"{base}/students/{{student_id}}/courses", response_model=StudentOut, dependencies=admin)(
            self.add_course
        )

    def _admin(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    # --- Réglages ---

    def _settings_out(self, db: Session, org_id: int) -> SettingsOut:
        row = self.client.settings(db, org_id)
        terms = self.client.terms(db, row.terms_id)
        return SettingsOut(
            title=row.title,
            subtitle=row.subtitle,
            intro=row.intro,
            rules=row.rules,
            min_age=row.min_age,
            schedule=row.schedule,
            places=row.places,
            contacts=row.contacts,
            certificate_hint=row.certificate_hint,
            waiver=terms.waiver,
            parental_consent=terms.parental_consent,
            terms_id=terms.id,
            terms_number=terms.number,
            link=f"{self.client.school_address(db.get(Ecole, org_id))}/essai",
        )

    def get_settings(self, ecole_id: int, db: Session = Depends(get_db)):
        return self._settings_out(db, ecole_id)

    def put_settings(self, ecole_id: int, data: SettingsIO, db: Session = Depends(get_db)):
        try:
            self.client.save_settings(db, ecole_id, data.model_dump())
        except TrialError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        return self._settings_out(db, ecole_id)

    # --- Page publique ---

    def _open(self, db: Session, org_id: int) -> Ecole:
        """La page n'existe que si le module est allumé dans l'école."""
        ecole = db.get(Ecole, org_id)
        if ecole is None or MODULE_KEY in disabled(db, org_id):
            raise HTTPException(status_code=404, detail="Page introuvable")
        return ecole

    def public_page(self, org_id: int, db: Session = Depends(get_db)):
        ecole = self._open(db, org_id)
        return PublicPageOut(**self._settings_out(db, org_id).model_dump(), club=ecole.nom, privacy=content.PRIVACY)

    async def register(self, org_id: int, request: Request, db: Session = Depends(get_db)):
        self._open(db, org_id)
        forwarded = request.headers.get("x-forwarded-for", "")
        ip = forwarded.split(",")[0].strip() or (request.client.host if request.client else None)
        if not self.limiter.allow(ip or "?"):
            raise HTTPException(status_code=429, detail="Trop de demandes : réessayez dans une heure")
        form = await request.form()

        def text(key: str) -> str:
            value = form.get(key)
            return value if isinstance(value, str) else ""

        async def file(key: str):
            value = form.get(key)
            if value is None or isinstance(value, str):
                return None
            return value.filename or "fichier", await value.read()

        people = []
        for i in range(3):
            if not text(f"first_name_{i}") and not text(f"last_name_{i}"):
                continue
            age = text(f"age_{i}")
            people.append(
                Person(
                    first_name=text(f"first_name_{i}"),
                    last_name=text(f"last_name_{i}"),
                    minor=text(f"minor_{i}") == "true",
                    age=int(age) if age.isdigit() else None,
                    parent_is_first=text(f"parent_is_first_{i}") == "true",
                    parent_first_name=text(f"parent_first_name_{i}"),
                    parent_last_name=text(f"parent_last_name_{i}"),
                    waiver_accepted=text(f"waiver_{i}") == "true",
                    certificate=await file(f"certificate_{i}"),
                )
            )
        signatures = {}
        for k in range(4):
            name, png = text(f"signature_name_{k}"), await file(f"signature_{k}")
            if name and png:
                signatures[name] = png[1]
        terms_id = text("terms_id")
        registration = Registration(
            email=text("email"), people=people, signatures=signatures, terms_id=int(terms_id) if terms_id.isdigit() else None
        )
        try:
            result = self.client.register(db, org_id, registration, ip=ip)
        except RegistrationError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        return RegistrationOut(
            people=[
                RegisteredOut(first_name=p["first_name"], last_name=p["last_name"], status=p["status"], qr=_data_url(p["qr_png"]))
                for p in result["people"]
            ]
        )

    # --- Admin > Essais ---

    def students(self, ecole_id: int, db: Session = Depends(get_db)):
        return [_student_out(row, member) for row, member in self.client.students(db, ecole_id)]

    def student(self, ecole_id: int, student_id: int, db: Session = Depends(get_db)):
        try:
            row, signatures, family, terms = self.client.student(db, ecole_id, student_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Inscrit introuvable") from None
        return StudentCardOut(
            **_student_out(row).model_dump(),
            terms_number=terms.number,
            waiver=terms.waiver,
            parental_consent=terms.parental_consent,
            family=[f"{f.first_name} {f.last_name}" for f in family],
            signatures=[
                SignatureOut(signer_name=s.signer_name, children=s.children, created_at=s.created_at, png=_data_url(s.png))
                for s in signatures
            ],
        )

    def update(self, ecole_id: int, student_id: int, data: StudentIn, db: Session = Depends(get_db)):
        try:
            row = self.client.update(db, ecole_id, student_id, data.model_dump(exclude_unset=True))
        except LookupError:
            raise HTTPException(status_code=404, detail="Inscrit introuvable") from None
        except TrialError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        return _student_out(row)

    def remove(self, ecole_id: int, student_id: int, db: Session = Depends(get_db)):
        try:
            self.client.remove(db, ecole_id, student_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Inscrit introuvable") from None

    def add_course(self, ecole_id: int, student_id: int, db: Session = Depends(get_db)):
        try:
            row = self.client.add_course(db, ecole_id, student_id)
        except LookupError:
            raise HTTPException(status_code=404, detail="Inscrit introuvable") from None
        except TrialError as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from None
        return _student_out(row)
