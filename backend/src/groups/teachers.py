"""Les profs (spec/core.md §5.1) : le groupe « Profs », un par organisation
et par saison, créé à la première demande.

Remplace le rôle Professeur (lignes « professeur » de `roles_compte`,
reprises par la migration a3c5e7f9b1d2). Le reste du code ne lit pas ce
groupe directement : il passe toujours par comptes/roles.py (`is_prof`),
qui garde le rang et les droits d'un prof inchangés.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Group, GroupMember

if TYPE_CHECKING:
    from comptes import Compte

TEACHERS = "teachers"


def _group(db: Session, org_id: int, season_id: int) -> Group:
    group = db.scalar(select(Group).where(Group.org_id == org_id, Group.season_id == season_id, Group.key == TEACHERS))
    if group is None:
        group = Group(org_id=org_id, season_id=season_id, key=TEACHERS, name="Profs")
        db.add(group)
        db.flush()
    return group


def add(db: Session, member: Compte) -> None:
    """Met la fiche dans les Profs de sa saison (sans commit). La fiche doit
    déjà avoir un id."""
    group = _group(db, member.ecole_id, member.saison_id)
    if db.get(GroupMember, (group.id, member.id)) is None:
        db.add(GroupMember(group_id=group.id, member_id=member.id))
        db.flush()
    db.expire(member, ["groups"])


def remove(db: Session, member: Compte) -> None:
    """Retire la fiche des Profs (sans commit)."""
    ids = select(Group.id).where(Group.key == TEACHERS)
    db.execute(delete(GroupMember).where(GroupMember.member_id == member.id, GroupMember.group_id.in_(ids)))
    db.flush()
    db.expire(member, ["groups"])
