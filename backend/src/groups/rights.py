"""Un droit = un groupe 🔒 (spec/core.md §5.3).

Un module déclare ses droits dans son `module.py` (`Right("finances.access",
"Accès au Financier")`) ; le core en fait un groupe par organisation et par
saison, clé `right.<droit>`, au nom du droit, créé à la première demande.
Le contrôle passe par `comptes.roles.has_right`, jamais par ce fichier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .models import Group, GroupMember

if TYPE_CHECKING:
    from comptes import Compte

PREFIX = "right."
# Droit → nom du groupe, rempli au montage des modules (registry.mount_all).
_DECLARED: dict[str, str] = {}


def declare(key: str, name: str) -> None:
    _DECLARED[key] = name


def group_key(right: str) -> str:
    return f"{PREFIX}{right}"


def _group(db: Session, org_id: int, season_id: int, right: str) -> Group:
    key = group_key(right)
    group = db.scalar(select(Group).where(Group.org_id == org_id, Group.season_id == season_id, Group.key == key))
    if group is None:
        group = Group(org_id=org_id, season_id=season_id, key=key, name=_DECLARED.get(right, right))
        db.add(group)
        db.flush()
    return group


def add(db: Session, member: Compte, right: str) -> None:
    """Met la fiche dans le groupe du droit, pour sa saison (sans commit)."""
    group = _group(db, member.ecole_id, member.saison_id, right)
    if db.get(GroupMember, (group.id, member.id)) is None:
        db.add(GroupMember(group_id=group.id, member_id=member.id))
        db.flush()
    db.expire(member, ["groups"])


def remove(db: Session, member: Compte, right: str) -> None:
    """Retire la fiche du groupe du droit (sans commit)."""
    ids = select(Group.id).where(Group.key == group_key(right))
    db.execute(delete(GroupMember).where(GroupMember.member_id == member.id, GroupMember.group_id.in_(ids)))
    db.flush()
    db.expire(member, ["groups"])
