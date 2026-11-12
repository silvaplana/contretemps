"""Un droit = un groupe 🔒 (spec/core.md §5.3).

Un module déclare ses droits dans son `module.py` (`Right("finances.access",
"Accès au Financier")`) ; le core en fait un groupe par organisation et par
saison, clé `right.<droit>`, au nom du droit, créé à la première demande.
Le contrôle passe par `comptes.roles.has_right`, jamais par ce fichier.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .models import Group, GroupMember

if TYPE_CHECKING:
    from comptes import Compte

PREFIX = "right."
# Droit → nom du groupe, rempli au montage des modules (registry.mount_all).
_DECLARED: dict[str, str] = {}
# Droits propres à une organisation (spec/core.md §11.1, ex. « Publier dans
# Techniques », un par blog) : provider(db, org_id) → {droit: nom}.
_PROVIDERS: list[Callable[[Session, int], dict[str, str]]] = []


def declare(key: str, name: str) -> None:
    _DECLARED[key] = name


def provide(provider: Callable[[Session, int], dict[str, str]]) -> None:
    _PROVIDERS.append(provider)


def declared_for(db: Session, org_id: int) -> dict[str, str]:
    """Les droits qu'on peut cocher dans cette organisation : ceux des
    modules, puis ceux de l'organisation."""
    result = dict(_DECLARED)
    for provider in _PROVIDERS:
        result.update(provider(db, org_id))
    return result


def group_key(right: str) -> str:
    return f"{PREFIX}{right}"


def _group(db: Session, org_id: int, season_id: int, right: str, name: str | None) -> Group:
    key = group_key(right)
    group = db.scalar(select(Group).where(Group.org_id == org_id, Group.season_id == season_id, Group.key == key))
    if group is None:
        group = Group(org_id=org_id, season_id=season_id, key=key, name=name or _DECLARED.get(right, right))
        db.add(group)
        db.flush()
    return group


def add(db: Session, member: Compte, right: str, name: str | None = None) -> None:
    """Met la fiche dans le groupe du droit, pour sa saison (sans commit).
    `name` : le nom du groupe d'un droit d'organisation."""
    group = _group(db, member.ecole_id, member.saison_id, right, name)
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


def rename(db: Session, org_id: int, right: str, name: str) -> None:
    """Un droit d'organisation renommé (son blog renommé) : ses groupes de
    toutes les saisons suivent (sans commit)."""
    db.execute(update(Group).where(Group.org_id == org_id, Group.key == group_key(right)).values(name=name))


def forget(db: Session, org_id: int, right: str) -> None:
    """Un droit d'organisation qui disparaît : ses groupes et leurs membres
    (sans commit)."""
    ids = list(db.scalars(select(Group.id).where(Group.org_id == org_id, Group.key == group_key(right))))
    db.execute(delete(GroupMember).where(GroupMember.group_id.in_(ids)))
    db.execute(delete(Group).where(Group.id.in_(ids)))


def of(member: Compte) -> list[str]:
    """Les droits dont la fiche est dans le groupe (sans le Super User) :
    ceux des modules dans leur ordre, puis ceux de l'organisation."""
    keys = {g.key for g in member.groups if g.key and g.key.startswith(PREFIX)}
    static = [right for right in _DECLARED if group_key(right) in keys]
    return static + sorted(k[len(PREFIX):] for k in keys if k[len(PREFIX):] not in _DECLARED)
