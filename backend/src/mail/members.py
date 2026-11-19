"""« Écrire aux adhérents » (spec/modules/mail.md §7 bis ; Seb, 19 novembre
2026) : tous les adhérents de la saison, ou des cours, chacun son propre mail
par Brevo (`ecoles.mail_ecole.envoyer_a_chacun`) ; personne ne voit l'adresse
des autres. Les réponses et une copie vont à la boîte du « De »."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape

from comptes import Compte
from cours.models import Cours
from groups.models import GroupMember
from saisons.models import Saison
from saisons.portee import toutes_saisons
from saisons.saisons import saison_courante_id
from sqlalchemy import select
from sqlalchemy.orm import Session


@dataclass
class Recipients:
    people: int  # fiches choisies
    addresses: list[str]  # une par adresse (une famille qui partage une adresse : un mail)
    without: int  # fiches sans adresse mail


def _recipients(members: list[Compte]) -> Recipients:
    addresses = {a.lower(): a for m in members for a in m.emails}
    return Recipients(
        people=len(members),
        addresses=sorted(addresses.values(), key=str.lower),
        without=sum(1 for m in members if not m.emails),
    )


def _members(db: Session, org_id: int, season_id: int | None, course_ids: list[int] | None) -> list[Compte]:
    """Les fiches de la saison ; avec `course_ids`, celles de ces cours (une
    fiche inscrite à deux cours une seule fois)."""
    query = select(Compte).where(Compte.ecole_id == org_id, Compte.saison_id == season_id)
    if course_ids is not None:
        groups = select(Cours.group_id).where(
            Cours.ecole_id == org_id, Cours.saison_id == season_id, Cours.id.in_(course_ids)
        )
        query = query.where(Compte.id.in_(select(GroupMember.member_id).where(GroupMember.group_id.in_(groups))))
    with toutes_saisons(db):
        return list(db.scalars(query))


def choices(db: Session, org_id: int) -> dict:
    """L'écran « Écrire aux adhérents » : la saison et ses cours, avec le
    nombre de personnes."""
    season_id = saison_courante_id(db, org_id)
    season = db.get(Saison, season_id) if season_id is not None else None
    everyone = _recipients(_members(db, org_id, season_id, None))
    with toutes_saisons(db):
        cours = list(
            db.scalars(select(Cours).where(Cours.ecole_id == org_id, Cours.saison_id == season_id).order_by(Cours.ordre))
        )
    courses = []
    for c in cours:
        r = _recipients(_members(db, org_id, season_id, [c.id]))
        courses.append({"id": c.id, "name": c.nom, "people": r.people})
    return {
        "season": season.nom if season else "",
        "people": everyone.people,
        "without": everyone.without,
        "courses": courses,
    }


def recipients(db: Session, org_id: int, course_ids: list[int] | None) -> Recipients:
    """Tous les adhérents (`course_ids` vide ou absent) ou ceux des cours."""
    return _recipients(_members(db, org_id, saison_courante_id(db, org_id), course_ids or None))


def content(school: str, subject: str, body: str, address: str, copy_to: str, people: int):
    """(sujet, texte, html) pour une adresse ; la copie de la boîte dit à qui
    le mail est parti."""
    footer = f"Vous recevez ce mail parce que vous êtes adhérent de {school}. Pour répondre, répondez à ce mail."
    if address.lower() == copy_to.lower():
        footer = f"Copie du mail envoyé à {people} adhérent{'s' if people > 1 else ''} de {school}."
    text = f"{body}\n\n{footer}"
    html = (
        '<div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.5;color:#1f1f1f">'
        f"{escape(body).replace(chr(10), '<br>')}"
        f'<p style="margin-top:24px;font-size:13px;color:#6c6a62">{escape(footer)}</p></div>'
    )
    return subject, text, html
