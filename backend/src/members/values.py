"""Les réponses d'une fiche aux champs de son organisation (spec/core.md
§4.3). Saisies par un admin pour l'instant ; le côté membre (réglages
avancés) viendra avec la fiche vue par la personne."""

from __future__ import annotations

import datetime as dt
import re
from typing import TYPE_CHECKING, BinaryIO

from groups import GroupMember
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import fields as f
from .models import MemberField, MemberValue

if TYPE_CHECKING:
    from comptes import Compte
    from storage import LocalStorage

MAX_TEXT = {"short_text": 200, "long_text": 5000, "phone": 50, "postal_code": 10}


def answers(db: Session, member: Compte) -> list[dict]:
    """Chaque champ de la fiche, dans l'ordre, avec la réponse de la fiche
    (None si vide)."""
    stored = {
        v.field_id: v.value for v in db.scalars(select(MemberValue).where(MemberValue.member_id == member.id))
    }
    return [
        {
            "field": field,
            "value": f.member_group_ids(db, field, member.id) if field.format == "group" else stored.get(field.id),
        }
        for field in f.fields(db, member.ecole_id, member.saison_id)
    ]


def all_answers(db: Session, org_id: int, season_id: int) -> dict[int, dict[int, object]]:
    """Les réponses de toutes les fiches de la saison, en une fois, pour le
    tableau des membres : {fiche: {champ: réponse}}."""
    from groups import Group

    result: dict[int, dict[int, object]] = {}
    fields = f.fields(db, org_id, season_id)
    ids = [field.id for field in fields if field.format != "group"]
    if ids:
        for value in db.scalars(select(MemberValue).where(MemberValue.field_id.in_(ids))):
            result.setdefault(value.member_id, {})[value.field_id] = value.value
    for field in fields:
        if field.format == "group":
            rows = db.execute(
                select(GroupMember.member_id, GroupMember.group_id)
                .join(Group, Group.id == GroupMember.group_id)
                .where(Group.parent_id == field.group_id)
                .order_by(GroupMember.group_id)
            )
            for member_id, group_id in rows:
                result.setdefault(member_id, {}).setdefault(field.id, []).append(group_id)
    return result


def _clean(field: MemberField, value):
    """La réponse telle qu'elle est gardée, ou FieldError. None = vide."""
    if value is None or value == "" or value == []:
        return None
    fmt = field.format
    if fmt in MAX_TEXT:
        value = str(value).strip()
        if len(value) > MAX_TEXT[fmt]:
            raise f.FieldError(f"« {field.label} » : trop long")
        if fmt == "phone" and not re.fullmatch(r"[0-9+ ().-]*", value):
            raise f.FieldError(f"« {field.label} » : numéro de téléphone invalide")
        if fmt == "postal_code" and not re.fullmatch(r"[0-9A-Za-z -]*", value):
            raise f.FieldError(f"« {field.label} » : code postal invalide")
        return value or None
    if fmt == "number":
        if isinstance(value, bool):
            raise f.FieldError(f"« {field.label} » : un nombre est attendu")
        try:
            number = float(str(value).replace(",", "."))
        except ValueError:
            raise f.FieldError(f"« {field.label} » : un nombre est attendu") from None
        return int(number) if number.is_integer() else number
    if fmt == "date":
        try:
            return dt.date.fromisoformat(str(value)).isoformat()
        except ValueError:
            raise f.FieldError(f"« {field.label} » : date invalide") from None
    if fmt == "yes_no":
        if not isinstance(value, bool):
            raise f.FieldError(f"« {field.label} » : oui ou non")
        return value
    if fmt == "list":
        chosen = value if isinstance(value, list) else [value]
        if not field.multiple and len(chosen) > 1:
            raise f.FieldError(f"« {field.label} » : un seul choix")
        if any(c not in field.choices for c in chosen):
            raise f.FieldError(f"« {field.label} » : choix inconnu")
        return [c for c in field.choices if c in chosen] if field.multiple else chosen[0]
    raise f.FieldError(f"« {field.label} » : se remplit autrement")


def _store(db: Session, member: Compte, field: MemberField, value) -> None:
    row = db.get(MemberValue, (member.id, field.id))
    if value is None:
        if row is not None:
            db.delete(row)
    elif row is None:
        db.add(MemberValue(member_id=member.id, field_id=field.id, value=value))
    else:
        row.value = value
    db.flush()


def set_external(db: Session, member: Compte, field: MemberField, value) -> None:
    """La réponse d'un champ apporté par un module (`field.source`, ex. la
    réponse HelloAsso), gardée telle que le module la donne : elle ne passe
    pas par les règles de saisie (sans commit)."""
    _store(db, member, field, None if value in (None, "", []) else value)


def _field_of(db: Session, member: Compte, field_id: int) -> MemberField:
    field = db.get(MemberField, field_id)
    if (
        field is None or field.removed_at is not None
        or (field.org_id, field.season_id) != (member.ecole_id, member.saison_id)
    ):
        raise LookupError("Champ introuvable")
    return field


def set_answer(db: Session, member: Compte, field_id: int, value) -> None:
    """Enregistre la réponse (sans commit). Format « Groupe » : `value` est
    la liste des sous-groupes cochés, la fiche entre dans ceux-là et sort
    des autres."""
    field = _field_of(db, member, field_id)
    if field.format == "file":
        if value is not None:
            raise f.FieldError(f"« {field.label} » : envoyez le fichier")
        _store(db, member, field, None)
        return
    if field.format != "group":
        _store(db, member, field, _clean(field, value))
        return
    wanted = set(value or [])
    allowed = {g.id for g in f.children(db, field.group_id)}
    if not wanted <= allowed:
        raise f.FieldError(f"« {field.label} » : groupe introuvable")
    if not field.multiple and len(wanted) > 1:
        raise f.FieldError(f"« {field.label} » : un seul choix")
    current = set(f.member_group_ids(db, field, member.id))
    if current - wanted:
        db.execute(
            delete(GroupMember).where(GroupMember.member_id == member.id, GroupMember.group_id.in_(current - wanted))
        )
    for group_id in sorted(wanted - current):
        db.add(GroupMember(group_id=group_id, member_id=member.id))
    db.flush()
    db.expire(member, ["groups"])


def set_file(db: Session, storage: LocalStorage, member: Compte, field_id: int, source: BinaryIO, name: str) -> dict:
    """Format « Fichier à télécharger » : range le fichier (storage/) et le
    garde comme réponse (sans commit)."""
    field = _field_of(db, member, field_id)
    if field.format != "file":
        raise f.FieldError(f"« {field.label} » n'attend pas de fichier")
    sha256, size = storage.put(member.ecole_id, source)
    value = {"sha256": sha256, "name": (name or "fichier")[-200:], "size": size}
    _store(db, member, field, value)
    return value


def file_of(db: Session, member: Compte, field_id: int) -> dict:
    """La réponse d'un champ fichier ({"sha256", "name", "size"}), ou LookupError."""
    field = _field_of(db, member, field_id)
    row = db.get(MemberValue, (member.id, field.id))
    if field.format != "file" or row is None:
        raise LookupError("Fichier introuvable")
    return row.value



def known_values(db: Session, org_id: int, season_id: int) -> dict[int, dict[str, object]]:
    """Les réponses aux champs marqués (`fields.KNOWN`), retirés compris,
    de toutes les fiches de la saison : {fiche: {clé: réponse}}."""
    rows = db.execute(
        select(MemberValue.member_id, MemberField.key, MemberValue.value)
        .join(MemberField, MemberField.id == MemberValue.field_id)
        .where(MemberField.org_id == org_id, MemberField.season_id == season_id, MemberField.key.is_not(None))
    )
    result: dict[int, dict[str, object]] = {}
    for member_id, key, value in rows:
        result.setdefault(member_id, {})[key] = value
    return result


def known_of(db: Session, member: Compte) -> dict[str, object]:
    """Les réponses d'une fiche aux champs marqués : {clé: réponse}."""
    rows = db.execute(
        select(MemberField.key, MemberValue.value)
        .join(MemberField, MemberField.id == MemberValue.field_id)
        .where(MemberValue.member_id == member.id, MemberField.key.is_not(None))
    )
    return dict(rows.all())


def set_known(db: Session, member: Compte, key: str, value) -> None:
    """Enregistre la réponse au champ marqué `key` (sans commit), même s'il
    est retiré de la fiche. Une date peut être un `datetime.date`."""
    field = f.known(db, member.ecole_id, member.saison_id)[key]
    _store(db, member, field, _clean(field, value.isoformat() if isinstance(value, dt.date) else value))


def birth_date(values: dict[str, object]) -> dt.date | None:
    """La date de naissance parmi des réponses {clé: réponse}."""
    value = values.get("birth_date")
    return dt.date.fromisoformat(value) if value else None
