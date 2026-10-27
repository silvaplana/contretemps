"""Les groupes faits à la main (spec/core.md §5.1) : « + Nouveau groupe… »
dans Admin > Administrateurs, ex. Bénévoles. Sans clé ni parent, un jeu par
organisation et par saison ; recopiés avec leurs membres à la nouvelle
saison. Ils ne donnent aucun droit par eux-mêmes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Group, GroupMember

if TYPE_CHECKING:
    from comptes import Compte


class GroupError(ValueError):
    """Message lisible, renvoyé tel quel à l'écran."""


def groups(db: Session, org_id: int, season_id: int) -> list[Group]:
    return list(
        db.scalars(
            select(Group)
            .where(Group.org_id == org_id, Group.season_id == season_id, Group.key.is_(None))
            .order_by(Group.name, Group.id)
        )
    )


def create(db: Session, org_id: int, season_id: int, name: str) -> Group:
    """Nouveau groupe (sans commit). Refusé si le nom est vide ou déjà pris
    dans la saison, groupes du code compris (Bureau, Profs...)."""
    name = " ".join((name or "").split())
    if not name:
        raise GroupError("Le nom du groupe est obligatoire")
    if len(name) > 100:
        raise GroupError("Nom trop long (100 caractères au plus)")
    taken = db.scalars(select(Group.name).where(Group.org_id == org_id, Group.season_id == season_id))
    if name.casefold() in {n.casefold() for n in taken}:
        raise GroupError(f"Le groupe « {name} » existe déjà")
    group = Group(org_id=org_id, season_id=season_id, name=name)
    db.add(group)
    db.flush()
    return group


def ids_of(db: Session, member: Compte) -> list[int]:
    """Les groupes faits à la main dont la fiche fait partie."""
    return list(
        db.scalars(
            select(Group.id)
            .join(GroupMember, GroupMember.group_id == Group.id)
            .where(GroupMember.member_id == member.id, Group.key.is_(None))
            .order_by(Group.id)
        )
    )


def set_groups(db: Session, member: Compte, group_ids) -> None:
    """Remplace les groupes faits à la main de la fiche (sans commit). Seuls
    ceux de son organisation et de sa saison sont acceptés."""
    allowed = {g.id for g in groups(db, member.ecole_id, member.saison_id)}
    wanted = set(group_ids)
    if not wanted <= allowed:
        raise GroupError("Groupe introuvable")
    current = set(ids_of(db, member))
    if current - wanted:
        db.execute(
            delete(GroupMember).where(GroupMember.member_id == member.id, GroupMember.group_id.in_(current - wanted))
        )
    for group_id in sorted(wanted - current):
        db.add(GroupMember(group_id=group_id, member_id=member.id))
    db.flush()


def copy_season(db: Session, org_id: int, old_season_id: int, new_season_id: int, members: dict[int, int]) -> None:
    """Nouvelle saison : mêmes groupes, avec les fiches recopiées (`members` :
    ancienne fiche → nouvelle)."""
    for old in groups(db, org_id, old_season_id):
        new = Group(org_id=org_id, season_id=new_season_id, name=old.name)
        db.add(new)
        db.flush()
        for (member_id,) in db.execute(select(GroupMember.member_id).where(GroupMember.group_id == old.id)):
            if member_id in members:
                db.add(GroupMember(group_id=new.id, member_id=members[member_id]))
    db.flush()
