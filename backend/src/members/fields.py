"""La fiche d'un membre (spec/core.md §4.3, niveau 1) : les champs que
l'organisation demande, un jeu par saison, recopié à la saison suivante.
Les champs du socle (nom, prénom, emails, téléphone) restent sur `comptes`
et ne sont pas ici."""

from __future__ import annotations

from datetime import datetime, timezone

from groups import Group, GroupMember
from groups.rights import PREFIX as RIGHTS
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .models import FORMATS, MemberField, MemberValue

SETTINGS = ("label", "required", "format", "choices", "group_id", "multiple",
            "member_sees", "member_edits", "others_see", "for_group_id")


class FieldError(ValueError):
    """Message lisible, renvoyé tel quel à l'écran."""


def fields(db: Session, org_id: int, season_id: int) -> list[MemberField]:
    return list(
        db.scalars(
            select(MemberField)
            .where(MemberField.org_id == org_id, MemberField.season_id == season_id, MemberField.removed_at.is_(None))
            .order_by(MemberField.position, MemberField.id)
        )
    )


def _not_a_right():
    return or_(Group.key.is_(None), ~Group.key.startswith(RIGHTS))


def parent_groups(db: Session, org_id: int, season_id: int) -> list[Group]:
    """Format « Groupe » : les groupes qui ont des sous-groupes (Cours,
    Bureau...), jamais un groupe de droit."""
    children = select(Group.parent_id).where(Group.parent_id.is_not(None))
    return list(
        db.scalars(
            select(Group)
            .where(Group.org_id == org_id, Group.season_id == season_id, Group.id.in_(children), _not_a_right())
            # Cours d'abord : le choix proposé d'office (« Cours suivis »).
            .order_by(func.coalesce(Group.key, "") != "courses", Group.id)
        )
    )


def audience_groups(db: Session, org_id: int, season_id: int) -> list[Group]:
    """« Pour qui » : les groupes de premier niveau de la saison."""
    return list(
        db.scalars(
            select(Group)
            .where(Group.org_id == org_id, Group.season_id == season_id, Group.parent_id.is_(None), _not_a_right())
            .order_by(Group.id)
        )
    )


def children(db: Session, group_id: int) -> list[Group]:
    return list(db.scalars(select(Group).where(Group.parent_id == group_id).order_by(Group.id)))


def _check(db: Session, field: MemberField) -> None:
    field.label = " ".join((field.label or "").split())
    if not field.label:
        raise FieldError("L'intitulé est obligatoire")
    if len(field.label) > 100:
        raise FieldError("Intitulé trop long (100 caractères au plus)")
    if field.format not in FORMATS:
        raise FieldError("Format de la réponse inconnu")
    if field.format == "list":
        field.choices = [c for c in (" ".join(str(c).split()) for c in field.choices or []) if c]
        if not field.choices:
            raise FieldError("Donnez au moins un choix")
    else:
        field.choices = None
    if field.format == "group":
        allowed = {g.id for g in parent_groups(db, field.org_id, field.season_id)}
        if field.group_id not in allowed:
            raise FieldError("Choisissez le groupe")
    else:
        field.group_id = None
    if field.format not in ("list", "group"):
        field.multiple = False
    if field.for_group_id is not None:
        if field.for_group_id not in {g.id for g in audience_groups(db, field.org_id, field.season_id)}:
            raise FieldError("Groupe introuvable")
    # Ce que voit la personne commande le reste (maquette).
    if not field.member_sees:
        field.member_edits = False
        field.others_see = False


def create(db: Session, org_id: int, season_id: int, **settings) -> MemberField:
    """Nouveau champ, à la fin de la fiche (sans commit)."""
    last = db.scalar(
        select(func.max(MemberField.position)).where(MemberField.org_id == org_id, MemberField.season_id == season_id)
    )
    field = MemberField(org_id=org_id, season_id=season_id, position=(last or 0) + 1)
    for key, value in settings.items():
        if key in SETTINGS:
            setattr(field, key, value)
    _check(db, field)
    db.add(field)
    db.flush()
    return field


def update(db: Session, field: MemberField, **settings) -> MemberField:
    for key, value in settings.items():
        if key in SETTINGS:
            setattr(field, key, value)
    _check(db, field)
    db.flush()
    return field


def remove(field: MemberField) -> None:
    """« Retirer ce champ » : il quitte la fiche, ses réponses sont gardées
    (Annuler le remet)."""
    field.removed_at = datetime.now(timezone.utc).replace(tzinfo=None)


def restore(field: MemberField) -> None:
    field.removed_at = None


def _same_group(db: Session, old_id: int | None, season_id: int) -> int | None:
    """Le groupe de la nouvelle saison qui prend la place de `old_id` : même
    clé et même nom, créé s'il manque (ex. « Cours » quand aucun cours n'est
    recopié)."""
    if old_id is None:
        return None
    old = db.get(Group, old_id)
    new = db.scalar(
        select(Group).where(
            Group.org_id == old.org_id, Group.season_id == season_id, Group.parent_id.is_(None),
            Group.name == old.name, Group.key.is_(None) if old.key is None else Group.key == old.key,
        )
    )
    if new is None:
        new = Group(org_id=old.org_id, season_id=season_id, key=old.key, name=old.name)
        db.add(new)
        db.flush()
    return new.id


def copy_season(db: Session, org_id: int, old_season_id: int, new_season_id: int, members: dict[int, int]) -> None:
    """Nouvelle saison : la même fiche (spec §4.3) et le même affichage dans
    Admin, et les réponses des fiches recopiées (`members` : ancienne fiche →
    nouvelle). Après la copie des groupes et des cours."""
    from . import columns

    copied: dict[int, int] = {}
    for old in fields(db, org_id, old_season_id):
        new = MemberField(org_id=org_id, season_id=new_season_id, position=old.position)
        for key in SETTINGS:
            setattr(new, key, getattr(old, key))
        new.group_id = _same_group(db, old.group_id, new_season_id)
        new.for_group_id = _same_group(db, old.for_group_id, new_season_id)
        db.add(new)
        db.flush()
        copied[old.id] = new.id
        for value in db.scalars(select(MemberValue).where(MemberValue.field_id == old.id)):
            if value.member_id in members:
                db.add(MemberValue(member_id=members[value.member_id], field_id=new.id, value=value.value))
    db.flush()
    columns.copy_season(db, org_id, old_season_id, new_season_id, copied)


def member_group_ids(db: Session, field: MemberField, member_id: int) -> list[int]:
    """Format « Groupe » : les sous-groupes cochés pour cette fiche."""
    ids = select(Group.id).where(Group.parent_id == field.group_id)
    return list(
        db.scalars(
            select(GroupMember.group_id)
            .where(GroupMember.member_id == member_id, GroupMember.group_id.in_(ids))
            .order_by(GroupMember.group_id)
        )
    )
