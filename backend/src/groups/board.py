"""Le bureau (spec/core.md §5.1) : le groupe Bureau et ses sous-groupes
Président·e, Vice-président·e, Secrétaire, Trésorier·e, un jeu par
organisation et par saison, créé à la première demande.

Des titres, aucun droit : l'onglet Financier reste la coche « Accès au
Financier ». Remplace la colonne `comptes.bureau_functions`, qui n'est plus
lue (reprise par la migration f2b4d6e8a0c3).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Group, GroupMember

if TYPE_CHECKING:
    from comptes import Compte

BOARD = "board"
# Dans l'ordre d'affichage. Clé de l'API et de l'assistant → nom du sous-groupe.
FUNCTIONS = {
    "president": "Président·e",
    "vice_president": "Vice-président·e",
    "secretary": "Secrétaire",
    "treasurer": "Trésorier·e",
}


def ordered(functions) -> list[str]:
    """Sans doublon, dans l'ordre de FUNCTIONS."""
    functions = set(functions)
    return [f for f in FUNCTIONS if f in functions]


def _groups(db: Session, org_id: int, season_id: int) -> dict[str, Group]:
    """Les sous-groupes du bureau de cette saison, par fonction, créés s'ils
    n'existent pas encore."""
    rows = db.scalars(
        select(Group).where(Group.org_id == org_id, Group.season_id == season_id, Group.key.like(f"{BOARD}%"))
    ).all()
    by_key = {g.key: g for g in rows}
    parent = by_key.get(BOARD)
    if parent is None:
        parent = Group(org_id=org_id, season_id=season_id, key=BOARD, name="Bureau")
        db.add(parent)
        db.flush()
    result = {}
    for function, name in FUNCTIONS.items():
        key = f"{BOARD}.{function}"
        if key not in by_key:
            by_key[key] = Group(org_id=org_id, season_id=season_id, parent_id=parent.id, key=key, name=name)
            db.add(by_key[key])
        result[function] = by_key[key]
    db.flush()
    return result


def functions_of(db: Session, member: Compte) -> list[str]:
    """Les fonctions de cette fiche au bureau, dans l'ordre d'affichage."""
    keys = db.scalars(
        select(Group.key)
        .join(GroupMember, GroupMember.group_id == Group.id)
        .where(GroupMember.member_id == member.id, Group.key.like(f"{BOARD}.%"))
    )
    return ordered(k.removeprefix(f"{BOARD}.") for k in keys)


def set_functions(db: Session, member: Compte, functions) -> None:
    """Remplace les fonctions de la fiche au bureau (sans commit)."""
    groups = _groups(db, member.ecole_id, member.saison_id)
    ids = [g.id for g in groups.values()]
    db.execute(delete(GroupMember).where(GroupMember.member_id == member.id, GroupMember.group_id.in_(ids)))
    for function in ordered(functions):
        db.add(GroupMember(group_id=groups[function].id, member_id=member.id))
    db.flush()


def board(db: Session, org_id: int, season_id: int) -> dict[int, list[str]]:
    """Les fiches du bureau de cette saison et leurs fonctions."""
    rows = db.execute(
        select(GroupMember.member_id, Group.key)
        .join(Group, Group.id == GroupMember.group_id)
        .where(Group.org_id == org_id, Group.season_id == season_id, Group.key.like(f"{BOARD}.%"))
    )
    found: dict[int, list[str]] = {}
    for member_id, key in rows:
        found.setdefault(member_id, []).append(key.removeprefix(f"{BOARD}."))
    return {member_id: ordered(functions) for member_id, functions in found.items()}
