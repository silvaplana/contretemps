"""The club on the FFST site (spec/modules/ffst.md §2-4): test and save its
login, read the three lists and keep a copy of the last reading, and the
FFST status of each member, matched by last and first name as in Sambo
Admin (there is no common identifier between HelloAsso and the FFST)."""

from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timezone

from comptes import Compte
from securite.chiffrement import chiffrer, dechiffrer
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import site
from .models import FfstConnection, FfstSnapshot

# By priority (Sambo Admin).
STATUSES = (
    (site.LICENSEES, "Licence créée"),
    (site.VALIDATED, "Validée, à payer"),
    (site.DRAFTS, "Brouillon"),
)
UNKNOWN = "Inconnu"

# Straight, typographic and similar apostrophes: the FFST site crashes on
# them, Sambo Admin sends a space instead (« M'Hadjou » = « M HADJOU »).
_APOSTROPHES = "'’‘ʼ`´"


def name_key(text: str | None) -> str:
    """Without accents, case, apostrophes or extra spaces."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    for apostrophe in _APOSTROPHES:
        text = text.replace(apostrophe, " ")
    return " ".join(text.split())


def member_key(last_name: str | None, first_name: str | None) -> str:
    return name_key(f"{last_name or ''} {first_name or ''}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Club:
    def __init__(
        self,
        check=site.check,
        read_all=site.read_all,
        create_request=site.create_request,
        delete_draft=site.delete_draft,
    ) -> None:
        # Replaceable in tests (no network, no browser).
        self.check = check
        self.read_all = read_all
        self.create_request = create_request
        self.delete_draft = delete_draft

    @staticmethod
    def row(db: Session, org_id: int) -> FfstConnection | None:
        return db.scalar(select(FfstConnection).where(FfstConnection.org_id == org_id))

    def test(self, login: site.Login) -> int:
        return self.check(login)

    def save(self, db: Session, org_id: int, login: site.Login) -> int:
        """Tests the login, then saves it (replaces the previous one)."""
        count = self.test(login)
        row = self.row(db, org_id) or FfstConnection(org_id=org_id)
        row.login_part1, row.login_part2, row.login_part3 = login.part1, login.part2, login.part3
        row.password_encrypted = chiffrer(login.password)
        row.connected_at = row.last_test_at = _now()
        row.last_test_ok = True
        db.add(row)
        db.commit()
        return count

    def login(self, db: Session, org_id: int) -> site.Login:
        row = self.row(db, org_id)
        if row is None:
            raise site.FfstError("Le site de la FFST n’est pas connecté.")
        password = dechiffrer(row.password_encrypted)
        if password is None:
            raise site.FfstError("Le mot de passe enregistré ne se lit plus : changez les identifiants.")
        return site.Login(row.login_part1, row.login_part2, row.login_part3, password)

    def retest(self, db: Session, org_id: int) -> int:
        login = self.login(db, org_id)
        row = self.row(db, org_id)
        row.last_test_at = _now()
        try:
            count = self.check(login)
        except site.FfstError:
            row.last_test_ok = False
            db.commit()
            raise
        row.last_test_ok = True
        db.commit()
        return count

    def refresh(self, db: Session, org_id: int) -> None:
        """Reads the three lists and replaces the copy, all or nothing: if the
        site fails, the previous copy stays (FfstError)."""
        lists = self.read_all(self.login(db, org_id))
        now = _now()
        db.execute(delete(FfstSnapshot).where(FfstSnapshot.org_id == org_id))
        for name, rows in lists.items():
            db.add(FfstSnapshot(org_id=org_id, list_name=name, rows=rows, read_at=now))
        db.commit()

    @staticmethod
    def lists(db: Session, org_id: int) -> tuple[dict[str, list[dict]], datetime | None]:
        """The copy of the last reading, and when it was read (None: never)."""
        snapshots = db.scalars(select(FfstSnapshot).where(FfstSnapshot.org_id == org_id)).all()
        lists = {name: [] for name in site.LISTS}
        for snapshot in snapshots:
            lists[snapshot.list_name] = snapshot.rows
        return lists, min((s.read_at for s in snapshots), default=None)

    @staticmethod
    def statuses(lists: dict[str, list[dict]], people: list[tuple[int, str, str]]) -> dict[int, str]:
        """{member id: FFST status}, `people` being (id, last name, first name)."""
        keys = {name: {name_key(r.get("Nom et Prénom")) for r in lists.get(name, [])} for name, _ in STATUSES}
        result = {}
        for member_id, last_name, first_name in people:
            key = member_key(last_name, first_name)
            result[member_id] = next((label for name, label in STATUSES if key in keys[name]), UNKNOWN)
        return result


    def gender_known(self, db: Session, org_id: int, member_ids: list[int]) -> dict[int, bool]:
        """Whether the HelloAsso form gives each member's gender (otherwise
        the screen asks « Genre absent de HelloAsso : Choisir »)."""
        from helloasso.members import table_answers
        from saisons import saison_courante_id

        season_id = saison_courante_id(db, org_id)
        answers = table_answers(db, org_id, season_id) if season_id is not None else {}
        return {m: gender(answers_of(answers.get(m)).get("gender")) is not None for m in member_ids}

    def _status_now(self, db: Session, org_id: int, member: Compte) -> str:
        """Reads the site again (always just before writing, spec §3)."""
        self.refresh(db, org_id)
        lists, _ = self.lists(db, org_id)
        return self.statuses(lists, [(member.id, member.nom, member.prenom)])[member.id]

    def request(
        self, db: Session, org_id: int, member_id: int, fonction: str, gender_override: str | None = None
    ) -> list[str]:
        """« Faire la demande »: refused when the site already has the person;
        otherwise the request goes in the basket. Returns the warnings."""
        member = _member(db, org_id, member_id)
        status = self._status_now(db, org_id, member)
        if status != UNKNOWN:
            raise Refused(f"Le site de la FFST a déjà {member.prenom} {member.nom} : {status}.")
        row = self.row(db, org_id)
        settings = site.Settings(
            discipline=row.discipline,
            default_birth_town=row.default_birth_town or (_school_town(db, org_id) or ""),
            image_rights=row.image_rights,
        )
        warnings = self.create_request(
            self.login(db, org_id), person(db, org_id, member, gender_override), fonction, settings
        )
        self._reread(db, org_id)
        return warnings

    def remove(self, db: Session, org_id: int, member_id: int) -> None:
        """« Supprimer la demande »: only a request still in the basket."""
        member = _member(db, org_id, member_id)
        status = self._status_now(db, org_id, member)
        if status != "Brouillon":
            raise Refused(f"La demande de {member.prenom} {member.nom} n’est plus dans le panier : {status}.")
        self.delete_draft(self.login(db, org_id), member.nom, member.prenom)
        self._reread(db, org_id)

    def _reread(self, db: Session, org_id: int) -> None:
        """After an action: the site is read again; if it does not answer,
        the action is still done, the next « Rafraîchir » will show it."""
        try:
            self.refresh(db, org_id)
        except site.FfstError:
            db.rollback()


# --- Writing on the site (spec §5) ---

_SHORT_YEAR = re.compile(r"^(\d{2}/\d{2})/00(\d{2})$")
_ISO_DATE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def birth_date(value, today: date | None = None) -> str | None:
    """JJ/MM/AAAA as the site wants it. A year typed on two digits, that
    HelloAsso keeps as « 0017 », is put back in its century (Sambo Admin: an
    FFST refusal « au-delà de 99 ans »); an ISO date is turned around."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    iso = _ISO_DATE.match(value)
    if iso:
        value = f"{iso.group(3)}/{iso.group(2)}/{iso.group(1)}"
    short = _SHORT_YEAR.match(value)
    if not short:
        return value
    current = (today or date.today()).year
    year = current - current % 100 + int(short.group(2))
    return f"{short.group(1)}/{year - 100 if year > current else year}"


def gender(value) -> str | None:
    """« H » or « F » from « Homme », « F », « femme »... (Sambo Admin)."""
    first = str(value or "").strip()[:1].upper()
    return first if first in ("H", "F") else None


# The questions of the HelloAsso form, found by a word of their title (Sambo
# Admin read ASC's: « Genre(H/F) », « date de naissance », « Adresse »,
# « code postal », « Ville », « Numéro de téléphone »).
_QUESTIONS = {
    "gender": ("genre", "sexe"),
    "birth_date": ("date de naissance", "date naissance"),
    "postal_code": ("code postal",),
    "city": ("ville", "commune"),
    "phone": ("telephone", "portable", "mobile"),
    "address": ("adresse",),
}


def answers_of(answers: list[dict] | None) -> dict[str, str]:
    """{gender, birth_date, address, postal_code, city, phone}: the first
    answer whose question title has one of the words."""
    found: dict[str, str] = {}
    for answer in answers or []:
        title, value = name_key(answer.get("name")), answer.get("answer")
        if not isinstance(value, str) or not value.strip():
            continue
        for key, words in _QUESTIONS.items():
            # « Adresse mail », « Ville de naissance » are not the address.
            if key in ("address", "city") and ("mail" in title or "naissance" in title):
                continue
            if key not in found and any(w in title for w in words):
                found[key] = value.strip()
                break
    return found


class Refused(site.FfstError):
    """Nothing sent to the site: the message says why."""


def _member(db: Session, org_id: int, member_id: int) -> Compte:
    member = db.get(Compte, member_id)
    if member is None or member.ecole_id != org_id:
        raise LookupError(member_id)
    return member


def person(db: Session, org_id: int, member: Compte, gender_override: str | None = None) -> site.Person:
    """The member as the site needs them: names of the card, the rest from
    their HelloAsso form this season (Sambo Admin), the gender chosen on
    screen when the form has none."""
    from helloasso.members import registration
    from saisons import saison_courante_id

    season_id = saison_courante_id(db, org_id)
    r = registration(db, org_id, season_id, member.id) if season_id is not None else None
    found = answers_of(r.answers if r else None)
    return site.Person(
        last_name=member.nom,
        first_name=member.prenom,
        gender=gender(found.get("gender")) or gender(gender_override),
        birth_date=birth_date(found.get("birth_date")),
        address=found.get("address"),
        postal_code=found.get("postal_code"),
        city=found.get("city"),
        phone=found.get("phone"),
        email=(r.payer_email if r else None) or member.payer_email,
    )


def _school_town(db: Session, org_id: int) -> str | None:
    from ecoles.models import Ecole

    school = db.get(Ecole, org_id)
    return school.ville if school else None
