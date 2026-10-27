"""Les cours (spec/core.md §5.1) : chaque cours est un sous-groupe du groupe
« Cours » de sa saison. Le groupe réunit ses élèves ; le reste du cours (jour,
horaire, salle, profs) reste dans la table `cours`, qui pointe vers son groupe
(`cours.group_id`, composition).

Remplace la table `eleves_cours` (reprise par la migration c5e7a9b1d3f4,
gardée en base, plus lue ni écrite). Le code des cours lit les élèves par
`cours.models.eleves_cours`, la même chose vue depuis les groupes.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Group, GroupMember

PARENT = "courses"
COURSE = "course"


def _parent(db: Session, org_id: int, season_id: int) -> Group:
    parent = db.scalar(select(Group).where(Group.org_id == org_id, Group.season_id == season_id, Group.key == PARENT))
    if parent is None:
        parent = Group(org_id=org_id, season_id=season_id, key=PARENT, name="Cours")
        db.add(parent)
        db.flush()
    return parent


def create(db: Session, org_id: int, season_id: int, name: str) -> Group:
    """Le groupe d'un nouveau cours (sans commit)."""
    group = Group(
        org_id=org_id, season_id=season_id, parent_id=_parent(db, org_id, season_id).id, key=COURSE, name=name[:100]
    )
    db.add(group)
    db.flush()
    return group


def rename(db: Session, group_id: int, name: str) -> None:
    group = db.get(Group, group_id)
    if group is not None:
        group.name = name[:100]


def add(db: Session, group_id: int, member_id: int) -> None:
    if db.get(GroupMember, (group_id, member_id)) is None:
        db.add(GroupMember(group_id=group_id, member_id=member_id))
        db.flush()


def remove(db: Session, group_id: int, member_id: int) -> None:
    db.execute(delete(GroupMember).where(GroupMember.group_id == group_id, GroupMember.member_id == member_id))


def drop(db: Session, group_id: int) -> None:
    """Supprime le groupe d'un cours et ses membres (sans commit)."""
    db.execute(delete(GroupMember).where(GroupMember.group_id == group_id))
    db.execute(delete(Group).where(Group.id == group_id))


def leave_all(db: Session, member_id: int) -> None:
    """La fiche quitte tous ses cours (sans commit)."""
    ids = select(Group.id).where(Group.key == COURSE)
    db.execute(delete(GroupMember).where(GroupMember.member_id == member_id, GroupMember.group_id.in_(ids)))
