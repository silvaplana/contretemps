"""Procès-verbal d'assemblée générale (spec proces-verbal-ag.md, étape 2).
Posé sur le fichier de base, comme la convocation : le PV est un fichier
Questionner dont la seule question est un bloc Signature marqué
`minutesOf` (l'id de la convocation). Ce module ajoute :

- les assemblées passées qui attendent leur PV, et le PV proposé (`draft`) :
  le texte est écrit par le code, chiffres compris (présents, représentés,
  quorum, bilan officiel), sur le plan du PV de l'an dernier ;
- l'envoi pour signature aux membres du bureau choisis (envois `sign`) ;
- à chaque signature, le PDF refait et rangé à côté de la convocation, un
  email à l'adresse de contact avec ce PDF, et le passage en Officiel
  quand tout le monde a signé.

Tous les chiffres sont calculés ici, jamais par l'assistant.
"""

from __future__ import annotations

import io
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime
from html import escape
from typing import TYPE_CHECKING

import pymupdf
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import app_content, assembly
from .models import (
    KIND_APP,
    LEVEL_EDIT,
    LEVEL_MANAGE,
    DocNode,
    DocResponse,
    DocSend,
    utcnow,
)
from .ports import Member

if TYPE_CHECKING:
    from .service import Documents

logger = logging.getLogger(__name__)

PROP = "minutesOf"
SIGN = "sign"
FUNCTION_WORDS = {
    "president": "président·e", "vice_president": "vice-président·e", "secretary": "secrétaire", "treasurer": "trésorier·e",
}
TODO = "À compléter : "
# Styles de BlockNote : en bleu ce que l'appli a compté, en jaune ce qu'il
# faut compléter ou vérifier (spec §1, étape 4).
APP = {"textColor": "blue"}
CHECK = {"backgroundColor": "yellow"}


# ----------------------------------------------------------------------
# Le fichier
# ----------------------------------------------------------------------


def block_of(content: dict) -> dict | None:
    """Le bloc Signature d'un PV (celui qui porte `minutesOf`)."""
    for b in app_content._walk(content.get("entry", {}).get("blocks", [])):
        source = (b.get("props") or {}).get(PROP)
        if b.get("type") == "signature" and isinstance(source, int) and not isinstance(source, bool) and source > 0:
            return b
    return None


def source_of(content: dict) -> int | None:
    bloc = block_of(content)
    return bloc["props"][PROP] if bloc else None


def _versions(db: Session, org_id: int):
    from .app_files import AppFiles

    for n in db.scalars(
        select(DocNode).where(DocNode.org_id == org_id, DocNode.kind == KIND_APP, DocNode.deleted_at.is_(None))
        .order_by(DocNode.created_at.desc(), DocNode.id.desc())
    ):
        version = AppFiles.current_version(db, n)
        if version is not None:
            yield n, version.content


def _title(convocation: DocNode) -> str:
    """« AGO du 21 novembre 2026 »."""
    return convocation.name.removeprefix("Convocation ")


def _node_for(docs: Documents, db: Session, member: Member, node_id: int, level: str = LEVEL_EDIT) -> tuple[DocNode, dict]:
    from .service import DocError

    node = docs.apps._app_node(db, member, node_id)
    docs._require(db, member, docs._locate(db, member, node), level)
    version = docs.apps.current_version(db, node)
    if version is None or block_of(version.content) is None:
        raise DocError(409, "Ce fichier n'est pas un procès-verbal.")
    return node, version.content


# ----------------------------------------------------------------------
# Quelle assemblée ? (spec §1, « Où on le lance »)
# ----------------------------------------------------------------------


def pending(docs: Documents, db: Session, member: Member, folder_id: int | None = None) -> list[dict]:
    """Les assemblées passées (convocation Officielle envoyée, date passée)
    sans PV, que la personne peut modifier ; la plus récente d'abord."""
    from .service import DocError

    fichiers = list(_versions(db, member.org_id))
    faits = {source_of(c) for _, c in fichiers} - {None}
    maintenant = assembly.now_local()
    trouvees = []
    for n, contenu in fichiers:
        bloc = assembly.block_of(contenu)
        if bloc is None or n.status != "official" or n.id in faits or (folder_id is not None and n.parent_id != folder_id):
            continue
        debut = assembly.props(bloc)["start"]
        if debut is None or debut > maintenant or not assembly.convoked(db, n):
            continue
        try:
            docs._require(db, member, docs._locate(db, member, n), LEVEL_EDIT)
        except DocError:
            continue
        trouvees.append({"id": n.id, "name": n.name, "title": _title(n), "folder_id": n.parent_id, "starts_at": debut.isoformat(timespec="minutes")})
    trouvees.sort(key=lambda x: x["starts_at"], reverse=True)
    return trouvees


# ----------------------------------------------------------------------
# Le texte proposé (spec §2)
# ----------------------------------------------------------------------


def _run(text: str, styles: dict | None = None) -> dict:
    return {"type": "text", "text": text, "styles": dict(styles or {})}


def _block(kind: str, runs: list[dict], **props) -> dict:
    return {"id": uuid.uuid4().hex, "type": kind, "props": props, "content": runs, "children": []}


def _p(*runs) -> dict:
    """Un paragraphe ; chaque morceau est un texte, ou (texte, styles)."""
    return _block("paragraph", [_run(*r) if isinstance(r, tuple) else _run(r) for r in runs])


def _flag_numbers(runs: list[dict]) -> list[dict]:
    """Texte repris de l'an dernier : chaque nombre surligné « à vérifier »."""
    sortie = []
    for r in runs:
        if not isinstance(r, dict) or r.get("type") != "text":
            sortie.append(r)
            continue
        for morceau in re.split(r"(\d[\d  .,]*\d|\d)", r.get("text") or ""):
            if morceau:
                styles = {**(r.get("styles") or {}), **CHECK} if morceau[0].isdigit() else dict(r.get("styles") or {})
                sortie.append(_run(morceau, styles))
    return sortie


def _plural(n: int, one: str, many: str) -> str:
    return f"{n} {one if n == 1 else many}"


def _euros(x: float | None) -> str:
    if x is None:
        return "?"
    texte = f"{abs(x):,.2f}".replace(",", " ").replace(".", ",").removesuffix(",00")
    return ("−" if x < 0 else "") + texte + " €"


def _point_key(text: str) -> str:
    return assembly._norm(re.sub(r"^\s*\d+\s*[.)-]\s*", "", text or ""))


def _previous_sections(db: Session, org_id: int, kind: str) -> dict[str, list[dict]]:
    """Le PV de la dernière assemblée de cette sorte : ses paragraphes, rangés
    sous le titre du point de l'ordre du jour."""
    from .app_files import AppFiles

    for n, contenu in _versions(db, org_id):
        source = source_of(contenu)
        convocation = db.get(DocNode, source) if source else None
        if convocation is None or convocation.org_id != org_id:
            continue
        version = AppFiles.current_version(db, convocation)
        bloc = assembly.block_of(version.content) if version else None
        if bloc is None or assembly.props(bloc)["kind"] != kind:
            continue
        sections: dict[str, list[dict]] = {}
        courante = None
        for b in contenu.get("entry", {}).get("blocks", []):
            if b.get("type") == "heading":
                courante = _point_key(app_content._inline_text(b.get("content")))
                sections[courante] = []
            elif courante is not None and b.get("type") in ("paragraph", "bulletListItem", "numberedListItem"):
                texte = app_content._inline_text(b.get("content")).strip()
                if texte and not texte.startswith(TODO):
                    sections[courante].append(b)
        return {k: v for k, v in sections.items() if v}
    return {}


def _agenda(convocation_content: dict) -> list[str]:
    return [
        app_content._inline_text(b.get("content")).strip()
        for b in convocation_content.get("entry", {}).get("blocks", [])
        if b.get("type") == "numberedListItem" and app_content._inline_text(b.get("content")).strip()
    ]


def _sent_on(db: Session, convocation: DocNode) -> datetime | None:
    parti = db.scalar(select(func.min(DocSend.sent_at)).where(
        DocSend.node_id == convocation.id, DocSend.test.is_(False), DocSend.channel == "email",
    ))
    return parti.replace(tzinfo=UTC).astimezone(assembly.TZ).replace(tzinfo=None) if parti else None


def _people(board, function: str) -> str:
    return ", ".join(b.name for b in board if function in b.functions)


def minutes_content(
    org_name: str, convocation: DocNode, convocation_content: dict, s: dict, sent_on: datetime | None,
    board: list, report: dict | None, previous: dict[str, list[dict]],
) -> dict:
    """Le PV proposé : le gabarit du §2, rempli par le code."""
    p = assembly.props(assembly.block_of(convocation_content))
    mot = assembly.KIND_WORDS[p["kind"]]
    lieu = str((assembly.block_of(convocation_content).get("props") or {}).get("place") or "").strip()
    debut = p["start"]
    blocs = [
        _block("heading", [_run(f"Procès-verbal de l'assemblée générale {mot}")], level=1),
        _p("Association : ", (org_name, APP)),
        _p(
            f"L'assemblée générale {mot} s'est réunie le ", (assembly.when_text(debut), APP), ", ",
            *([(lieu, APP)] if lieu else [(TODO + "le lieu", CHECK)]), ".",
        ),
        _p(
            "Les membres ont été convoqués par email",
            *([" le ", (assembly.day_text(sent_on), APP)] if sent_on else []),
            " (", (_plural(s["convoked"], "membre convoqué", "membres convoqués"), APP), ").",
        ),
    ]
    presidence, secretaire = _people(board, "president"), _people(board, "secretary")
    blocs.append(_p("Présidence de séance : ", (presidence, APP) if presidence else (TODO + "qui préside", CHECK), "."))
    blocs.append(_p("Secrétaire de séance : ", (secretaire, APP) if secretaire else (TODO + "qui tient le procès-verbal", CHECK), "."))

    blocs.append(_block("heading", [_run("Présents et représentés")], level=2))
    blocs.append(_p(
        (_plural(s["present"], "membre présent", "membres présents"), APP), " et ",
        (_plural(s["represented"], "membre représenté", "membres représentés"), APP), ", soit ",
        (_plural(s["votes"], "voix", "voix"), APP), " sur ", (str(s["convoked"]), APP), " membres convoqués.",
    ))
    if s["lost"]:
        blocs.append(_p(
            (_plural(s["lost"], "pouvoir n'a pas été pris", "pouvoirs n'ont pas été pris"), APP),
            " en compte : le représentant était absent.",
        ))
    q = s["quorum"]
    if q:
        seuil = (f"Le quorum, fixé à {assembly.QUORUM_WORDS.get(q['rule'], '')} des membres, soit ", (_plural(q["needed"], "voix", "voix"), APP))
        if q["reached"]:
            blocs.append(_p(*seuil, ", est atteint : l'assemblée peut valablement délibérer."))
        else:
            blocs.append(_p(*seuil, ", n'est pas atteint. ", (TODO + "la suite donnée (nouvelle assemblée…)", CHECK)))
    blocs.append(_p("La liste des présents et les pouvoirs sont joints en annexe."))

    points = _agenda(convocation_content)
    blocs.append(_block("heading", [_run("Ordre du jour")], level=2))
    blocs += [_block("numberedListItem", [_run(x)]) for x in points]
    for i, point in enumerate(points, start=1):
        blocs.append(_block("heading", [_run(f"{i}. {point}")], level=2))
        if report and re.search(r"financ|comptes", assembly._norm(point)):
            blocs.append(_p(
                "Le bilan de la saison ", (str(report["season"]), APP), " présente ", (_euros(report["income"]), APP),
                " de recettes et ", (_euros(report["expense"]), APP), " de dépenses, soit un résultat de ",
                (_euros(report["result"]), APP), ".",
            ))
        repris = previous.get(_point_key(point))
        if repris:
            blocs.append(_p((TODO + "texte repris du procès-verbal de l'an dernier, à adapter", CHECK)))
            blocs += [_block(b["type"], _flag_numbers(b.get("content") or [])) for b in repris]
        else:
            blocs.append(_p((TODO + "ce qui a été dit et le résultat du vote", CHECK)))
    blocs.append(_block("heading", [_run("Clôture")], level=2))
    blocs.append(_p("L'ordre du jour étant épuisé, la séance est levée à ", (TODO + "l'heure", CHECK), "."))
    blocs.append(_block("signature", [], label="Signature", required=True, **{PROP: convocation.id}))
    return {"schema": app_content.SCHEMA, "entry": {"blocks": blocs}, "result": {"blocks": []}}


def draft(docs: Documents, db: Session, member: Member, convocation_id: int) -> dict:
    """« Proposer le procès-verbal » : le PV en Brouillon, à côté de la
    convocation."""
    from .service import DocError

    convocation, contenu = assembly._node_for(docs, db, member, convocation_id)
    debut = assembly.props(assembly.block_of(contenu))["start"]
    if convocation.status != "official" or not assembly.convoked(db, convocation):
        raise DocError(409, "Cette convocation n'a pas été envoyée.")
    if debut is None or debut > assembly.now_local():
        raise DocError(409, "L'assemblée n'a pas encore eu lieu.")
    deja = next((n for n, c in _versions(db, member.org_id) if source_of(c) == convocation.id), None)
    if deja is not None:
        raise DocError(409, f"Le procès-verbal existe déjà : « {deja.name} ».")
    s = assembly.sheet(docs, db, convocation, contenu)
    kind = assembly.props(assembly.block_of(contenu))["kind"]
    ecole = docs.mailer.org(db, member.org_id)[0] if docs.mailer is not None else ""
    lien = docs.association
    contenu_pv = minutes_content(
        ecole, convocation, contenu, s, _sent_on(db, convocation),
        lien.board(db, member.org_id) if lien else [],
        lien.approved_report(db, member.org_id) if lien else None,
        _previous_sections(db, member.org_id, kind),
    )
    cree = docs.apps.create(
        db, member, convocation.space, convocation.parent_id, "question", f"PV de l'{_title(convocation)}", content=contenu_pv,
    )
    return {**cree, "folder_id": convocation.parent_id, "family": "question"}


# ----------------------------------------------------------------------
# Les signatures (spec §1, étapes 5 à 8)
# ----------------------------------------------------------------------


def signers(db: Session, node: DocNode) -> list[DocSend]:
    return list(db.scalars(select(DocSend).where(DocSend.node_id == node.id, DocSend.channel == SIGN).order_by(DocSend.name)))


def _labels(functions) -> str:
    return ", ".join(FUNCTION_WORDS[f] for f in functions if f in FUNCTION_WORDS)


def _board(docs: Documents, db: Session, org_id: int) -> dict[int, object]:
    return {b.person_id: b for b in docs.association.board(db, org_id)} if docs.association else {}


def status(docs: Documents, db: Session, member: Member, node_id: int) -> dict:
    """Qui doit signer, qui a signé ; le bureau pour « Qui doit signer ? »."""
    node, contenu = _node_for(docs, db, member, node_id)
    bureau = _board(docs, db, node.org_id)
    convocation = db.get(DocNode, source_of(contenu))
    lignes = [
        {
            "person_id": s.person_id, "name": s.name, "email": s.email,
            "functions": _labels(bureau[s.person_id].functions) if s.person_id in bureau else "",
            "signed_at": s.answered_at.isoformat() if s.answered_at else None,
            "send_status": s.status,
            # « Signer moi-même » : son propre lien seulement.
            "token": s.token if s.person_id == member.person_id else None,
        }
        for s in signers(db, node)
    ]
    return {
        "status": node.status,
        "signers": lignes,
        "signed": sum(1 for x in lignes if x["signed_at"]),
        "board": [
            {"person_id": b.person_id, "name": b.name, "functions": _labels(b.functions),
             "default": "president" in b.functions or "secretary" in b.functions}
            for b in bureau.values()
        ],
        "members": len(assembly.convoked(db, convocation)) if convocation is not None and convocation.deleted_at is None else 0,
        "convocation_id": convocation.id if convocation is not None else None,
        "available": docs.mailer is not None and docs.mailer.available,
    }


def status_text(docs: Documents, db: Session, node: DocNode) -> str:
    """Pour l'assistant (lire_fichier) : où en sont les signatures."""
    bureau = _board(docs, db, node.org_id)
    gens = signers(db, node)
    if not gens:
        return "Pas encore envoyé pour signature."
    lignes = [
        f"- {s.name}{f' ({_labels(bureau[s.person_id].functions)})' if s.person_id in bureau else ''} : "
        + (f"a signé le {s.answered_at:%d/%m/%Y}" if s.answered_at else "pas encore signé")
        for s in gens
    ]
    signe = sum(1 for s in gens if s.answered_at)
    return f"{signe} signature{'s' if signe > 1 else ''} sur {len(gens)} :\n" + "\n".join(lignes)


def _mail(paragraphs: list[str], org_name: str, greeting: str | None = None) -> tuple[str, str]:
    if greeting:
        return assembly._letter(greeting, paragraphs, org_name)
    lignes = [*paragraphs, f"Message envoyé par {org_name}."]
    html = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;color:#222;max-width:520px">'
        + "".join(f'<p style="margin:0 0 16px;white-space:pre-line">{escape(x)}</p>' for x in lignes)
        + "</div>"
    )
    return "\n\n".join(lignes) + "\n", html


def send_for_signature(docs: Documents, db: Session, member: Member, node_id: int, person_ids: list[int]) -> tuple[dict, list[dict]]:
    """« Envoyer pour signature » (ou « Relancer » une personne) : chacun
    reçoit son lien personnel ; le même lien resert à chaque envoi."""
    from .service import DocError

    node, _ = _node_for(docs, db, member, node_id, LEVEL_MANAGE)
    if node.status != "validated":
        raise DocError(409, "Validez d'abord le procès-verbal : le texte est figé avant les signatures.")
    if docs.mailer is None or not docs.mailer.available:
        raise DocError(409, "L'envoi d'emails n'est pas configuré sur ce serveur.")
    ids = list(dict.fromkeys(person_ids))
    if not ids:
        raise DocError(422, "Choisissez qui doit signer.")
    gens = docs.directory.recipients(db, node.org_id, [("member", str(i)) for i in ids])
    if len(gens) != len(ids):
        raise DocError(404, "Membre introuvable")
    sans = [g.name for g in gens if not g.email]
    if sans:
        raise DocError(409, f"Pas d'adresse email pour : {', '.join(sans)}.")
    deja = {s.person_id: s for s in signers(db, node)}
    signe = [deja[g.person_id].name for g in gens if g.person_id in deja and deja[g.person_id].answered_at]
    if signe:
        raise DocError(409, f"A déjà signé : {', '.join(signe)}.")
    envois = []
    for g in gens:
        s = deja.get(g.person_id)
        if s is None:
            s = DocSend(org_id=node.org_id, node_id=node.id, token=secrets.token_urlsafe(24), person_id=g.person_id, channel=SIGN, test=False)
            db.add(s)
        s.name, s.email, s.status, s.error, s.sent_by = g.name, g.email, "pending", None, member.person_id
        envois.append(s)
    docs._log(db, member, node, "sent", {"count": len(envois), "signature": True})
    db.commit()
    ecole, adresse = docs.mailer.org(db, node.org_id)
    moi = docs.directory.recipients(db, member.org_id, [("member", str(member.person_id))])
    reply_to = moi[0].email if moi and moi[0].email else None
    titre = node.name.removeprefix("PV de l'")
    jobs = []
    for s in envois:
        texte, html = _mail([
            (
                f"Le procès-verbal de l'{titre} est prêt. Merci de le relire, puis de le signer avec le doigt, avec votre "
                f"lien personnel :\n{adresse}/r/{s.token}"
            ),
            f"Si vous n'êtes pas d'accord avec le texte, écrivez à {member.display_name} avant de signer"
            + (", en répondant à ce mail." if reply_to else "."),
            "Ce lien vous est personnel : ne le transférez à personne.",
        ], ecole, greeting=s.name)
        jobs.append({"send_id": s.id, "to": s.email, "subject": f"À signer : procès-verbal de l'{titre}", "text": texte,
                     "html": html, "sender_name": ecole, "reply_to": reply_to})
    return {"sent": len(envois)}, jobs


def signer_sentence(docs: Documents, db: Session, node: DocNode, s: DocSend) -> str:
    fonctions = _board(docs, db, node.org_id).get(s.person_id)
    qui = f"{s.name}, {_labels(fonctions.functions)}" if fonctions is not None and fonctions.functions else s.name
    return f"Je soussigné(e) {qui}, certifie ce procès-verbal exact."


def link_content(docs: Documents, db: Session, node: DocNode, content: dict, s: DocSend) -> dict:
    """Ce que montre le lien personnel : au signataire, la phrase à signer à la
    place du titre du bloc ; aux autres membres, le texte sans signature."""
    bloc = block_of(content)
    entree = content.get("entry", {}).get("blocks", [])
    if s.channel == SIGN:
        blocs = [{**b, "props": {**b["props"], "label": signer_sentence(docs, db, node, s)}} if b is bloc else b for b in entree]
    else:
        blocs = [b for b in entree if b is not bloc]
    return {"schema": content.get("schema", 1), "entry": {"blocks": blocs}}


def reset_signatures(db: Session, node: DocNode) -> None:
    """Le PV repasse en Brouillon : les signatures déjà faites s'effacent
    (le texte va changer) ; les liens restent les mêmes."""
    gens = signers(db, node)
    ids = [s.response_id for s in gens if s.response_id]
    if ids:
        db.query(DocResponse).filter(DocResponse.id.in_(ids)).delete(synchronize_session=False)
    for s in gens:
        s.response_id, s.answered_at = None, None


def after_signature(docs: Documents, db: Session, node: DocNode, response: DocResponse, name: str) -> None:
    """Une signature arrive : PDF refait et rangé, Officiel si tout le monde a
    signé, email à l'adresse de contact avec le PDF. Un échec ici ne perd
    jamais la signature."""
    from .app_files import AppFiles

    try:
        contenu = AppFiles.current_version(db, node).content
        gens = signers(db, node)
        signe = sum(1 for s in gens if s.answered_at)
        tous = signe == len(gens)
        if tous:
            node.status = "official"
            node.updated_at = utcnow()
            docs._log(db, assembly._system_member(node, None), node, "status", {"from": "validated", "to": "official"})
            db.commit()
        pdf = minutes_pdf(docs, db, node, contenu)
        assembly._store(docs, db, assembly._system_member(node, response.person_id), node, f"{node.name}.pdf", pdf)
    except Exception:  # la signature reste dans les réponses
        logger.exception("PV : PDF non refait après une signature (fichier %s)", node.id)
        db.rollback()
        return
    adresse = docs.association.contact_email(db, node.org_id) if docs.association else None
    if not adresse or docs.mailer is None or not docs.mailer.available:
        return
    ecole = docs.mailer.org(db, node.org_id)[0]
    titre = node.name.removeprefix("PV de l'")
    fonctions = _board(docs, db, node.org_id).get(response.person_id)
    qui = f"{name} ({_labels(fonctions.functions)})" if fonctions is not None and fonctions.functions else name
    texte, html = _mail([
        f"{qui} a signé le procès-verbal de l'{titre} ({signe} signature{'s' if signe > 1 else ''} sur {len(gens)}).",
        "Toutes les signatures sont là : le procès-verbal est officiel." if tous
        else "Les autres signatures sont attendues.",
        "Le PDF à jour est joint à ce mail ; il est aussi rangé dans le dossier de l'assemblée.",
    ], ecole)
    try:
        docs.mailer.send(adresse, f"{name} a signé le procès-verbal de l'{titre}", texte, html, ecole, None, [(f"{node.name}.pdf", pdf)])
    except Exception as erreur:  # noqa: BLE001 (la signature est enregistrée)
        logger.warning("PV : email de signature non envoyé à %s : %s", adresse, erreur)


# ----------------------------------------------------------------------
# Le PDF (spec §1, étapes 7 et 8)
# ----------------------------------------------------------------------


def _html_blocks(blocks: list[dict], skip: dict | None) -> str:
    parts, numero = [], 0
    for b in app_content._walk(blocks):
        genre = b.get("type")
        texte = escape(app_content._inline_text(b.get("content")).strip())
        numero = numero + 1 if genre == "numberedListItem" else 0
        if b is skip or genre in app_content.QUESTION_TYPES or not texte:
            continue
        if genre == "heading":
            niveau = min(max(int((b.get("props") or {}).get("level") or 1), 1), 3)
            parts.append(f"<h{niveau}>{texte}</h{niveau}>")
        elif genre == "numberedListItem":
            parts.append(f"<p>{numero}. {texte}</p>")
        elif genre == "bulletListItem":
            parts.append(f"<p>• {texte}</p>")
        else:
            parts.append(f"<p>{texte}</p>")
    return "".join(parts)


def _render(html: str, archive=None) -> bytes:
    buffer = io.BytesIO()
    page = pymupdf.paper_rect("a4")
    story = pymupdf.Story(html=html, user_css=assembly._CSS, archive=archive)
    writer = pymupdf.DocumentWriter(buffer)
    more = True
    while more:
        device = writer.begin_page(page)
        more, _ = story.place(page + (48, 48, -48, -48))
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()


def minutes_pdf(docs: Documents, db: Session, node: DocNode, content: dict) -> bytes:
    """Le texte, une zone par signataire (remplie à mesure), puis en annexe
    la feuille d'émargement (présents, représentés, pouvoirs)."""
    import base64

    bloc = block_of(content)
    ecole = docs.mailer.org(db, node.org_id)[0] if docs.mailer is not None else ""
    bureau = _board(docs, db, node.org_id)
    archive = pymupdf.Archive()
    cases = []
    for i, s in enumerate(signers(db, node)):
        reponse = db.get(DocResponse, s.response_id) if s.response_id else None
        image = (reponse.values or {}).get(bloc["id"]) if reponse is not None else None
        fonction = _labels(bureau[s.person_id].functions) if s.person_id in bureau else ""
        if image and s.answered_at:
            archive.add(base64.b64decode(image.split(",", 1)[1]), f"s{i}.png")
            quand = s.answered_at.replace(tzinfo=UTC).astimezone(assembly.TZ)
            signe = f"<img src='s{i}.png' width='160' height='60'/><br/><span class='small'>Signé en ligne le {quand:%d/%m/%Y à %H h %M}</span>"
        else:
            signe = "<p class='small'>En attente de signature</p>"
        cases.append(f"<td><b>{escape(s.name)}</b>{f'<br/>{escape(fonction)}' if fonction else ''}<br/>{signe}</td>")
    lignes = "".join(f"<tr>{''.join(cases[i:i + 2])}</tr>" for i in range(0, len(cases), 2))
    html = (
        f"<p class='org'>{escape(ecole.upper())}</p>"
        + _html_blocks(content.get("entry", {}).get("blocks", []), bloc)
        + (f"<h2>Signatures</h2><table class='t'>{lignes}</table>" if lignes else "")
    )
    pdf = pymupdf.open(stream=_render(html, archive), filetype="pdf")
    convocation = db.get(DocNode, bloc["props"][PROP])
    version = docs.apps.current_version(db, convocation) if convocation is not None else None
    if version is not None and assembly.block_of(version.content) is not None:
        feuille = assembly.sheet(docs, db, convocation, version.content)
        annexe = assembly.sheet_html(feuille, _title(convocation), ecole).replace(
            "<h1>Feuille d'émargement</h1>", "<h1>Annexe : liste des présents et pouvoirs</h1>", 1,
        )
        pdf.insert_pdf(pymupdf.open(stream=_render(annexe), filetype="pdf"))
    sortie = pdf.tobytes(garbage=3, deflate=True)
    pdf.close()
    return sortie


def export(docs: Documents, db: Session, member: Member, node_id: int) -> tuple[bytes, str]:
    """« Télécharger le PDF » : (contenu, nom)."""
    node, contenu = _node_for(docs, db, member, node_id)
    return minutes_pdf(docs, db, node, contenu), f"{node.name}.pdf"
