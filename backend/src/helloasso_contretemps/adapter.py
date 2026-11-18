"""What the HelloAsso statistics read from the other modules of Contretemps
(spec/modules/helloasso.md §7.8): the school's accounts in the Financier
and the licences on the FFST site. Neither module imports the other."""

from __future__ import annotations

from registry.activation import disabled
from sqlalchemy.orm import Session

from ffst.club import Club
from ffst.site import LICENSEES
from finances.ports import Member

# Taken from Sambo Admin (helloasso/summary.py): one licence per member, plus
# the coach's, at the price of a licence (euros).
FFST_LICENCE_PRICE = 24
COACH_LICENCES = 1


def ledger(finances):
    """`finances`: the Financier (core.finances_client). Read in the school's
    name: the HelloAsso screen decides who sees what."""

    def read(db: Session, org_id: int) -> dict | None:
        if "finances" in disabled(db, org_id):
            return None
        return finances.get_ledger(db, Member(person_id=0, org_id=org_id, name="", is_treasurer=True))

    return read


def licences(db: Session, org_id: int, members: int) -> dict | None:
    """Licences still to pay: members + coach - licensees of the last reading
    of the FFST site; None if FFST is off or never read."""
    if "ffst" in disabled(db, org_id) or Club.row(db, org_id) is None:
        return None
    lists, read_at = Club.lists(db, org_id)
    if read_at is None:
        return None
    count = max(0, members + COACH_LICENCES - len(lists[LICENSEES]))
    return {"count": count, "price": FFST_LICENCE_PRICE}
