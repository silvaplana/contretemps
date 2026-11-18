"""The club on the FFST site (spec/modules/ffst.md §2-4): test and save its
login, read the three lists and keep a copy of the last reading, and the
FFST status of each member, matched by last and first name as in Sambo
Admin (there is no common identifier between HelloAsso and the FFST)."""

from __future__ import annotations

import unicodedata
from datetime import datetime, timezone

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
    def __init__(self, check=site.check, read_all=site.read_all) -> None:
        # Replaceable in tests (no network).
        self.check = check
        self.read_all = read_all

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
