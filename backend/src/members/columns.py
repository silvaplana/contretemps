"""L'affichage dans Admin (spec/core.md §4.3, niveau 2) : quelles colonnes
du tableau des membres sont affichées, et dans quel ordre, par saison. Le
serveur garde seulement les clés ; l'écran sait ce qu'est chaque colonne."""

from __future__ import annotations

import re

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .fields import FieldError
from .models import MemberColumn

_KEY = re.compile(r"[a-z_]{1,30}|field:\d{1,9}")


def columns(db: Session, org_id: int, season_id: int) -> list[MemberColumn]:
    return list(
        db.scalars(
            select(MemberColumn)
            .where(MemberColumn.org_id == org_id, MemberColumn.season_id == season_id)
            .order_by(MemberColumn.position)
        )
    )


def save(db: Session, org_id: int, season_id: int, wanted: list[dict]) -> list[MemberColumn]:
    """Remplace l'affichage de la saison par `wanted` ([{key, shown}], dans
    l'ordre ; sans commit)."""
    keys = [c["key"] for c in wanted]
    if len(set(keys)) != len(keys) or not all(_KEY.fullmatch(k) for k in keys):
        raise FieldError("Colonnes invalides")
    db.execute(delete(MemberColumn).where(MemberColumn.org_id == org_id, MemberColumn.season_id == season_id))
    for position, column in enumerate(wanted):
        db.add(MemberColumn(org_id=org_id, season_id=season_id, key=column["key"], shown=column["shown"],
                            position=position))
    db.flush()
    return columns(db, org_id, season_id)


def copy_season(db: Session, org_id: int, old_season_id: int, new_season_id: int, fields: dict[int, int]) -> None:
    """Nouvelle saison : le même affichage (`fields` : ancien champ → nouveau)."""
    for old in columns(db, org_id, old_season_id):
        key = old.key
        if key.startswith("field:"):
            new_field = fields.get(int(key.removeprefix("field:")))
            if new_field is None:
                continue
            key = f"field:{new_field}"
        db.add(MemberColumn(org_id=org_id, season_id=new_season_id, key=key, shown=old.shown, position=old.position))
    db.flush()
