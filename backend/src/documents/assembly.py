"""Assemblée générale : convocation, présence et procurations (spec
procurations.md). Posé sur le fichier de base : la convocation est un
fichier Questionner qui contient un bloc « Présence et procuration »
(`assembly`) ; l'envoi, les liens personnels et les réponses sont ceux de
tous les fichiers de l'appli. Ce module ajoute :

- la convocation toute prête (`convene`), rangée dans Réunions ;
- les règles d'une procuration, qui dépendent des autres réponses
  (plafond, pas de chaîne, membre convoqué), contrôlées à chaque réponse ;
- le pouvoir signé en PDF, rangé dans « Pouvoirs » à côté de la convocation ;
- le décompte (présents, procurations, quorum), le récapitulatif PDF et Excel.

Tous les chiffres sont calculés ici, jamais par l'assistant.
"""

from __future__ import annotations

import base64
import io
import logging
import math
import re
from datetime import datetime
from html import escape
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pymupdf
from openpyxl import Workbook
from openpyxl.styles import Font
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import app_content
from .app_content import ContentError
from .models import (
    KIND_APP,
    KIND_FOLDER,
    LEVEL_EDIT,
    SYSTEM_PERIOD,
    DocActivity,
    DocAttendance,
    DocNode,
    DocResponse,
    DocSend,
    utcnow,
)
from .ports import Member

if TYPE_CHECKING:
    from .service import Documents

logger = logging.getLogger(__name__)

# Les heures de l'assemblée sont celles de l'école.
TZ = ZoneInfo("Europe/Paris")
KIND_WORDS = {"ordinary": "ordinaire", "extraordinary": "extraordinaire"}
KIND_SHORT = {"ordinary": "AGO", "extraordinary": "AGE"}
ANSWER_WORDS = {"attend": "Vient", "proxy": "Procuration", "absent": "Ne vient pas", "none": "Pas encore répondu"}
BASE_AGENDA = {
    "ordinary": [
        "Rapport moral",
        "Rapport financier et approbation des comptes",
        "Budget prévisionnel",
        "Renouvellement du bureau",
        "Questions diverses",
    ],
    "extraordinary": ["Modification des statuts", "Questions diverses"],
}
DAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
CHOICES = (("attend", "Je viens"), ("proxy", "Je donne procuration"), ("absent", "Je ne viens pas"))
PROXIES_FOLDER = "Pouvoirs"
MEETINGS_FOLDER = "Réunions"


# ----------------------------------------------------------------------
# Dates et textes
# ----------------------------------------------------------------------


def parse_start(value: str | None) -> datetime | None:
    """« 2026-11-21T14:00 », heure de l'école."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value)).replace(tzinfo=None, second=0, microsecond=0)
    except (TypeError, ValueError):
        return None


def day_text(start: datetime) -> str:
    """« 21 novembre 2026 »."""
    return f"{start.day}{'er' if start.day == 1 else ''} {MONTHS[start.month - 1]} {start.year}"


def when_text(start: datetime) -> str:
    """« samedi 21 novembre 2026 à 14 h » (« 14 h 30 »)."""
    heure = f"{start.hour} h" + (f" {start.minute:02d}" if start.minute else "")
    return f"{DAYS[start.weekday()]} {day_text(start)} à {heure}"


def assembly_title(kind: str, start: datetime) -> str:
    return f"{KIND_SHORT[kind]} du {day_text(start)}"


def now_local() -> datetime:
    return datetime.now(TZ).replace(tzinfo=None)


def proxy_sentence(mandant: str, org_name: str, holder: str, kind: str, start: datetime | None, blank_to: str) -> str:
    """Le texte du pouvoir (spec §3.3), rempli par le code."""
    qui = (
        f"la personne désignée par le bureau{f' (à défaut, {blank_to})' if blank_to else ''}"
        if holder == "blank"
        else holder
    )
    quand = f" du {day_text(start)}" if start else ""
    return (
        f"Je soussigné(e) {mandant}, membre de {org_name}, donne pouvoir à {qui} pour me représenter "
        f"à l'assemblée générale {KIND_WORDS.get(kind, 'ordinaire')}{quand} et prendre part aux votes en mon nom."
    )


def _norm(texte: str) -> str:
    from .service import normalize_search

    return normalize_search(texte)


# ----------------------------------------------------------------------
# Qui est convoqué, qui peut représenter
# ----------------------------------------------------------------------


def block_of(content: dict) -> dict | None:
    return app_content.assembly_block(content)


def props(block: dict) -> dict:
    p = block.get("props") or {}
    return {
        "kind": p.get("kind") or "ordinary",
        "start": parse_start(p.get("startsAt")),
        "max": p.get("maxProxies", 2) if isinstance(p.get("maxProxies", 2), int) else 2,
        "blank_to": str(p.get("blankTo") or ""),
        "quorum": p.get("quorum") or "none",
    }


def convoked(db: Session, node: DocNode) -> dict[int, str]:
    """Les membres convoqués : ceux à qui le fichier est parti (envoi réel)."""
    return {
        s.person_id: s.name
        for s in db.scalars(
            select(DocSend).where(DocSend.node_id == node.id, DocSend.test.is_(False), DocSend.channel == "email")
            .order_by(DocSend.name)
        )
        if s.person_id is not None
    }


def default_principals(docs: Documents, db: Session, node: DocNode) -> list[dict]:
    """À qui proposer d'envoyer : les convoqués de la dernière AG, sinon
    tous les membres (réglage de l'appli hôte)."""
    precedente = _previous(db, node.org_id, exclude=node.id, sent_only=True)
    if precedente is not None:
        gens = convoked(db, precedente)
        if gens:
            return [{"type": "member", "id": str(pid)} for pid in gens]
    return [{"type": t, "id": i} for t, i in docs.members]


def candidates(docs: Documents, db: Session, node: DocNode) -> dict[int, str]:
    """Qui peut recevoir une procuration : les convoqués ; avant le premier
    envoi (un essai), ceux qui seront convoqués par défaut."""
    gens = convoked(db, node)
    if gens:
        return gens
    cibles = [(p["type"], p["id"]) for p in default_principals(docs, db, node)]
    return {r.person_id: r.name for r in docs.directory.recipients(db, node.org_id, cibles)}


def _answers(db: Session, node: DocNode, block_id: str, real_only: bool = True) -> list[DocResponse]:
    requete = select(DocResponse).where(DocResponse.node_id == node.id)
    if real_only:
        requete = requete.where(DocResponse.is_test.is_(False))
    return [r for r in db.scalars(requete.order_by(DocResponse.id)) if isinstance((r.values or {}).get(block_id), dict)]


def _holds(answers: list[DocResponse], block_id: str, exclude: int | None = None) -> dict[int, list[int]]:
    """Pouvoirs nommés reçus : mandataire -> mandants."""
    recus: dict[int, list[int]] = {}
    for r in answers:
        v = r.values[block_id]
        if r.id != exclude and v.get("answer") == "proxy" and isinstance(v.get("proxy_to"), int):
            recus.setdefault(v["proxy_to"], []).append(r.person_id)
    return recus


def link_context(docs: Documents, db: Session, node: DocNode, content: dict, person_id: int | None) -> dict | None:
    """Ce que la page du membre doit savoir pour le bloc (lien personnel,
    Aperçu) : qui peut le représenter, et qui en a déjà assez."""
    bloc = block_of(content)
    if bloc is None:
        return None
    p = props(bloc)
    reponses = _answers(db, node, bloc["id"])
    mien = next((r.id for r in reponses if r.person_id == person_id), None)
    recus = _holds(reponses, bloc["id"], exclude=mien)
    a_donne = {r.person_id for r in reponses if r.values[bloc["id"]].get("answer") == "proxy" and r.id != mien}
    gens = []
    for pid, nom in sorted(candidates(docs, db, node).items(), key=lambda x: _norm(x[1])):
        if pid == person_id:
            continue
        n = len(recus.get(pid, []))
        plein = bool(p["max"]) and n >= p["max"]
        gens.append({
            "id": pid, "name": nom, "holds": n,
            "full": plein or pid in a_donne,
            "why": "a déjà donné procuration" if pid in a_donne else f"a déjà {n} pouvoirs" if plein else "",
        })
    ecole = docs.mailer.org(db, node.org_id)[0] if docs.mailer is not None else ""
    return {
        "block_id": bloc["id"],
        "kind": p["kind"],
        "starts_at": p["start"].isoformat(timespec="minutes") if p["start"] else None,
        "closed": bool(p["start"] and now_local() >= p["start"]),
        "max": p["max"],
        "blank_to": p["blank_to"],
        "org_name": ecole,
        "received": len(recus.get(person_id, [])) if person_id else 0,
        "candidates": gens,
    }


# ----------------------------------------------------------------------
# Une réponse
# ----------------------------------------------------------------------


def check_answer(
    docs: Documents, db: Session, node: DocNode, content: dict, values: dict, person_id: int | None,
    response_id: int | None, test: bool, previous: dict | None = None,
) -> dict:
    """Les règles d'une procuration (spec §3.4) ; complète la réponse avec
    le nom du mandataire et l'heure de signature. Lève ContentError."""
    bloc = block_of(content)
    if bloc is None or bloc["id"] not in values:
        return values
    p = props(bloc)
    if not test and p["start"] and now_local() >= p["start"]:
        raise ContentError("L'assemblée a commencé : la réponse ne peut plus changer.")
    v = dict(values[bloc["id"]])
    if v["answer"] != "proxy":
        values[bloc["id"]] = v
        return values
    if person_id is None:
        raise ContentError("Une procuration se donne depuis son lien personnel, reçu par email.")
    qui = v["proxy_to"]
    reponses = _answers(db, node, bloc["id"])
    if qui != "blank":
        if qui == person_id:
            raise ContentError("Vous ne pouvez pas vous donner procuration à vous-même.")
        gens = candidates(docs, db, node)
        if qui not in gens:
            raise ContentError("Cette personne n'est pas convoquée à l'assemblée : choisissez quelqu'un d'autre.")
        v["proxy_name"] = gens[qui]
        if not test:
            sienne = next((r for r in reponses if r.person_id == qui), None)
            if sienne is not None and sienne.values[bloc["id"]].get("answer") == "proxy":
                raise ContentError(f"{gens[qui]} a lui-même donné procuration : choisissez quelqu'un d'autre.")
            recus = _holds(reponses, bloc["id"], exclude=response_id)
            if p["max"] and len(recus.get(qui, [])) >= p["max"]:
                raise ContentError(f"{gens[qui]} a déjà {p['max']} pouvoirs : choisissez quelqu'un d'autre.")
    if not test:
        mes_mandants = _holds(reponses, bloc["id"], exclude=response_id).get(person_id, [])
        if mes_mandants:
            noms = docs.directory.person_names(db, node.org_id, set(mes_mandants))
            liste = " et ".join(noms.get(m, "?") for m in mes_mandants)
            raise ContentError(
                f"Vous avez reçu {len(mes_mandants)} pouvoir{'s' if len(mes_mandants) > 1 else ''} : venez à l'assemblée, "
                f"ou prévenez {liste} pour qu'ils choisissent quelqu'un d'autre."
            )
    avant = previous or {}
    meme = avant.get("answer") == "proxy" and avant.get("proxy_to") == qui and avant.get("signature") == v["signature"]
    v["signed_at"] = avant.get("signed_at") if meme and avant.get("signed_at") else utcnow().isoformat(timespec="seconds")
    if meme and avant.get("pdf_id"):
        v["pdf_id"] = avant["pdf_id"]
    values[bloc["id"]] = v
    return values


def _system_member(node: DocNode, person_id: int | None) -> Member:
    """L'appli range le pouvoir à la place du membre (qui n'a pas de compte
    dans Docs) : avec les droits d'un admin de l'école."""
    return Member(
        person_id=node.created_by or person_id or 0, org_id=node.org_id, display_name="Contretemps",
        is_admin=True, groups=frozenset({"role:admin"}),
    )


def after_answer(docs: Documents, db: Session, node: DocNode, response: DocResponse, mandant: str, previous: dict | None) -> None:
    """Après une vraie réponse : le pouvoir signé est enregistré en PDF dans
    « Pouvoirs » ; un pouvoir remplacé ou retiré garde son PDF, marqué
    « retiré ». Un échec ici ne perd jamais la réponse."""
    from .app_files import AppFiles

    version = AppFiles.current_version(db, node)
    bloc = block_of(version.content) if version else None
    if bloc is None or node.parent_id is None or node.space == "personal":
        return
    v = dict((response.values or {}).get(bloc["id"]) or {})
    avant = previous or {}
    try:
        systeme = _system_member(node, response.person_id)
        if avant.get("pdf_id") and avant.get("pdf_id") != v.get("pdf_id"):
            ancien = db.get(DocNode, avant["pdf_id"])
            if ancien is not None and ancien.deleted_at is None and "(retiré" not in ancien.name:
                nom = ancien.name.removesuffix(".pdf") + f" (retiré le {now_local():%d-%m-%Y}).pdf"
                docs.update(db, systeme, ancien.id, name=nom)
        if v.get("answer") != "proxy" or v.get("pdf_id"):
            return
        p = props(bloc)
        ecole = docs.mailer.org(db, node.org_id)[0] if docs.mailer is not None else ""
        pdf = proxy_pdf(mandant, ecole, v, p, node.name)
        dossier = _child_folder(docs, db, systeme, node.parent_id, PROXIES_FOLDER)
        qui = "le bureau" if v["proxy_to"] == "blank" else v.get("proxy_name", "")
        de = "d'" if _norm(mandant)[:1] in tuple("aeiouyh") else "de "
        cree = docs.upload(db, systeme, node.space, dossier, f"Pouvoir {de}{mandant} à {qui}.pdf", io.BytesIO(pdf))
        v["pdf_id"] = cree["id"]
        response.values = {**response.values, bloc["id"]: v}
        db.commit()
    except Exception:  # le pouvoir reste dans les réponses
        logger.exception("Pouvoir non rangé en PDF (fichier %s, réponse %s)", node.id, response.id)
        db.rollback()
        return
    _send_copies(docs, db, node, response, v, p, mandant, ecole, pdf)


def _letter(person: str, paragraphs: list[str], org_name: str) -> tuple[str, str]:
    """Un email simple (texte et HTML), écrit comme ceux de Diffuser."""
    lignes = [f"Bonjour {person},", *paragraphs, f"Message envoyé par {org_name}."]
    texte = "\n\n".join(lignes) + "\n"
    html = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;color:#222;max-width:520px">'
        + "".join(f'<p style="margin:0 0 16px;white-space:pre-line">{escape(x)}</p>' for x in lignes)
        + "</div>"
    )
    return texte, html


def _send_copies(
    docs: Documents, db: Session, node: DocNode, response: DocResponse, v: dict, p: dict, mandant: str,
    org_name: str, pdf: bytes,
) -> None:
    """Étape 3 (spec §1.1) : le mandataire apprend qu'il a un pouvoir, le
    mandant reçoit la copie de son pouvoir signé ; le PDF est joint. Un
    échec d'envoi est noté, la réponse reste."""
    if docs.mailer is None or not docs.mailer.available:
        return
    assemblee = f"l'assemblée générale du {day_text(p['start'])}" if p["start"] else "l'assemblée générale"
    quand = f" le {when_text(p['start'])}" if p["start"] else ""
    piece = [("Pouvoir.pdf", pdf)]
    mails = []
    if v["proxy_to"] != "blank":
        porteur = docs.directory.recipients(db, node.org_id, [("member", str(v["proxy_to"]))])
        if porteur and porteur[0].email:
            mails.append((porteur[0].email, f"{mandant} vous a donné procuration pour {assemblee}", _letter(porteur[0].name, [
                f"{mandant} vous a donné procuration : vous voterez en son nom à {assemblee}{quand}.",
                "Son pouvoir signé est joint à ce mail.",
                (
                    f"Si vous ne pouvez pas venir, prévenez {mandant}, qui peut choisir quelqu'un d'autre avec son lien "
                    "jusqu'au début de l'assemblée. Sans vous, son pouvoir sera perdu."
                ),
            ], org_name)))
    envoi = db.scalar(
        select(DocSend).where(DocSend.node_id == node.id, DocSend.person_id == response.person_id,
                              DocSend.channel == "email", DocSend.test.is_(False))
    )
    if response.email and envoi is not None:
        adresse = docs.mailer.org(db, node.org_id)[1]
        qui = "le bureau désignera la personne qui vous représente" if v["proxy_to"] == "blank" else f"{v.get('proxy_name', '')} vous représentera"
        mails.append((response.email, f"Votre procuration pour {assemblee}", _letter(mandant, [
            f"Votre procuration est enregistrée : {qui} à {assemblee}{quand}.",
            "Votre pouvoir signé est joint à ce mail.",
            f"Vous pouvez changer d'avis avec le même lien jusqu'au début de l'assemblée :\n{adresse}/r/{envoi.token}",
        ], org_name)))
    for a, sujet, (texte, html) in mails:
        try:
            docs.mailer.send(a, sujet, texte, html, org_name, None, piece)
        except Exception as erreur:  # noqa: BLE001 (la réponse est enregistrée)
            logger.warning("Copie du pouvoir non envoyée à %s : %s", a, erreur)


# ----------------------------------------------------------------------
# La relance sept jours avant (étape 3)
# ----------------------------------------------------------------------

REMIND_DAYS = 7


def non_respondents(db: Session, node: DocNode) -> list[DocSend]:
    """Les convoqués sans réponse, joignables par email."""
    return list(db.scalars(select(DocSend).where(
        DocSend.node_id == node.id, DocSend.test.is_(False), DocSend.channel == "email",
        DocSend.status == "sent", DocSend.answered_at.is_(None), DocSend.email.is_not(None),
    ).order_by(DocSend.name)))


def _reminder_jobs(db: Session, mailer, directory, node: DocNode, content: dict, cibles: list[DocSend], rappel: str) -> list[dict]:
    """Le mail de la convocation, précédé du rappel, avec le lien de chacun."""
    from .app_sends import compose

    ecole, adresse = mailer.org(db, node.org_id)
    qui = cibles[0].sent_by if cibles else None
    expediteur = directory.person_names(db, node.org_id, {qui}).get(qui, ecole) if qui else ecole
    jobs = []
    for s in cibles:
        sujet, texte, html = compose(
            node.name, node.family, content, s.name, rappel, f"{adresse}/r/{s.token}", ecole, expediteur, False, False,
        )
        jobs.append({"to": s.email, "subject": f"Rappel : {sujet}", "text": texte, "html": html, "sender_name": ecole})
    return jobs


def send_reminders(mailer, jobs: list[dict]) -> int:
    """Fait partir les rappels ; rend le nombre d'emails envoyés."""
    total = 0
    for job in jobs:
        try:
            mailer.send(job["to"], job["subject"], job["text"], job["html"], job["sender_name"], None)
            total += 1
        except Exception as erreur:  # noqa: BLE001 (on continue avec les autres)
            logger.warning("Relance de l'AG non envoyée à %s : %s", job["to"], erreur)
    return total


def remind(docs: Documents, db: Session, member: Member, node_id: int) -> tuple[dict, list[dict]]:
    """Relancer maintenant les convoqués sans réponse (Résultats, ou
    l'assistant). Rend (récapitulatif, emails à faire partir)."""
    from .service import DocError

    node, contenu = _node_for(docs, db, member, node_id)
    debut = props(block_of(contenu))["start"]
    if node.status != "official":
        raise DocError(409, "La convocation n'est pas encore validée.")
    if debut is not None and now_local() >= debut:
        raise DocError(409, "L'assemblée a commencé : les réponses sont fermées.")
    if docs.mailer is None or not docs.mailer.available:
        raise DocError(409, "L'envoi d'emails n'est pas configuré sur ce serveur.")
    cibles = non_respondents(db, node)
    if not cibles:
        raise DocError(409, "Tout le monde a répondu : personne à relancer.")
    quand = f", le {when_text(debut)}" if debut else ""
    jobs = _reminder_jobs(
        db, docs.mailer, docs.directory, node, contenu, cibles,
        f"Rappel : l'assemblée a lieu bientôt{quand}, et nous n'avons pas encore votre réponse.",
    )
    docs._log(db, member, node, "reminded", {"count": len(cibles)})
    db.commit()
    return {"sent": len(jobs)}, jobs


def remind_due(db: Session, mailer, directory, now: datetime | None = None) -> int:
    """Sept jours avant l'assemblée, relance une fois les convoqués qui n'ont
    pas répondu, avec leur lien. Seulement si la convocation est partie avant
    J-7 (sinon elle vient d'arriver). Appelé chaque minute par
    `app.relance_worker` ; rend le nombre d'emails envoyés. Une relance
    faite à la main avant ne l'empêche pas."""
    from datetime import UTC, timedelta

    from .app_files import AppFiles

    if mailer is None or not mailer.available:
        return 0
    now = now or now_local()
    deja = select(DocActivity.node_id).where(DocActivity.action == "reminded", DocActivity.person_id.is_(None))
    attente = select(DocSend.node_id).where(
        DocSend.test.is_(False), DocSend.channel == "email", DocSend.status == "sent", DocSend.answered_at.is_(None),
    )
    fichiers = db.scalars(select(DocNode).where(
        DocNode.kind == KIND_APP, DocNode.status == "official", DocNode.deleted_at.is_(None),
        DocNode.id.in_(attente), DocNode.id.not_in(deja),
    ))
    total = 0
    for node in list(fichiers):
        version = AppFiles.current_version(db, node)
        bloc = block_of(version.content) if version else None
        debut = props(bloc)["start"] if bloc else None
        if debut is None or not debut - timedelta(days=REMIND_DAYS) <= now < debut:
            continue
        parti = db.scalar(select(func.min(DocSend.sent_at)).where(
            DocSend.node_id == node.id, DocSend.test.is_(False), DocSend.channel == "email",
        ))
        if parti is None or parti.replace(tzinfo=UTC).astimezone(TZ).replace(tzinfo=None) > debut - timedelta(days=REMIND_DAYS):
            continue
        cibles = non_respondents(db, node)
        # Noté avant d'envoyer : jamais deux relances, même si l'envoi casse.
        db.add(DocActivity(org_id=node.org_id, node_id=node.id, person_id=None, action="reminded", detail={"count": len(cibles)}))
        db.commit()
        rappel = f"Rappel : l'assemblée a lieu dans une semaine, le {when_text(debut)}, et nous n'avons pas encore votre réponse."
        total += send_reminders(mailer, _reminder_jobs(db, mailer, directory, node, version.content, cibles, rappel))
    return total


def _child_folder(docs: Documents, db: Session, member: Member, parent_id: int, name: str) -> int:
    for n in db.scalars(select(DocNode).where(DocNode.parent_id == parent_id, DocNode.kind == KIND_FOLDER, DocNode.deleted_at.is_(None))):
        if _norm(n.name) == _norm(name):
            return n.id
    parent = db.get(DocNode, parent_id)
    return docs.create_folder(db, member, parent.space, parent_id, name)["id"]


# ----------------------------------------------------------------------
# Le décompte
# ----------------------------------------------------------------------


def summary(docs: Documents, db: Session, node: DocNode, content: dict) -> dict | None:
    bloc = block_of(content)
    if bloc is None:
        return None
    p = props(bloc)
    gens = convoked(db, node)
    toutes = _answers(db, node, bloc["id"], real_only=False)
    vraies = {r.person_id: r for r in toutes if not r.is_test and r.person_id in gens}
    reponse = lambda pid: vraies[pid].values[bloc["id"]] if pid in vraies else {}
    viennent = {pid for pid in gens if reponse(pid).get("answer") == "attend"}
    procurations = {pid for pid in gens if reponse(pid).get("answer") == "proxy"}
    recus: dict = {}
    for pid in sorted(procurations, key=lambda x: _norm(gens[x])):
        recus.setdefault(reponse(pid).get("proxy_to"), []).append(pid)
    # Un pouvoir compte si son représentant vient ; il est perdu s'il a dit
    # qu'il ne viendrait pas ; en attente tant qu'il n'a pas répondu.
    absents = {pid for pid in gens if reponse(pid).get("answer") in ("absent", "proxy")}
    perdus = sum(len(m) for qui, m in recus.items() if qui in absents)
    portes = sum(len(m) for qui, m in recus.items() if qui == "blank" or qui in viennent)
    voix = len(viennent) + portes
    seuil = {"quarter": 4, "third": 3, "half": 2}.get(p["quorum"])
    lignes = []
    for pid, nom in sorted(gens.items(), key=lambda x: _norm(x[1])):
        v = reponse(pid)
        lignes.append({
            "person_id": pid, "name": nom, "answer": v.get("answer", "none"),
            "proxy_to": v.get("proxy_to"),
            "proxy_name": ("le bureau" if v.get("proxy_to") == "blank" else v.get("proxy_name")) if v.get("answer") == "proxy" else None,
            "signed_at": v.get("signed_at"), "pdf_id": v.get("pdf_id"),
            "holds": len(recus.get(pid, [])),
        })
    essais = [
        {"name": r.email or "Essai", "answer": r.values[bloc["id"]].get("answer"),
         "proxy_name": r.values[bloc["id"]].get("proxy_name") or ("le bureau" if r.values[bloc["id"]].get("proxy_to") == "blank" else None)}
        for r in toutes if r.is_test
    ]
    porteurs = [
        {"name": gens.get(qui, "?"), "person_id": qui, "count": len(m), "from": [gens[x] for x in m],
         "lost": qui in absents, "pending": qui not in viennent and qui not in absents}
        for qui, m in recus.items() if qui != "blank"
    ]
    porteurs.sort(key=lambda h: (-h["count"], _norm(h["name"])))
    if "blank" in recus:
        porteurs.append({"name": "En blanc (au bureau" + (f", à défaut {p['blank_to']})" if p["blank_to"] else ")"),
                         "person_id": None, "count": len(recus["blank"]), "from": [gens[x] for x in recus["blank"]], "lost": False})
    return {
        "kind": p["kind"],
        "starts_at": p["start"].isoformat(timespec="minutes") if p["start"] else None,
        "convoked": len(gens),
        "answered": len(vraies),
        "attend": len(viennent),
        "proxy": len(procurations),
        "absent": sum(1 for pid in gens if reponse(pid).get("answer") == "absent"),
        "none": len(gens) - len(vraies),
        "lost": perdus,
        "quorum": {"rule": p["quorum"], "needed": math.ceil(len(gens) / seuil), "votes": voix, "reached": voix >= math.ceil(len(gens) / seuil)}
        if seuil and gens else None,
        "votes": voix,
        "holders": porteurs,
        "rows": lignes,
        "tests": essais,
    }


QUORUM_WORDS = {"quarter": "un quart", "third": "un tiers", "half": "la moitié"}


def _holder_note(holder: dict) -> str:
    if holder["lost"]:
        return " (ne vient pas : pouvoirs perdus)"
    return " (n'a pas encore répondu)" if holder.get("pending") else ""


def _votes(holder: dict) -> str:
    return "" if holder["person_id"] is None else f"1 + {holder['count']}"


def summary_html(s: dict, title: str, org_name: str) -> str:
    quand = f" · état au {now_local():%d/%m/%Y à %H h %M}"
    parts = [
        f"<p class='org'>{escape(org_name.upper())}</p><h1>Présences et procurations</h1>",
        f"<p class='sub'>{escape(title)}{quand}</p>",
        "<table class='kpi'><tr>"
        + "".join(f"<td><b>{n}</b><br/>{escape(t)}</td>" for n, t in (
            (s["convoked"], "membres convoqués"), (s["attend"], "viennent"), (s["proxy"], "procurations"), (s["absent"], "ne viennent pas"),
        ))
        + "</tr></table>",
    ]
    q = s["quorum"]
    if q:
        etat = "atteint" if q["reached"] else "pas atteint"
        parts.append(
            f"<p class='q'><b>Quorum (prévision)</b> : {q['votes']} voix présentes ou représentées sur {s['convoked']} ; "
            f"il en faut {q['needed']} ({QUORUM_WORDS.get(q['rule'], '')} des membres). {etat.capitalize()}.</p>"
        )
    else:
        parts.append(f"<p class='q'><b>Voix présentes ou représentées (prévision)</b> : {s['votes']} sur {s['convoked']}.</p>")
    viennent = [r["name"] for r in s["rows"] if r["answer"] == "attend"]
    parts.append(f"<h2>Viennent ({len(viennent)})</h2><p>{escape(', '.join(viennent)) or '—'}</p>")
    lignes = "".join(
        f"<tr><td><b>{escape(h['name'])}</b>{_holder_note(h)}</td>"
        f"<td>{escape(', '.join(h['from']))}</td><td>{_votes(h)}</td></tr>"
        for h in s["holders"]
    )
    parts.append(
        "<h2>Procurations : qui représente qui</h2>"
        + (f"<table class='t'><tr><th>MANDATAIRE</th><th>REPRÉSENTE</th><th>VOIX</th></tr>{lignes}</table>" if lignes else "<p>—</p>")
    )
    absents = [r["name"] for r in s["rows"] if r["answer"] == "absent"]
    parts.append(f"<h2>Ne viennent pas, sans procuration ({len(absents)})</h2><p>{escape(', '.join(absents)) or '—'}</p>")
    sans = [r["name"] for r in s["rows"] if r["answer"] == "none"]
    parts.append(f"<h2>Sans réponse ({len(sans)})</h2><p>{escape(', '.join(sans)) or '—'}</p>")
    parts.append(
        "<p class='foot'>Les pouvoirs signés sont rangés un par un en PDF dans le dossier « Pouvoirs ». "
        "Chiffres calculés par l'appli à partir des réponses ; la feuille d'émargement du jour remplace cette prévision.</p>"
    )
    return "".join(parts)


_CSS = """
* { font-family: sans-serif; }
body { font-size: 10pt; color: #15211f; }
.org { font-size: 9pt; color: #0f7b6c; font-weight: bold; margin: 0; }
h1 { font-size: 20pt; margin: 4pt 0; }
h2 { font-size: 11pt; margin: 12pt 0 4pt 0; }
.sub { color: #4f5f5b; margin: 0 0 10pt 0; }
.kpi { width: 100%; border-collapse: collapse; }
.kpi td { border: 1px solid #d7dfdc; padding: 6pt; width: 25%; }
.q { background-color: #dcefeb; padding: 6pt; }
.t { width: 100%; border-collapse: collapse; }
.t td, .t th { border-bottom: 1px solid #d7dfdc; padding: 3pt; text-align: left; vertical-align: top; }
.t th { font-size: 8pt; color: #4f5f5b; }
.foot { font-size: 8pt; color: #4f5f5b; margin-top: 14pt; }
.big { font-size: 12pt; line-height: 1.5; }
.small { font-size: 8pt; color: #4f5f5b; }
"""


def _pdf(html: str, extra=None) -> bytes:
    """HTML -> PDF A4 (pymupdf, sans Chromium). `extra(page, y)` dessine
    sous le texte de la dernière page (la signature)."""
    buffer = io.BytesIO()
    page = pymupdf.paper_rect("a4")
    where = page + (48, 48, -48, -48)
    story = pymupdf.Story(html=html, user_css=_CSS)
    writer = pymupdf.DocumentWriter(buffer)
    more, rempli = True, None
    while more:
        device = writer.begin_page(page)
        more, rempli = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    if extra is None:
        return buffer.getvalue()
    doc = pymupdf.open(stream=buffer.getvalue(), filetype="pdf")
    extra(doc[-1], rempli[3] if rempli is not None else 400)
    sortie = doc.tobytes(garbage=3, deflate=True)
    doc.close()
    return sortie


def summary_pdf(s: dict, title: str, org_name: str) -> bytes:
    return _pdf(summary_html(s, title, org_name))


def summary_xlsx(s: dict, title: str) -> bytes:
    classeur = Workbook()
    feuille = classeur.active
    feuille.title = "Réponses"
    feuille.append([title])
    feuille["A1"].font = Font(bold=True, size=13)
    feuille.append([])
    feuille.append(["Membre", "Réponse", "Procuration à", "Signée le", "Pouvoirs reçus"])
    for cellule in feuille[3]:
        cellule.font = Font(bold=True)
    for r in s["rows"]:
        signe = r["signed_at"][:16].replace("T", " ") if r["signed_at"] else ""
        feuille.append([r["name"], ANSWER_WORDS[r["answer"]], r["proxy_name"] or "", signe, r["holds"] or ""])
    for colonne, largeur in zip("ABCDE", (28, 20, 28, 18, 14)):
        feuille.column_dimensions[colonne].width = largeur
    sortie = io.BytesIO()
    classeur.save(sortie)
    return sortie.getvalue()


def proxy_pdf(mandant: str, org_name: str, value: dict, p: dict, title: str) -> bytes:
    """Le pouvoir signé (maquette « Le pouvoir signé »)."""
    qui = "le bureau" if value["proxy_to"] == "blank" else value.get("proxy_name", "")
    phrase = proxy_sentence(mandant, org_name, "blank" if value["proxy_to"] == "blank" else qui, p["kind"], p["start"], p["blank_to"])
    quand = f"{when_text(p['start'])}" if p["start"] else ""
    signe = datetime.fromisoformat(value["signed_at"]).replace(tzinfo=ZoneInfo("UTC")).astimezone(TZ)
    html = (
        f"<p class='org'>{escape(org_name.upper())}</p><p class='small'>Association loi 1901</p>"
        f"<h1>Pouvoir</h1><p class='sub'>{escape(title)}{f' · {escape(quand)}' if quand else ''}</p>"
        f"<p class='big'>{escape(phrase)}</p>"
        f"<p>Fait le {signe.day} {MONTHS[signe.month - 1]} {signe.year} à {signe:%H h %M}.</p>"
        "<p class='small'>Signature du membre :</p>"
    )

    def signature(page, y):
        image = base64.b64decode(value["signature"].split(",", 1)[1])
        page.insert_image(pymupdf.Rect(48, y + 4, 288, y + 84), stream=image, keep_proportion=True)
        page.insert_textbox(
            pymupdf.Rect(48, y + 96, 547, y + 140),
            f"Signé en ligne par lien personnel, le {signe:%d/%m/%Y à %H:%M}. Ce pouvoir peut être retiré avec le même lien "
            "jusqu'au début de l'assemblée ; s'il vient en personne, sa présence l'emporte.",
            fontsize=7, color=(0.31, 0.37, 0.36),
        )

    return _pdf(html, signature)


def _on_day(start: datetime | None) -> str:
    return f" du {day_text(start)}" if start else ""


def convocation_pdf(content: dict, title: str, org_name: str) -> bytes:
    """La convocation à imprimer : le texte du formulaire d'entrée, puis le
    coupon de réponse (avec la procuration à remplir à la main)."""
    lignes = app_content.readable(content, intro_only=False)
    bloc = block_of(content)
    corps = "".join(f"<p class='big'>{escape(x)}</p>" for x in lignes)
    if bloc is not None:
        p = props(bloc)
        corps += (
            "<h2>Réponse</h2><p>☐ Je viens &nbsp;&nbsp; ☐ Je donne procuration &nbsp;&nbsp; ☐ Je ne viens pas</p>"
            "<h2>Pouvoir</h2>"
            f"<p>Je soussigné(e) ……………………………………, membre de {escape(org_name)}, donne pouvoir à …………………………………… "
            f"pour me représenter à l'assemblée générale {KIND_WORDS.get(p['kind'], 'ordinaire')}"
            f"{_on_day(p['start'])} et prendre part aux votes en mon nom.</p>"
            "<p>Fait le …………………… &nbsp;&nbsp;&nbsp; Signature :</p>"
        )
    return _pdf(f"<p class='org'>{escape(org_name.upper())}</p><h1>{escape(title)}</h1>{corps}")


# ----------------------------------------------------------------------
# Convoquer : la convocation toute prête, rangée dans Réunions
# ----------------------------------------------------------------------


def folder_kind(name: str) -> str | None:
    """Un dossier d'AG ? « AG 2026 », « AGO du … », « Assemblée générale
    extraordinaire » : sa sorte si le nom la dit, « any » sinon."""
    mots = re.findall(r"[a-z0-9]+", _norm(name))
    texte = " ".join(mots)
    if not ({"ag", "ago", "age"} & set(mots) or "assemblee generale" in texte):
        return None
    if "age" in mots or "extraordinaire" in mots:
        return "extraordinary"
    if "ago" in mots or "ordinaire" in mots:
        return "ordinary"
    return "any"


def _previous(db: Session, org_id: int, exclude: int | None = None, kind: str | None = None, sent_only: bool = False) -> DocNode | None:
    """La dernière convocation de l'école (de cette sorte)."""
    from .app_files import AppFiles

    noeuds = db.scalars(
        select(DocNode).where(
            DocNode.org_id == org_id, DocNode.kind == KIND_APP, DocNode.deleted_at.is_(None), DocNode.id != (exclude or 0)
        ).order_by(DocNode.created_at.desc(), DocNode.id.desc())
    )
    for n in noeuds:
        version = AppFiles.current_version(db, n)
        bloc = block_of(version.content) if version else None
        if bloc is None or (kind and props(bloc)["kind"] != kind):
            continue
        if sent_only and not convoked(db, n):
            continue
        return n
    return None


def _period_folder(docs: Documents, db: Session, org_id: int) -> DocNode:
    from .service import DocError

    docs.ensure_system_folders(db, org_id)
    courante = next((p for p in docs.periods.list(db, org_id) if p.is_current), None)
    dossier = None
    if courante is not None:
        dossier = db.scalar(
            select(DocNode).where(DocNode.org_id == org_id, DocNode.system_kind == SYSTEM_PERIOD, DocNode.period_id == courante.id)
        )
    if dossier is None:
        raise DocError(409, f"Pas de {docs.period_label.lower()} en cours : créez-la d'abord.")
    return dossier


def _folders(db: Session, parent_id: int) -> list[DocNode]:
    return list(db.scalars(
        select(DocNode).where(DocNode.parent_id == parent_id, DocNode.kind == KIND_FOLDER, DocNode.deleted_at.is_(None))
        .order_by(DocNode.name)
    ))


def find_folder(docs: Documents, db: Session, member: Member, kind: str) -> tuple[int | None, list[dict], int | None]:
    """(dossier Réunions s'il existe, dossiers d'AG possibles, dossier choisi).
    Un seul dossier d'AG libre : il est choisi ; aucun ou plusieurs : rien."""
    saison = _period_folder(docs, db, member.org_id)
    reunions = next((n for n in _folders(db, saison.id) if _norm(n.name) in ("reunion", "reunions")), None)
    if reunions is None:
        return None, [], None
    possibles = []
    for n in _folders(db, reunions.id):
        sorte = folder_kind(n.name)
        if sorte is None or sorte not in ("any", kind) or _used(db, n):
            continue
        possibles.append({"id": n.id, "name": n.name})
    return reunions.id, possibles, possibles[0]["id"] if len(possibles) == 1 else None


def _used(db: Session, folder: DocNode) -> bool:
    """Le dossier contient déjà une convocation envoyée."""
    from .app_files import AppFiles

    for n in db.scalars(select(DocNode).where(DocNode.parent_id == folder.id, DocNode.kind == KIND_APP, DocNode.deleted_at.is_(None))):
        version = AppFiles.current_version(db, n)
        if version and block_of(version.content) is not None and convoked(db, n):
            return True
    return False


def _text(genre: str, texte: str, **p) -> dict:
    import uuid

    return {"id": uuid.uuid4().hex, "type": genre, "props": p, "content": [{"type": "text", "text": texte, "styles": {}}], "children": []}


def convocation_content(kind: str, start: datetime, place: str, agenda: list[str], org_name: str, signer: str) -> dict:
    import uuid

    mot = KIND_WORDS[kind]
    lieu = place or "[lieu à préciser]"
    bloc = {
        "id": uuid.uuid4().hex, "type": "assembly",
        "props": {"label": "Serez-vous là ?", "kind": kind, "startsAt": start.isoformat(timespec="minutes"),
                  "place": place, "maxProxies": 2, "blankTo": signer, "quorum": "none"},
        "content": [], "children": [],
    }
    entree = [
        _text("heading", f"Assemblée générale {mot}", level=1),
        _text("paragraph", "Chers membres,"),
        _text("paragraph", f"Vous êtes convoqués à l'assemblée générale {mot} de {org_name}, le {when_text(start)}, {lieu}."),
        _text("heading", "Ordre du jour", level=2),
        *(_text("numberedListItem", point) for point in agenda),
        _text("paragraph", "Si vous ne pouvez pas venir, vous pouvez donner procuration à un autre membre : il votera pour vous."),
        bloc,
        _text("paragraph", signer),
    ]
    resultat = [
        {"id": uuid.uuid4().hex, "type": t, "props": {}, "content": [], "children": []}
        for t in ("assemblyQuorum", "assemblyProxies", "responseTable")
    ]
    return {"schema": app_content.SCHEMA, "entry": {"blocks": entree}, "result": {"blocks": resultat}}


def _agenda_and_place(db: Session, org_id: int, kind: str) -> tuple[list[str], str]:
    """L'ordre du jour et le lieu de la dernière AG de cette sorte ; sinon
    l'ordre du jour de base."""
    from .app_files import AppFiles

    precedente = _previous(db, org_id, kind=kind)
    if precedente is not None:
        contenu = AppFiles.current_version(db, precedente).content
        points = [
            app_content._inline_text(b.get("content")).strip()
            for b in contenu.get("entry", {}).get("blocks", []) if b.get("type") == "numberedListItem"
        ]
        lieu = str((block_of(contenu).get("props") or {}).get("place") or "")
        if any(points):
            return [x for x in points if x], lieu
        return BASE_AGENDA[kind], lieu
    return BASE_AGENDA[kind], ""


def convene(
    docs: Documents, db: Session, member: Member, kind: str, starts_at: str, folder_id: int | None = None,
    new_folder: bool = False,
) -> dict:
    """« Convoquer l'AG » (spec §1.3) : la convocation en Brouillon, dans
    Réunions › AGO du … Si l'appli n'est pas sûre du dossier, elle rend les
    dossiers possibles (`folders`) sans rien créer : la question est posée."""
    from .service import DocError

    if kind not in KIND_WORDS:
        raise DocError(422, "Choisissez ordinaire ou extraordinaire.")
    debut = parse_start(starts_at)
    if debut is None:
        raise DocError(422, "Donnez la date et l'heure de l'assemblée.")
    if debut <= now_local():
        raise DocError(422, "Cette date est passée.")
    saison = _period_folder(docs, db, member.org_id)
    titre = assembly_title(kind, debut)
    if folder_id is None and not new_folder:
        _, possibles, choisi = find_folder(docs, db, member, kind)
        if choisi is None and possibles:
            return {"folders": possibles, "new_name": titre}
        folder_id = choisi
    if folder_id is None:
        reunions = next((n.id for n in _folders(db, saison.id) if _norm(n.name) in ("reunion", "reunions")), None)
        if reunions is None:
            reunions = docs.create_folder(db, member, "private", saison.id, MEETINGS_FOLDER)["id"]
        folder_id = docs.create_folder(db, member, "private", reunions, titre)["id"]
    else:
        dossier = docs._node(db, member, folder_id)
        if dossier.kind != KIND_FOLDER or dossier.space != "private":
            raise DocError(404, "Dossier introuvable")
    agenda, lieu = _agenda_and_place(db, member.org_id, kind)
    ecole = docs.mailer.org(db, member.org_id)[0] if docs.mailer is not None else ""
    contenu = convocation_content(kind, debut, lieu, agenda, ecole, member.display_name)
    cree = docs.apps.create(db, member, "private", folder_id, "question", f"Convocation {titre}", content=contenu)
    return {**cree, "folder_id": folder_id, "family": "question"}


# ----------------------------------------------------------------------
# Pour l'écran du bureau (routes)
# ----------------------------------------------------------------------


def _node_for(docs: Documents, db: Session, member: Member, node_id: int) -> tuple[DocNode, dict]:
    from .service import DocError

    node = docs.apps._app_node(db, member, node_id)
    docs._require(db, member, docs._locate(db, member, node), LEVEL_EDIT)
    version = docs.apps.current_version(db, node)
    if version is None or block_of(version.content) is None:
        raise DocError(409, "Ce fichier n'est pas une convocation.")
    return node, version.content


def overview(docs: Documents, db: Session, member: Member, node_id: int) -> dict:
    """Le décompte, et à qui envoyer par défaut (« Pour : N membres »)."""
    node, contenu = _node_for(docs, db, member, node_id)
    cibles = default_principals(docs, db, node)
    gens = docs.directory.recipients(db, node.org_id, [(p["type"], p["id"]) for p in cibles])
    return {
        "summary": summary(docs, db, node, contenu),
        "principals": cibles,
        "recipients": [{"person_id": g.person_id, "name": g.name, "email": g.email} for g in gens],
    }


def export(docs: Documents, db: Session, member: Member, node_id: int, what: str) -> tuple[bytes, str, str]:
    """(contenu, type, nom) : « summary.pdf », « summary.xlsx », « convocation.pdf »."""
    node, contenu = _node_for(docs, db, member, node_id)
    ecole = docs.mailer.org(db, node.org_id)[0] if docs.mailer is not None else ""
    titre = node.name.removeprefix("Convocation ")
    if what == "convocation.pdf":
        return convocation_pdf(contenu, node.name, ecole), "application/pdf", f"{node.name}.pdf"
    s = summary(docs, db, node, contenu)
    if what == "summary.xlsx":
        return summary_xlsx(s, titre), XLSX, f"Récapitulatif {titre}.xlsx"
    return summary_pdf(s, titre, ecole), "application/pdf", f"Récapitulatif {titre}.pdf"


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# ----------------------------------------------------------------------
# Le jour de l'assemblée : la feuille d'émargement (étape 2, §3.5 et §4)
# ----------------------------------------------------------------------


def sheet(docs: Documents, db: Session, node: DocNode, content: dict) -> dict:
    """Le décompte du jour. Présents = pointés sur la feuille. Un pouvoir
    compte si son mandataire est présent (ou s'il est en blanc) ; il est
    perdu sinon ; il ne compte plus si le mandant est venu (sa présence
    l'emporte)."""
    bloc = block_of(content)
    p = props(bloc)
    gens = convoked(db, node)
    pointes = {
        a.person_id: a for a in db.scalars(select(DocAttendance).where(DocAttendance.node_id == node.id))
    }
    hors = set(pointes) - set(gens)
    noms = {**gens, **(docs.directory.person_names(db, node.org_id, hors) if hors else {})}
    reponses = {r.person_id: r.values[bloc["id"]] for r in _answers(db, node, bloc["id"]) if r.person_id in gens}
    valides: dict = {}
    perdus: dict = {}
    for mandant, v in reponses.items():
        if v.get("answer") != "proxy" or mandant in pointes:
            continue
        qui = v.get("proxy_to")
        (valides if qui == "blank" or qui in pointes else perdus).setdefault(qui, []).append(mandant)
    represente = {m: qui for qui, ms in valides.items() for m in ms}
    lignes = []
    for pid, nom in sorted(noms.items(), key=lambda x: _norm(x[1])):
        qui = represente.get(pid)
        a = pointes.get(pid)
        lignes.append({
            "person_id": pid, "name": nom, "convoked": pid in gens,
            "present": a is not None, "source": a.source if a else None,
            "answer": reponses.get(pid, {}).get("answer", "none"),
            "represented_by": None if qui is None else "le bureau" if qui == "blank" else noms.get(qui, "?"),
            # Sa procuration, quand elle ne compte pas (lui présent, ou mandataire absent).
            "proxy_name": reponses.get(pid, {}).get("proxy_name") if qui is None else None,
            "holds": len(valides.get(pid, [])),
            "lost": [noms[m] for m in perdus.get(pid, [])],
        })
    portes = sum(len(m) for m in valides.values())
    voix = len(pointes) + portes
    seuil = {"quarter": 4, "third": 3, "half": 2}.get(p["quorum"])
    il_faut = math.ceil(len(gens) / seuil) if seuil and gens else None
    return {
        "convoked": len(gens),
        "present": len(pointes),
        "represented": portes,
        "absent": sum(1 for pid in gens if pid not in pointes and pid not in represente),
        "lost": sum(len(m) for m in perdus.values()),
        "blank": len(valides.get("blank", [])),
        "votes": voix,
        "quorum": {"rule": p["quorum"], "needed": il_faut, "votes": voix, "reached": voix >= il_faut} if il_faut else None,
        "rows": lignes,
    }


def attendance(docs: Documents, db: Session, member: Member, node_id: int) -> dict:
    node, contenu = _node_for(docs, db, member, node_id)
    return sheet(docs, db, node, contenu)


def mark(docs: Documents, db: Session, member: Member, node_id: int, person_id: int, present: bool, source: str = "hand") -> dict:
    """Pointer (ou dépointer) une personne. Un membre de l'école non convoqué
    peut être ajouté (« Ajouter une personne »)."""
    from .service import DocError

    node, contenu = _node_for(docs, db, member, node_id)
    if node.status != "official":
        raise DocError(409, "La feuille d'émargement s'ouvre quand la convocation est officielle.")
    ligne = db.scalar(select(DocAttendance).where(DocAttendance.node_id == node.id, DocAttendance.person_id == person_id))
    if present and ligne is None:
        # `recipients` ne rend que les personnes de cette école.
        if person_id not in convoked(db, node) and not docs.directory.recipients(db, node.org_id, [("member", str(person_id))]):
            raise DocError(404, "Membre introuvable")
        db.add(DocAttendance(
            org_id=node.org_id, node_id=node.id, person_id=person_id, marked_by=member.person_id,
            source=source if source in ("hand", "photo") else "hand",
        ))
        db.commit()
    elif not present and ligne is not None:
        db.delete(ligne)
        db.commit()
    return sheet(docs, db, node, contenu)


STATE_WORDS = {"present": "Présent", "represented": "Représenté", "absent": "Absent"}


def sheet_html(s: dict, title: str, org_name: str) -> str:
    q = s["quorum"]
    quorum = (
        f"Quorum : {q['votes']} voix présentes ou représentées sur {s['convoked']} ; il en faut {q['needed']} "
        f"({QUORUM_WORDS.get(q['rule'], '')} des membres). {'Atteint' if q['reached'] else 'Pas atteint'}."
        if q else f"Voix présentes ou représentées : {s['votes']} sur {s['convoked']}."
    )
    lignes = []
    for r in s["rows"]:
        if r["present"]:
            etat = "Présent" + ("" if r["convoked"] else " (non convoqué)")
            voix = 1 + r["holds"]
        elif r["represented_by"]:
            etat, voix = f"Représenté par {r['represented_by']}", ""
        elif r["proxy_name"]:
            etat, voix = f"Absent (pouvoir à {r['proxy_name']}, perdu)", ""
        else:
            etat, voix = "Absent", ""
        perdus = f"<br/><small>Pouvoir perdu : {escape(', '.join(r['lost']))}</small>" if r["lost"] else ""
        lignes.append(f"<tr><td>{escape(r['name'])}</td><td>{escape(etat)}{perdus}</td><td>{voix}</td></tr>")
    blanc = f"<p>Pouvoirs en blanc, portés par le bureau : {s['blank']}.</p>" if s["blank"] else ""
    return (
        f"<p class='org'>{escape(org_name.upper())}</p><h1>Feuille d'émargement</h1>"
        f"<p class='sub'>{escape(title)} · arrêtée le {now_local():%d/%m/%Y à %H h %M}</p>"
        "<table class='kpi'><tr>"
        + "".join(f"<td><b>{n}</b><br/>{escape(t)}</td>" for n, t in (
            (s["convoked"], "membres convoqués"), (s["present"], "présents"), (s["represented"], "représentés"), (s["lost"], "pouvoirs perdus"),
        ))
        + f"</tr></table><p class='q'>{escape(quorum)}</p>{blanc}"
        "<table class='t'><tr><th>MEMBRE</th><th>PRÉSENCE</th><th>VOIX</th></tr>" + "".join(lignes) + "</table>"
        "<p class='foot'>Présents pointés par le bureau ; procurations signées en ligne, rangées dans le dossier « Pouvoirs ». "
        "Un mandant présent reprend sa voix ; un pouvoir dont le mandataire est absent est perdu.</p>"
    )


def store_sheet(docs: Documents, db: Session, member: Member, node_id: int) -> dict:
    """La feuille en PDF, rangée à côté de la convocation (nouvelle version
    si elle y est déjà)."""
    node, contenu = _node_for(docs, db, member, node_id)
    titre = node.name.removeprefix("Convocation ")
    ecole = docs.mailer.org(db, node.org_id)[0] if docs.mailer is not None else ""
    pdf = _pdf(sheet_html(sheet(docs, db, node, contenu), titre, ecole))
    return _store(docs, db, member, node, f"Feuille d'émargement {titre}.pdf", pdf)


def store(docs: Documents, db: Session, member: Member, node_id: int, what: str) -> dict:
    """Le récapitulatif (« summary ») ou la convocation (« convocation »)
    en PDF, rangé à côté de la convocation (l'assistant ne télécharge pas)."""
    pdf, _, nom = export(docs, db, member, node_id, "convocation.pdf" if what == "convocation" else "summary.pdf")
    return _store(docs, db, member, docs.apps._app_node(db, member, node_id), nom, pdf)


def stored_name(node: DocNode, what: str) -> str:
    return f"{node.name}.pdf" if what == "convocation" else f"Récapitulatif {node.name.removeprefix('Convocation ')}.pdf"


def _store(docs: Documents, db: Session, member: Member, node: DocNode, nom: str, pdf: bytes) -> dict:
    deja = db.scalar(select(DocNode).where(
        DocNode.parent_id == node.parent_id, DocNode.name == nom, DocNode.kind == "file", DocNode.deleted_at.is_(None),
    ))
    if deja is not None:
        docs.new_version(db, member, deja.id, nom, io.BytesIO(pdf))
        return {"id": deja.id, "name": nom}
    cree = docs.upload(db, member, node.space, node.parent_id, nom, io.BytesIO(pdf))
    return {"id": cree["id"], "name": cree.get("name", nom)}


def _names(rows: list[dict]) -> str:
    return ", ".join(r["name"] for r in rows)


def status_text(docs: Documents, db: Session, node: DocNode, content: dict) -> str:
    """Où en est l'AG, en phrases, pour l'assistant : les chiffres viennent
    d'ici (summary, sheet), l'assistant ne compte rien."""
    s = summary(docs, db, node, content)
    if s is None:
        return ""
    if not s["convoked"]:
        return "Convocation pas encore envoyée."
    pluriel = lambda n, mot: f"{n} {mot}{'s' if n > 1 else ''}"
    par = {a: [r for r in s["rows"] if r["answer"] == a] for a in ANSWER_WORDS}
    lignes = [(
        f"{pluriel(s['convoked'], 'convoqué')}, {s['answered']} {'ont' if s['answered'] > 1 else 'a'} répondu : "
        f"{s['attend']} {'viennent' if s['attend'] > 1 else 'vient'}, {pluriel(s['proxy'], 'procuration')}, "
        f"{s['absent']} {'ne viennent pas' if s['absent'] > 1 else 'ne vient pas'}."
    )]
    for cle, mot in (("attend", "Viennent"), ("absent", "Ne viennent pas"), ("none", "Sans réponse")):
        if par[cle]:
            lignes.append(f"{mot} ({len(par[cle])}) : {_names(par[cle])}.")
    for h in s["holders"]:
        lignes.append(f"Pouvoirs : {h['name']} porte {h['count']} ({', '.join(h['from'])}){_holder_note(h)}.")
    q = s["quorum"]
    lignes.append(
        f"Voix prévues : {s['votes']}"
        + (f" ; quorum ({QUORUM_WORDS[q['rule']]} des convoqués) : il en faut {q['needed']}, "
           f"{'atteint' if q['reached'] else 'pas atteint'}." if q else " ; pas de quorum demandé.")
        + (f" {s['lost']} pouvoir(s) perdu(s)." if s["lost"] else "")
    )
    if db.scalar(select(DocAttendance.id).where(DocAttendance.node_id == node.id).limit(1)) is not None:
        t = sheet(docs, db, node, content)
        lignes.append(
            f"Le jour de l'AG (feuille d'émargement) : {t['present']} présents, {t['represented']} représentés, "
            f"{t['votes']} voix" + (f", quorum {'atteint' if t['quorum']['reached'] else 'pas atteint'}" if t.get("quorum") else "") + "."
        )
    lignes.append("Les pouvoirs signés sont dans le dossier « Pouvoirs » à côté de la convocation.")
    return "\n".join(lignes)
