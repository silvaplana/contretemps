"""Card payment with the school's own keys (spec/modules/helloasso.md §8.2):
a season set to « L'appli fait tout, HelloAsso encaisse » pays through the
school's HelloAsso connection instead of the server's variables. Given to the
online registration as a keys provider (`HelloAsso.school_keys`), so neither
module imports the other."""

from __future__ import annotations

from sqlalchemy.orm import Session

from . import api
from .campaign import PAYMENT, Campaigns
from .connection import Connection


def school_keys(db: Session, org_id: int, season_id: int) -> tuple[str, str, str, str] | None:
    """(client_id, secret, slug, base URL) of the school for this season, or
    None: no such season choice, module off, not connected, or keys that no
    longer decrypt (the server's keys are then used, as before)."""
    from registry.activation import disabled

    row = Campaigns.row(db, season_id)
    if row is None or row.mode != PAYMENT or row.org_id != org_id or "helloasso" in disabled(db, org_id):
        return None
    connection = Connection.row(db, org_id)
    if connection is None or not connection.active:
        return None
    try:
        client_id, secret, slug = Campaigns._keys(connection)
    except api.HelloAssoError:
        return None
    return client_id, secret, slug, api._base()
