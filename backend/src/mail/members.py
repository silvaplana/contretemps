"""« Écrire aux adhérents » (spec/modules/mail.md §7 bis ; Seb, 19 novembre
2026) : tout le monde (adhérents, administrateurs et professeurs : toutes les
fiches de la saison), ou des cours, chacun son propre mail par Brevo
(`ecoles.mail_ecole.envoyer_a_chacun`) ; personne ne voit l'adresse des
autres. Les réponses vont à la boîte du « De », qui garde le mail dans
« Envoyés »."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from comptes import Compte
from cours.models import Cours
from groups.board import BOARD
from groups.models import Group, GroupMember
from groups.teachers import TEACHERS
from saisons.models import Saison
from saisons.portee import toutes_saisons
from saisons.saisons import saison_courante_id
from sqlalchemy import select
from sqlalchemy.orm import Session


EVERYONE = "Tout le monde"


@dataclass
class Recipients:
    label: str  # « Tout le monde » ou les noms des cours, et le nombre
    people: int  # fiches choisies
    addresses: list[str]  # une par adresse (une famille qui partage une adresse : un mail)
    without: int  # fiches sans adresse mail


def _recipients(members: list[Compte], label: str = EVERYONE) -> Recipients:
    addresses = {a.lower(): a for m in members for a in m.emails}
    return Recipients(
        label=f"{label} · {len(members)}",
        people=len(members),
        addresses=sorted(addresses.values(), key=str.lower),
        without=sum(1 for m in members if not m.emails),
    )


def _member_ids(group_ids):
    """Les fiches de ces groupes et de leurs sous-groupes (Bureau ›
    Président·e…)."""
    children = select(Group.id).where(Group.parent_id.in_(group_ids))
    return select(GroupMember.member_id).where(GroupMember.group_id.in_(group_ids) | GroupMember.group_id.in_(children))


def _members(
    db: Session, org_id: int, season_id: int | None, course_ids: list[int] | None = None,
    group_ids: list[int] | None = None,
) -> list[Compte]:
    """Les fiches de la saison ; avec des cours ou des groupes, celles qui en
    sont (une fiche dans deux cours ou groupes une seule fois)."""
    query = select(Compte).where(Compte.ecole_id == org_id, Compte.saison_id == season_id)
    if course_ids or group_ids:
        of_courses = select(Cours.group_id).where(
            Cours.ecole_id == org_id, Cours.saison_id == season_id, Cours.id.in_(course_ids or [])
        )
        of_groups = select(Group.id).where(
            Group.org_id == org_id, Group.season_id == season_id, Group.id.in_(group_ids or [])
        )
        query = query.where(Compte.id.in_(_member_ids(of_courses.union(of_groups).scalar_subquery())))
    with toutes_saisons(db):
        return list(db.scalars(query))


def _admin_groups(db: Session, org_id: int, season_id: int | None) -> list[Group]:
    """Les groupes d'Admin › Administrateurs qu'on peut joindre : Bureau, Profs,
    puis les groupes faits à la main (pas les droits 🔒 ni les cours)."""
    with toutes_saisons(db):
        rows = list(db.scalars(
            select(Group).where(
                Group.org_id == org_id, Group.season_id == season_id, Group.parent_id.is_(None),
                Group.key.is_(None) | Group.key.in_((BOARD, TEACHERS)),
            )
        ))
    order = {BOARD: 0, TEACHERS: 1}
    return sorted(rows, key=lambda g: (order.get(g.key, 2), g.name.lower()))


def choices(db: Session, org_id: int) -> dict:
    """L'écran « Écrire à un groupe » : la saison, ses cours et ses groupes,
    avec le nombre de personnes."""
    season_id = saison_courante_id(db, org_id)
    season = db.get(Saison, season_id) if season_id is not None else None
    everyone = _recipients(_members(db, org_id, season_id))
    with toutes_saisons(db):
        cours = list(
            db.scalars(select(Cours).where(Cours.ecole_id == org_id, Cours.saison_id == season_id).order_by(Cours.ordre))
        )
    courses = [
        {"id": c.id, "name": c.nom, "people": len(_members(db, org_id, season_id, course_ids=[c.id]))} for c in cours
    ]
    groups = [
        {"id": g.id, "name": g.name, "people": len(_members(db, org_id, season_id, group_ids=[g.id]))}
        for g in _admin_groups(db, org_id, season_id)
    ]
    return {
        "season": season.nom if season else "",
        "people": everyone.people,
        "without": everyone.without,
        "courses": courses,
        "groups": [g for g in groups if g["people"] > 0],
    }


def recipients(
    db: Session, org_id: int, course_ids: list[int] | None, group_ids: list[int] | None = None,
) -> Recipients:
    """Tout le monde (ni cours ni groupe) ou ceux des cours et des groupes."""
    season_id = saison_courante_id(db, org_id)
    label = EVERYONE
    if course_ids or group_ids:
        with toutes_saisons(db):
            names = list(db.scalars(
                select(Cours.nom).where(Cours.ecole_id == org_id, Cours.id.in_(course_ids or [])).order_by(Cours.ordre)
            )) + list(db.scalars(
                select(Group.name).where(Group.org_id == org_id, Group.id.in_(group_ids or [])).order_by(Group.name)
            ))
        label = ", ".join(names) or label
    return _recipients(_members(db, org_id, season_id, course_ids, group_ids), label)


def content(school: str, subject: str, body: str):
    """(sujet, texte, html), le même pour chacun."""
    footer = f"Mail de {school}. Pour répondre, répondez à ce mail."
    text = f"{body}\n\n{footer}"
    html = (
        '<div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.5;color:#1f1f1f">'
        f"{escape(body).replace(chr(10), '<br>')}"
        f'<p style="margin-top:24px;font-size:13px;color:#6c6a62">{escape(footer)}</p></div>'
    )
    return subject, text, html
