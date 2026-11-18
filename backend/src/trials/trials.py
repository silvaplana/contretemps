"""Le module Essai (spec/modules/essai.md), repris de Sambo Admin
(silvaplana/test-python, backend/src/trials/) : page publique d'inscription,
mail avec un QR code par personne, liste des élèves à l'essai, deux cours
au plus, suppression au bout d'un an.

Écart voulu (Seb, 18/11/2026, §6) : le certificat médical n'est jamais
gardé. Il est seulement joint au mail de confirmation (copie à l'email de
contact de l'école), puis oublié.
"""

from __future__ import annotations

import io
import re
import secrets
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pillow_heif
import segno
from PIL import Image, ImageOps
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ecoles.models import Ecole

from . import content
from .emails import confirmation_email
from .models import TrialSettings, TrialSignature, TrialStudent, TrialTerms

pillow_heif.register_heif_opener()

PARIS = ZoneInfo("Europe/Paris")
MAX_PEOPLE = 3
MAX_COURSES = 2
ADULT_AGE = 18
RETENTION_DAYS = 365
MAX_CERTIFICATE_BYTES = 15_000_000
MAX_SIGNATURE_BYTES = 500_000
# Pièces jointes du mail, au total (les certificats, réduits).
MAX_ATTACHMENTS_BYTES = 10_000_000
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


class RegistrationError(ValueError):
    """Inscription refusée : le message s'affiche tel quel sur la page publique."""


class TrialError(ValueError):
    """Action refusée dans Admin > Essais : message affiché tel quel."""


@dataclass
class Person:
    first_name: str
    last_name: str
    minor: bool = False
    age: int | None = None
    parent_is_first: bool = False
    parent_first_name: str = ""
    parent_last_name: str = ""
    waiver_accepted: bool = False
    # (nom du fichier, contenu) ; jamais enregistré.
    certificate: tuple[str, bytes] | None = None

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class Registration:
    email: str
    people: list[Person]
    # {nom du signataire: image PNG}
    signatures: dict[str, bytes] = field(default_factory=dict)
    terms_id: int | None = None


def today() -> date:
    """La date du jour à Paris (pas celle du serveur, en UTC)."""
    return datetime.now(PARIS).date()


def normalize(text: str | None) -> str:
    """« Léa  Martin » -> « lea martin »."""
    decomposed = unicodedata.normalize("NFD", " ".join((text or "").split()))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def expected_signers(people: list[Person]) -> dict[str, list[str]]:
    """Qui signe, et pour quels enfants (autorisation parentale) : la 1re
    personne si elle est majeure ; chaque parent extérieur ; un majeur de la
    famille quand la 1re personne est mineure. Un seul signataire par nom.
    La page publique fait le même calcul (PageEssai.jsx)."""
    signers: dict[str, list[str]] = {}
    keys: dict[str, str] = {}

    def add(name: str, child: str | None) -> None:
        key = normalize(name)
        if key not in keys:
            keys[key] = name
            signers[name] = []
        if child:
            signers[keys[key]].append(child)

    first = people[0]
    if not first.minor:
        add(first.name, None)
    for i, p in enumerate(people):
        if p.minor and i > 0 and p.parent_is_first:
            add(first.name, p.name)
        elif p.minor:
            add(f"{p.parent_first_name} {p.parent_last_name}".strip(), p.name)
        elif not first.minor or i == 0:
            continue
        else:
            add(p.name, None)
    return signers


def certificate_attachment(name: str, filename: str, data: bytes) -> tuple[str, bytes]:
    """Le certificat prêt pour le mail : PDF tel quel ; photo tournée,
    réduite à 2000 px et mise en JPEG (les photos d'iPhone, HEIC, ne
    s'ouvrent pas partout)."""
    if len(data) > MAX_CERTIFICATE_BYTES:
        raise RegistrationError("Certificat trop volumineux (15 Mo au plus)")
    plain = "".join(c for c in unicodedata.normalize("NFD", name) if not unicodedata.combining(c))
    slug = re.sub(r"[^A-Za-z0-9-]+", "-", plain).strip("-") or "eleve"
    if data.startswith(b"%PDF"):
        return f"certificat-{slug}.pdf", data
    try:
        image = ImageOps.exif_transpose(Image.open(io.BytesIO(data)))
        image.thumbnail((2000, 2000))
        buffer = io.BytesIO()
        image.convert("RGB").save(buffer, format="JPEG", quality=85)
    except Exception as exc:  # noqa: BLE001 (tout fichier illisible)
        raise RegistrationError("Certificat illisible : envoyez une photo ou un PDF") from exc
    return f"certificat-{slug}.jpg", buffer.getvalue()


def qr_png(url: str) -> bytes:
    buffer = io.BytesIO()
    segno.make(url, error="m").save(buffer, kind="png", scale=10, border=4)
    return buffer.getvalue()


class Trials:
    def __init__(
        self,
        send: Callable[..., None],
        school_address: Callable[[Ecole], str],
        member_names: Callable[[Session, int], set[str]] = lambda db, org_id: set(),
    ) -> None:
        # send(to, subject, text, html, attachments, images, copy, reply_to, sender)
        self.send = send
        self.school_address = school_address
        # Noms normalisés (« prenom nom ») des élèves de l'école : la puce
        # « Pas encore adhérents ».
        self.member_names = member_names

    # --- Réglages (§5) ---

    def settings(self, db: Session, org_id: int) -> TrialSettings:
        """La page d'essai de l'école ; créée avec les textes par défaut la
        première fois."""
        row = db.scalar(select(TrialSettings).where(TrialSettings.org_id == org_id))
        if row is not None:
            return row
        terms = TrialTerms(org_id=org_id, number=1, waiver=content.WAIVER, parental_consent=content.PARENTAL_CONSENT)
        db.add(terms)
        db.flush()
        row = TrialSettings(
            org_id=org_id,
            title=content.TITLE,
            subtitle="",
            intro=content.INTRO,
            rules=list(content.RULES),
            min_age=content.MIN_AGE,
            schedule=[],
            places=[],
            contacts=[],
            certificate_hint=content.CERTIFICATE_HINT,
            terms_id=terms.id,
        )
        db.add(row)
        db.commit()
        return row

    def terms(self, db: Session, terms_id: int) -> TrialTerms:
        return db.get(TrialTerms, terms_id)

    def save_settings(self, db: Session, org_id: int, data: dict) -> TrialSettings:
        row = self.settings(db, org_id)
        if not (data.get("title") or "").strip():
            raise TrialError("Le titre est obligatoire")
        if not 3 <= int(data.get("min_age") or 0) <= 17:
            raise TrialError("L'âge minimum va de 3 à 17 ans")
        for key in ("title", "subtitle", "intro", "certificate_hint"):
            setattr(row, key, (data.get(key) or "").strip())
        row.min_age = int(data["min_age"])
        row.rules = [r.strip() for r in data.get("rules") or [] if r.strip()]
        row.schedule = [s for s in data.get("schedule") or [] if any((v or "").strip() for v in s.values())]
        row.places = [p for p in data.get("places") or [] if (p.get("name") or "").strip()]
        row.contacts = [c for c in data.get("contacts") or [] if (c.get("phone") or "").strip()]
        current = self.terms(db, row.terms_id)
        waiver = (data.get("waiver") or "").strip()
        consent = (data.get("parental_consent") or "").strip()
        if not waiver or not consent:
            raise TrialError("La décharge et l'autorisation parentale sont obligatoires")
        if (waiver, consent) != (current.waiver, current.parental_consent):
            # Nouvelle version : les inscriptions faites gardent la leur.
            terms = TrialTerms(org_id=org_id, number=current.number + 1, waiver=waiver, parental_consent=consent)
            db.add(terms)
            db.flush()
            row.terms_id = terms.id
        db.commit()
        return row

    # --- Inscription publique (§2, §3, §6) ---

    def _validate(self, settings: TrialSettings, reg: Registration) -> None:
        if not 1 <= len(reg.people) <= MAX_PEOPLE:
            raise RegistrationError(f"De 1 à {MAX_PEOPLE} personnes par demande")
        if not EMAIL_PATTERN.match(reg.email):
            raise RegistrationError("Adresse e-mail invalide")
        if reg.terms_id != settings.terms_id:
            raise RegistrationError("La page a changé entre-temps : rechargez-la puis recommencez")
        for i, p in enumerate(reg.people):
            if not p.first_name.strip() or not p.last_name.strip():
                raise RegistrationError("Prénom et nom sont obligatoires pour chaque personne")
            if p.minor:
                if p.age is None or not settings.min_age <= p.age < ADULT_AGE:
                    raise RegistrationError(
                        f"Âge de {p.name} : les mineurs sont accueillis à partir de {settings.min_age} ans"
                    )
                if i > 0 and p.parent_is_first:
                    if reg.people[0].minor:
                        raise RegistrationError(f"Le parent de {p.name} doit être majeur")
                elif not p.parent_first_name.strip() or not p.parent_last_name.strip():
                    raise RegistrationError(f"Prénom et nom du parent de {p.name} sont obligatoires")
            if not p.waiver_accepted:
                raise RegistrationError(f"Merci d'accepter la décharge pour {p.name}")
            if p.certificate is None:
                raise RegistrationError(f"Merci de joindre le certificat médical de {p.name}")
        given = {normalize(name): png for name, png in reg.signatures.items()}
        for name in expected_signers(reg.people):
            png = given.get(normalize(name))
            if png is None:
                raise RegistrationError(f"Merci de faire signer {name}")
            if not png.startswith(PNG_MAGIC) or len(png) > MAX_SIGNATURE_BYTES:
                raise RegistrationError(f"Signature de {name} illisible, recommencez")

    def register(self, db: Session, org_id: int, reg: Registration, ip: str | None = None) -> dict:
        """Enregistre la demande et envoie le mail. Le mail est envoyé avant
        d'enregistrer : s'il ne part pas, rien n'est gardé (§6).
        Rend {"people": [{first_name, last_name, status, qr_png}]}, où
        status vaut « created » ou « existing » (déjà inscrit : même QR code)."""
        ecole = db.get(Ecole, org_id)
        settings = self.settings(db, org_id)
        reg.email = reg.email.strip().lower()
        for p in reg.people:
            p.first_name, p.last_name = p.first_name.strip(), p.last_name.strip()
        self._validate(settings, reg)
        if not ecole.email_contact:
            raise RegistrationError("Inscription impossible pour le moment : contactez le club par téléphone")

        attachments, total = [], 0
        for p in reg.people:
            name, data = certificate_attachment(p.name, *p.certificate)
            total += len(data)
            if total > MAX_ATTACHMENTS_BYTES:
                raise RegistrationError("Certificats trop lourds : envoyez des photos plus petites")
            attachments.append((name, data))

        now = datetime.now(timezone.utc)
        family = secrets.token_hex(8)
        existing_rows = db.scalars(
            select(TrialStudent).where(TrialStudent.org_id == org_id, TrialStudent.email == reg.email)
        ).all()
        rows, statuses = [], []
        for p in reg.people:
            row = next((r for r in existing_rows if normalize(r.first_name + " " + r.last_name) == normalize(p.name)), None)
            if row is not None:
                row.certificate_at = now
                statuses.append("existing")
            else:
                if p.minor:
                    parent = reg.people[0].name if p.parent_is_first else f"{p.parent_first_name} {p.parent_last_name}".strip()
                else:
                    parent = None
                row = TrialStudent(
                    org_id=org_id,
                    first_name=p.first_name,
                    last_name=p.last_name,
                    age=p.age if p.minor else None,
                    email=reg.email,
                    parent_name=parent,
                    family=family,
                    token=secrets.token_urlsafe(16),
                    terms_id=settings.terms_id,
                    waiver_accepted=True,
                    certificate_at=now,
                    ip=ip,
                    created_at=now,
                )
                db.add(row)
                statuses.append("created")
            rows.append(row)
        given = {normalize(name): png for name, png in reg.signatures.items()}
        signatures = [
            TrialSignature(
                org_id=org_id,
                family=family,
                signer_name=name,
                children=children,
                png=given[normalize(name)],
                terms_id=settings.terms_id,
                ip=ip,
                created_at=now,
            )
            for name, children in expected_signers(reg.people).items()
        ]
        db.add_all(signatures)
        db.flush()

        address = self.school_address(ecole)
        qrs = [qr_png(f"{address}/?essai={row.token}") for row in rows]
        terms = self.terms(db, settings.terms_id)
        subject, text, html = confirmation_email(ecole.nom, settings, terms, rows, statuses, signatures)
        images = [(f"qr-{i}", png) for i, png in enumerate(qrs)] + [
            (f"signature-{i}", s.png) for i, s in enumerate(signatures)
        ]
        try:
            self.send(
                to=reg.email,
                subject=subject,
                text=text,
                html=html,
                attachments=attachments,
                images=images,
                copy=ecole.email_contact,
                reply_to=ecole.email_contact,
                school=ecole,
            )
        except Exception as exc:  # noqa: BLE001 (rien n'est gardé si le mail ne part pas)
            db.rollback()
            raise RegistrationError("Envoi impossible, réessayez dans un instant") from exc
        db.commit()
        return {
            "people": [
                {"first_name": r.first_name, "last_name": r.last_name, "status": s, "qr_png": png}
                for r, s, png in zip(rows, statuses, qrs)
            ]
        }

    # --- Admin > Essais (§4) ---

    def _student(self, db: Session, org_id: int, student_id: int) -> TrialStudent:
        row = db.get(TrialStudent, student_id)
        if row is None or row.org_id != org_id:
            raise LookupError(student_id)
        return row

    def students(self, db: Session, org_id: int) -> list[tuple[TrialStudent, bool]]:
        """Les élèves à l'essai, les plus récents d'abord, avec « déjà
        élève de l'école » (même prénom et nom)."""
        members = self.member_names(db, org_id)
        rows = db.scalars(
            select(TrialStudent).where(TrialStudent.org_id == org_id).order_by(TrialStudent.created_at.desc())
        ).all()
        return [(r, normalize(f"{r.first_name} {r.last_name}") in members) for r in rows]

    def student(self, db: Session, org_id: int, student_id: int) -> tuple[TrialStudent, list[TrialSignature], list[TrialStudent], TrialTerms]:
        row = self._student(db, org_id, student_id)
        signatures = db.scalars(
            select(TrialSignature).where(TrialSignature.org_id == org_id, TrialSignature.family == row.family)
        ).all()
        family = db.scalars(
            select(TrialStudent).where(
                TrialStudent.org_id == org_id, TrialStudent.family == row.family, TrialStudent.id != row.id
            )
        ).all()
        return row, signatures, family, self.terms(db, row.terms_id)

    def update(self, db: Session, org_id: int, student_id: int, data: dict) -> TrialStudent:
        row = self._student(db, org_id, student_id)
        for key in ("first_name", "last_name", "email"):
            if key in data:
                value = (data[key] or "").strip()
                if not value:
                    raise TrialError("Prénom, nom et e-mail sont obligatoires")
                setattr(row, key, value)
        for key in ("phone", "parent_name"):
            if key in data:
                setattr(row, key, (data[key] or "").strip() or None)
        if "comment" in data:
            row.comment = data["comment"] or ""
        if "age" in data:
            age = data["age"]
            if age is not None and not 3 <= age < ADULT_AGE:
                raise TrialError("L'âge d'un mineur va de 3 à 17 ans ; vide pour un majeur")
            row.age = age
        for n in (1, 2):
            key = f"course{n}_date"
            if key in data:
                value = data[key]
                if value != getattr(row, key):
                    setattr(row, key, value)
                    setattr(row, f"course{n}_mode", "manual" if value else None)
        db.commit()
        return row

    def add_course(self, db: Session, org_id: int, student_id: int, mode: str = "manual") -> TrialStudent:
        """« + Cours aujourd'hui » : la date du jour dans le 1er cours libre."""
        row = self._student(db, org_id, student_id)
        day = today()
        if day in (row.course1_date, row.course2_date):
            raise TrialError("Cours déjà noté aujourd'hui")
        if row.course1_date is None:
            row.course1_date, row.course1_mode = day, mode
        elif row.course2_date is None:
            row.course2_date, row.course2_mode = day, mode
        else:
            raise TrialError(f"Les {MAX_COURSES} cours d'essai sont déjà faits")
        db.commit()
        return row

    def remove(self, db: Session, org_id: int, student_id: int) -> None:
        row = self._student(db, org_id, student_id)
        db.delete(row)
        db.flush()
        self._delete_orphan_signatures(db)
        db.commit()

    # --- Suppression au bout d'un an (§7) ---

    def purge_expired(self, db: Session) -> int:
        """Supprime, toutes écoles confondues, les inscrits sans inscription
        ni cours depuis un an, avec leurs signatures."""
        limit = today() - timedelta(days=RETENTION_DAYS)
        expired = [
            row
            for row in db.scalars(select(TrialStudent)).all()
            if max(d for d in (row.created_at.date(), row.course1_date, row.course2_date) if d) < limit
        ]
        for row in expired:
            db.delete(row)
        db.flush()
        self._delete_orphan_signatures(db)
        db.commit()
        return len(expired)

    @staticmethod
    def _delete_orphan_signatures(db: Session) -> None:
        db.execute(
            delete(TrialSignature).where(TrialSignature.family.not_in(select(TrialStudent.family).distinct()))
        )
