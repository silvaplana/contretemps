"""Signer un document (spec signature-documents.md), étapes 1 à 3.

Posé sur le fichier de base, comme la convocation et le PV : un fichier
Questionner dont la seule question est un bloc `signDocument` (le document à
signer, où signer, la mention, le message aux signataires). Ce module
ajoute :

- la création du fichier (tuile du +, ou « Faire signer… » sur un PDF ou un
  Word) et le choix du document ; un Word devient des blocs de l'appli, que
  l'on corrige dans l'Aperçu (§2.2) ;
- les pages du document, en images, pour l'Aperçu ;
- **Valider fige le document** (§1, obligation 1) : le PDF à signer est
  rangé dans le stockage par son empreinte SHA-256 et l'événement
  `validated` est écrit au journal de preuves (`doc_sign_events`). Repasser
  en Brouillon écrit `reset` et annule les signatures déjà faites.
- « Faire signer à qui ? » (§2.3) : un lien personnel par signataire
  (`doc_sends`, canal `sign`, comme le PV), qui expire 14 jours après le
  dernier envoi ; Relancer.
- Le lien du signataire (§2.4), sans compte : ouvert, lu jusqu'en bas,
  consentement et signature (une réponse `doc_responses`), ou refus avec un
  motif. Chaque pas est écrit au journal avec l'adresse IP et l'appareil.
- « Produire le document signé » (§2.5, §3) quand tout le monde a signé :
  le PDF figé (empreinte vérifiée), les signatures et les paraphes, la page
  Certificat de preuves ; rangé à côté de l'original, envoyé par mail, et
  le fichier passe Officiel.

Le journal ne se modifie jamais : on n'y fait que des INSERT.
"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from html import escape
from html.parser import HTMLParser
from typing import TYPE_CHECKING

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import app_content, assembly, minutes, preview
from .models import (
    KIND_FILE,
    LEVEL_EDIT,
    LEVEL_MANAGE,
    LEVEL_VIEW,
    DocNode,
    DocResponse,
    DocSend,
    DocSignEvent,
    DocVersion,
    StoredFile,
    utcnow,
)
from .ports import Member

if TYPE_CHECKING:
    from .service import Documents

logger = logging.getLogger(__name__)

BLOCK = "signDocument"
DEFAULT_NAME = "Faire signer un document"
DEFAULT_MENTION = "Lu et approuvé"
PAGE_DPI = 96


def _error(status: int, message: str):
    from .service import DocError

    return DocError(status, message)


# ----------------------------------------------------------------------
# Le fichier
# ----------------------------------------------------------------------


def block_of(content: dict) -> dict | None:
    return next((b for b in app_content._walk(content.get("entry", {}).get("blocks", [])) if b.get("type") == BLOCK), None)


def props(bloc: dict) -> dict:
    p = bloc.get("props") or {}
    return {
        "source": p.get("source") or 0,
        "mode": p.get("mode") or "end",
        "mention": p.get("mention") or "",
        "message": p.get("message") or "",
    }


def kind_of(name: str) -> str | None:
    """« pdf », « word » (texte à corriger dans l'Aperçu), sinon None."""
    ext = preview.extension(name)
    return "pdf" if ext == ".pdf" else "word" if ext in preview.TEXT_DOCUMENTS else None


def _new_block() -> dict:
    return {
        "id": uuid.uuid4().hex, "type": BLOCK,
        "props": {"source": 0, "mode": "end", "mention": DEFAULT_MENTION, "message": ""},
        "content": [], "children": [],
    }


def _node_for(docs: Documents, db: Session, member: Member, node_id: int, level: str = LEVEL_EDIT) -> tuple[DocNode, dict, dict]:
    node = docs.apps._app_node(db, member, node_id)
    docs._require(db, member, docs._locate(db, member, node), level)
    version = docs.apps.current_version(db, node)
    bloc = block_of(version.content) if version is not None else None
    if bloc is None:
        raise _error(409, "Ce fichier n'est pas un document à signer.")
    return node, version.content, bloc


def _source(docs: Documents, db: Session, member: Member, source_id: int) -> DocNode:
    """Le document choisi dans Docs : un PDF ou un Word que la personne peut lire."""
    source = docs._node(db, member, source_id)
    docs._require(db, member, docs._locate(db, member, source), LEVEL_VIEW)
    if source.kind != KIND_FILE or kind_of(source.name) is None:
        raise _error(422, "Choisissez un PDF ou un Word.")
    return source


def _stem(name: str) -> str:
    point = name.rfind(".")
    return name[:point] if point > 0 else name


def create(docs: Documents, db: Session, member: Member, space: str, parent_id: int | None, source_id: int | None = None) -> dict:
    """La tuile « Faire signer un document » (sans document), ou « Faire
    signer… » sur un PDF ou un Word : le fichier est créé à côté."""
    source = _source(docs, db, member, source_id) if source_id else None
    if source is not None:
        space, parent_id = source.space, source.parent_id
    contenu = {"schema": app_content.SCHEMA, "entry": {"blocks": [_new_block()]}, "result": {"blocks": []}}
    nom = f"Signature : {_stem(source.name)}" if source is not None else DEFAULT_NAME
    cree = docs.apps.create(db, member, space, parent_id, "question", nom, content=contenu)
    if source is not None:
        attach(docs, db, member, cree["id"], source.id)
    return {**cree, "folder_id": parent_id, "family": "question"}


def attach(docs: Documents, db: Session, member: Member, node_id: int, source_id: int) -> dict:
    """« Le document » (§2.1) : un PDF reste tel quel ; un Word devient des
    blocs de l'appli, au-dessus du bloc, qu'on corrige dans l'Aperçu."""
    node, contenu, bloc = _node_for(docs, db, member, node_id)
    if node.status not in (None, "draft"):
        raise _error(409, "Repassez le fichier en Brouillon pour changer de document.")
    source = _source(docs, db, member, source_id)
    blocs = []
    if kind_of(source.name) == "word":
        chemin, nom, _ = docs.content(db, member, source.id)
        html = preview.convert_to_html(chemin, nom)
        if html is None:
            raise _error(503, "Ce Word n'a pas pu être lu. Enregistrez-le en PDF, puis déposez le PDF.")
        blocs = html_to_blocks(html)
        if not blocs:
            raise _error(422, "Ce Word est vide.")
    nouveau = {**bloc, "props": {**(bloc.get("props") or {}), "source": source.id}}
    docs.apps.save(db, member, node.id, {**contenu, "entry": {"blocks": [*blocs, nouveau]}})
    # Le nom par défaut, éventuellement numéroté (« … (2) ») : on le remplace.
    if re.fullmatch(rf"{re.escape(DEFAULT_NAME)}( \(\d+\))?", node.name):
        docs.update(db, member, node.id, name=f"Signature : {_stem(source.name)}")
    return {"kind": kind_of(source.name), "name": source.name}


# ----------------------------------------------------------------------
# Un Word en blocs (§2.2) : titres, paragraphes, listes, gras ; un tableau
# devient une ligne de texte par rangée.
# ----------------------------------------------------------------------

_STYLES = {"b": "bold", "strong": "bold", "i": "italic", "em": "italic", "u": "underline"}
_SKIP = {"head", "style", "script", "title"}


class _Reader(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[dict] = []
        self.lists: list[str] = []
        self.styles: list[str] = []
        self.current: dict | None = None
        self.row: list[str] | None = None
        self.cell: list[str] | None = None
        self.skip = 0

    def _open(self, kind: str, props: dict | None = None) -> None:
        if self.current is None:
            self.current = {"id": uuid.uuid4().hex, "type": kind, "props": props or {}, "content": [], "children": []}

    def _close(self) -> None:
        bloc, self.current = self.current, None
        if bloc is None:
            return
        runs = bloc["content"]
        if runs:
            runs[0]["text"] = runs[0]["text"].lstrip()
            runs[-1]["text"] = runs[-1]["text"].rstrip()
        bloc["content"] = [r for r in runs if r["text"]]
        if bloc["content"]:
            self.blocks.append(bloc)

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._close()
            self._open("heading", {"level": min(int(tag[1]), 3)})
        elif tag in ("ul", "ol"):
            self._close()
            self.lists.append(tag)
        elif tag == "li":
            self._close()
            self._open("numberedListItem" if self.lists and self.lists[-1] == "ol" else "bulletListItem")
        elif tag == "p" and self.cell is None:
            self._open("paragraph")
        elif tag == "tr":
            self._close()
            self.row = []
        elif tag in ("td", "th"):
            self.cell = []
        elif tag in _STYLES:
            self.styles.append(_STYLES[tag])
        elif tag == "br":
            self.handle_data(" ")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
        elif tag in ("h1", "h2", "h3", "h4", "h5", "h6", "li") or tag == "p" and self.current and self.current["type"] == "paragraph":
            self._close()
        elif tag in ("ul", "ol"):
            self._close()
            if self.lists:
                self.lists.pop()
        elif tag in ("td", "th") and self.cell is not None:
            if self.row is not None:
                self.row.append(" ".join("".join(self.cell).split()))
            self.cell = None
        elif tag == "tr" and self.row is not None:
            cases = [c for c in self.row if c]
            self.row = None
            if cases:
                self._open("paragraph")
                self.current["content"].append({"type": "text", "text": " · ".join(cases), "styles": {}})
                self._close()
        elif tag in _STYLES and _STYLES[tag] in self.styles:
            self.styles.reverse()
            self.styles.remove(_STYLES[tag])
            self.styles.reverse()

    def handle_data(self, data):
        if self.skip:
            return
        texte = re.sub(r"\s+", " ", data)
        if self.cell is not None:
            self.cell.append(texte)
            return
        if self.current is None:
            if not texte.strip():
                return
            self._open("paragraph")
        styles = {s: True for s in sorted(set(self.styles))}
        runs = self.current["content"]
        if runs and runs[-1]["styles"] == styles:
            runs[-1]["text"] = (runs[-1]["text"] + texte).replace("  ", " ")
        else:
            runs.append({"type": "text", "text": texte, "styles": styles})


def html_to_blocks(html: str) -> list[dict]:
    lecteur = _Reader()
    lecteur.feed(html)
    lecteur.close()
    lecteur._close()
    return lecteur.blocks


# ----------------------------------------------------------------------
# Le PDF à signer (§3) et ses pages
# ----------------------------------------------------------------------


def _stored_bytes(docs: Documents, db: Session, node: DocNode) -> tuple[bytes, DocVersion]:
    version = db.get(DocVersion, node.current_version_id or 0)
    stocke = db.get(StoredFile, version.stored_file_id) if version is not None else None
    if stocke is None:
        raise _error(409, "Le document à signer est introuvable : choisissez-le de nouveau.")
    return docs.storage.path(node.org_id, stocke.sha256).read_bytes(), version


def _source_node(db: Session, node: DocNode, bloc: dict) -> DocNode | None:
    source = db.get(DocNode, props(bloc)["source"] or 0)
    if source is None or source.org_id != node.org_id or source.deleted_at is not None or source.kind != KIND_FILE:
        return None
    return source


def _to_sign(docs: Documents, db: Session, node: DocNode, contenu: dict, bloc: dict) -> tuple[bytes, DocNode, DocVersion | None]:
    """Le PDF tel qu'il sera signé : un PDF déposé tel quel ; un Word, son
    texte corrigé mis en page A4 (même moteur que le PV)."""
    source = _source_node(db, node, bloc)
    if source is None:
        raise _error(409, "Choisissez d'abord le document à faire signer.")
    if kind_of(source.name) == "word":
        texte = minutes._html_blocks(contenu.get("entry", {}).get("blocks", []), bloc)
        return minutes._render(texte), source, None
    data, version = _stored_bytes(docs, db, source)
    return data, source, version


def _open_pdf(data: bytes) -> pymupdf.Document:
    try:
        pdf = pymupdf.open(stream=data, filetype="pdf")
    except Exception:  # noqa: BLE001 (n'importe quel PDF abîmé)
        raise _error(422, "Ce PDF est illisible. Enregistrez-le de nouveau, puis déposez-le.") from None
    if pdf.needs_pass:
        raise _error(422, "Ce PDF est protégé par un mot de passe : déposez une version sans mot de passe.")
    return pdf


def frozen(db: Session, node: DocNode) -> DocSignEvent | None:
    """L'événement `validated` en cours (None si le document n'est pas figé,
    ou s'il a été repassé en Brouillon depuis)."""
    dernier = db.scalar(
        select(DocSignEvent)
        .where(DocSignEvent.node_id == node.id, DocSignEvent.event.in_(("validated", "reset")))
        .order_by(DocSignEvent.id.desc()).limit(1)
    )
    return dernier if dernier is not None and dernier.event == "validated" else None


def _shown(docs: Documents, db: Session, node: DocNode, contenu: dict, bloc: dict) -> bytes | None:
    """Le PDF dont l'Aperçu montre les pages : le PDF figé, sinon le PDF
    déposé ; None pour un Word en Brouillon (on corrige son texte)."""
    fige = frozen(db, node)
    if fige is not None:
        stocke = db.get(StoredFile, fige.detail["stored_file_id"])
        return docs.storage.path(node.org_id, stocke.sha256).read_bytes()
    source = _source_node(db, node, bloc)
    if source is None or kind_of(source.name) != "pdf":
        return None
    return _stored_bytes(docs, db, source)[0]


def overview(docs: Documents, db: Session, member: Member, node_id: int) -> dict:
    node, contenu, bloc = _node_for(docs, db, member, node_id, LEVEL_VIEW)
    source = _source_node(db, node, bloc)
    fige = frozen(db, node)
    pages = 0
    data = _shown(docs, db, node, contenu, bloc)
    if data is not None:
        pages = _open_pdf(data).page_count
    return {
        "source": {"id": source.id, "name": source.name, "kind": kind_of(source.name)} if source is not None else None,
        "missing": source is None and bool(props(bloc)["source"]),
        "frozen": {"sha256": fige.detail["sha256"], "pages": fige.detail["pages"], "at": fige.at.isoformat()} if fige else None,
        "pages": pages,
        # Déjà envoyé pour signature : « Voir les résultats » s'ouvre (§2.5).
        "signers": len(minutes.signers(db, node)),
    }


def page_png(docs: Documents, db: Session, member: Member, node_id: int, number: int) -> bytes:
    node, contenu, bloc = _node_for(docs, db, member, node_id, LEVEL_VIEW)
    data = _shown(docs, db, node, contenu, bloc)
    pdf = _open_pdf(data) if data is not None else None
    if pdf is None or not 1 <= number <= pdf.page_count:
        raise _error(404, "Page introuvable")
    return pdf[number - 1].get_pixmap(dpi=PAGE_DPI).tobytes("png")


# ----------------------------------------------------------------------
# Valider fige le document (§1, obligation 1)
# ----------------------------------------------------------------------


def on_status(docs: Documents, db: Session, member: Member, node: DocNode, status: str | None) -> None:
    """Appelé avant chaque changement d'état d'un fichier de l'appli : sortir
    du Brouillon fige le document, y revenir l'écrit au journal."""
    version = docs.apps.current_version(db, node)
    bloc = block_of(version.content) if version is not None else None
    if bloc is None:
        return
    brouillon = (None, "draft")
    if node.status in brouillon and status in ("validated", "official"):
        freeze(docs, db, member, node, version.content, bloc)
    elif node.status not in brouillon and status in brouillon and frozen(db, node) is not None:
        # Le texte va changer : les signatures déjà faites sont annulées
        # (§6) ; le journal en garde la trace, les liens restent les mêmes.
        signees = sum(1 for s in minutes.signers(db, node) if s.answered_at)
        minutes.reset_signatures(db, node)
        db.add(DocSignEvent(
            org_id=node.org_id, node_id=node.id, event="reset",
            detail={"by": member.person_id, "by_name": member.display_name, "signatures": signees},
        ))


def freeze(docs: Documents, db: Session, member: Member, node: DocNode, contenu: dict, bloc: dict) -> DocSignEvent:
    data, source, version = _to_sign(docs, db, node, contenu, bloc)
    pages = _open_pdf(data).page_count
    stocke = docs._store(db, node.org_id, "a-signer.pdf", io.BytesIO(data))
    evenement = DocSignEvent(
        org_id=node.org_id, node_id=node.id, event="validated",
        detail={
            "sha256": stocke.sha256, "stored_file_id": stocke.id, "pages": pages,
            "source_id": source.id, "source_name": source.name, "source_version_id": version.id if version else None,
            "by": member.person_id, "by_name": member.display_name,
        },
    )
    db.add(evenement)
    return evenement


# ----------------------------------------------------------------------
# Étape 2 : « Faire signer à qui ? » (§2.3) et le lien du signataire (§2.4)
# ----------------------------------------------------------------------

SIGN = minutes.SIGN
LINK_DAYS = 14
MAX_IMAGE = 300_000  # octets d'un tracé (PNG) une fois décodé
MAX_REASON = 1000
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
# Un client (adresse IP, appareil) : ce que le journal note d'un navigateur.
Client = tuple[str | None, str | None]
NO_CLIENT: Client = (None, None)


def _event(db: Session, node: DocNode, event: str, send_id: int | None = None, client: Client = NO_CLIENT, **detail) -> None:
    db.add(DocSignEvent(
        org_id=node.org_id, node_id=node.id, send_id=send_id, event=event, ip=client[0], user_agent=client[1],
        detail=detail or None,
    ))


def _since(db: Session, node: DocNode, fige: DocSignEvent | None) -> list[DocSignEvent]:
    """Les événements depuis le document figé en cours (un retour en
    Brouillon remet tout le monde à zéro)."""
    if fige is None:
        return []
    return list(db.scalars(
        select(DocSignEvent).where(DocSignEvent.node_id == node.id, DocSignEvent.id > fige.id).order_by(DocSignEvent.id)
    ))


def _expires(s: DocSend) -> datetime:
    return (s.sent_at or s.created_at or utcnow()) + timedelta(days=LINK_DAYS)


def _document(fige: DocSignEvent | None, node: DocNode) -> str:
    return _stem(fige.detail["source_name"]) if fige is not None else node.name


def _who(bureau: dict, person_id: int | None, name: str) -> str:
    """« Karim Benali, trésorier·e » pour quelqu'un du bureau, sinon le nom."""
    b = bureau.get(person_id) if person_id is not None else None
    return f"{name}, {minutes._labels(b.functions)}" if b is not None and b.functions else name


def consent_text(bureau: dict, s: DocSend, document: str) -> str:
    """La phrase de la case à cocher (§1, obligation 4)."""
    return f"Je soussigné(e) {_who(bureau, s.person_id, s.name)}, ai lu le document « {document} » et je le signe."


def _state(s: DocSend, mine: list[DocSignEvent]) -> tuple[str, DocSignEvent | None]:
    """Où en est un signataire : signé, refusé, lu, ouvert, envoyé…"""
    noms = {e.event: e for e in mine}
    if s.answered_at:
        return "signed", noms.get("signed")
    for etat in ("refused", "read", "opened"):
        if etat in noms:
            return etat, noms[etat]
    return {"failed": "failed", "pending": "pending"}.get(s.status, "sent"), None


def signers_status(docs: Documents, db: Session, member: Member, node_id: int) -> dict:
    """Le suivi de Diffuser et le bureau pour « Faire signer à qui ? »."""
    node, _, _ = _node_for(docs, db, member, node_id, LEVEL_MANAGE)
    fige = frozen(db, node)
    bureau = minutes._board(docs, db, node.org_id)
    evenements = _since(db, node, fige)
    lignes = []
    for s in minutes.signers(db, node):
        mine = [e for e in evenements if e.send_id == s.id]
        dernier = {e.event: e for e in mine}
        etat, quand = _state(s, mine)
        lignes.append({
            "id": s.id, "person_id": s.person_id, "name": s.name, "email": s.email,
            "functions": minutes._labels(bureau[s.person_id].functions) if s.person_id in bureau else "",
            "state": etat,
            "at": (s.answered_at if etat == "signed" else quand.at if quand is not None else s.sent_at or s.created_at).isoformat(),
            "reason": (dernier["refused"].detail or {}).get("reason") if "refused" in dernier and etat != "signed" else None,
            "error": s.error if s.status == "failed" else None,
            "expires_at": _expires(s).isoformat(),
            # « Signer moi-même » : son propre lien seulement.
            "token": s.token if member.person_id is not None and s.person_id == member.person_id else None,
        })
    return {
        "status": node.status,
        "frozen": fige is not None,
        "signers": lignes,
        "signed": sum(1 for x in lignes if x["state"] == "signed"),
        # Une puce par fonction du bureau, avec le nom de la personne (§2.3).
        "board": [
            {"function": mot[:1].upper() + mot[1:], "person_id": b.person_id, "name": b.name}
            for cle, mot in minutes.FUNCTION_WORDS.items() for b in bureau.values() if cle in b.functions
        ],
        "available": docs.mailer is not None and docs.mailer.available,
        # Étape 3 : le journal de preuves et le document signé (§2.5).
        "journal": journal(db, node, fige),
        "produced": _produced(evenements),
    }


def _wanted(docs: Documents, db: Session, node: DocNode, principals: list[dict], others: list[dict]) -> list[tuple[int | None, str, str | None]]:
    """Les personnes choisies : membres, rôles et cours de l'école, et
    « Quelqu'un d'autre » (nom et adresse email, hors de l'école)."""
    cles = []
    for p in principals or []:
        t, i = str(p.get("type", "")), str(p.get("id", ""))
        if t in ("member", "group") and i and (t, i) not in cles:
            cles.append((t, i))
    gens: list[tuple[int | None, str, str | None]] = [
        (g.person_id, g.name, g.email) for g in (docs.directory.recipients(db, node.org_id, cles) if cles else [])
    ]
    for o in others or []:
        nom, email = str(o.get("name") or "").strip()[:255], str(o.get("email") or "").strip().lower()[:255]
        if not nom:
            raise _error(422, "Écrivez le nom de la personne.")
        if not _EMAIL.match(email):
            raise _error(422, f"L'adresse email de {nom} n'est pas valable.")
        gens.append((None, nom, email))
    if not gens:
        raise _error(422, "Choisissez qui doit signer.")
    return gens


def _ready_to_send(docs: Documents, db: Session, member: Member, node_id: int) -> tuple[DocNode, dict, DocSignEvent]:
    node, _, bloc = _node_for(docs, db, member, node_id, LEVEL_MANAGE)
    fige = frozen(db, node)
    if node.status != "validated" or fige is None:
        raise _error(409, "Validez d'abord le document : il est figé avant les signatures.")
    return node, bloc, fige


def preview_send(docs: Documents, db: Session, member: Member, node_id: int, principals: list[dict], others: list[dict]) -> dict:
    """Le récapitulatif nominatif avant « Envoyer aux N »."""
    node, _, _ = _ready_to_send(docs, db, member, node_id)
    deja = minutes.signers(db, node)
    signe = {s.person_id for s in deja if s.answered_at and s.person_id} | {(s.email or "").lower() for s in deja if s.answered_at and not s.person_id}
    vus, partent, sans, faits = set(), [], [], []
    for pid, nom, email in _wanted(docs, db, node, principals, others):
        cle = pid if pid is not None else email
        if cle in vus:
            continue
        vus.add(cle)
        if cle in signe:
            faits.append(nom)
        elif not email:
            sans.append(nom)
        else:
            partent.append({"name": nom, "email": email})
    return {"count": len(partent), "recipients": partent, "without_email": sans, "signed": faits,
            "available": docs.mailer is not None and docs.mailer.available}


def send(
    docs: Documents, db: Session, member: Member, node_id: int, principals: list[dict], others: list[dict],
    client: Client = NO_CLIENT,
) -> tuple[dict, list[dict]]:
    """« Envoyer aux N » : un lien personnel à chacun (le même lien resert à
    une relance). Les personnes sans adresse email, ou qui ont déjà signé,
    sont laissées de côté sans bloquer les autres."""
    node, bloc, fige = _ready_to_send(docs, db, member, node_id)
    recap = preview_send(docs, db, member, node_id, principals, others)
    if not recap["available"]:
        raise _error(409, "L'envoi d'emails n'est pas configuré sur ce serveur.")
    if not recap["count"]:
        raise _error(409, "Tout le monde a déjà signé." if recap["signed"] else "Personne n'a d'adresse email parmi les personnes choisies.")
    deja = minutes.signers(db, node)
    par_personne = {s.person_id: s for s in deja if s.person_id}
    par_email = {(s.email or "").lower(): s for s in deja if not s.person_id}
    gens = {(pid if pid is not None else email): (pid, nom, email) for pid, nom, email in _wanted(docs, db, node, principals, others)}
    choisis = {r["email"] for r in recap["recipients"]}
    envois = []
    for pid, nom, email in gens.values():
        if email not in choisis:
            continue
        s = par_personne.get(pid) if pid is not None else par_email.get(email)
        if s is not None and s.answered_at:
            continue
        envois.append((_prepare(db, node, member, s, pid, nom, email), s is not None))
    return _dispatch(docs, db, member, node, bloc, fige, envois, client)


def remind(
    docs: Documents, db: Session, member: Member, node_id: int, send_ids: list[int] | None, client: Client = NO_CLIENT,
) -> tuple[dict, list[dict]]:
    """« Relancer » : une ligne (même après un refus), ou tous ceux qui n'ont
    ni signé ni refusé. Le lien reste le même ; il expire 14 jours après."""
    node, bloc, fige = _ready_to_send(docs, db, member, node_id)
    if docs.mailer is None or not docs.mailer.available:
        raise _error(409, "L'envoi d'emails n'est pas configuré sur ce serveur.")
    evenements = _since(db, node, fige)
    refus = {e.send_id for e in evenements if e.event == "refused"}
    gens = [
        s for s in minutes.signers(db, node)
        if not s.answered_at and s.email and (s.id in send_ids if send_ids is not None else s.id not in refus)
    ]
    if send_ids is not None and len(gens) != len(set(send_ids)):
        raise _error(409, "Cette personne a déjà signé, ou n'est pas parmi les signataires.")
    if not gens:
        raise _error(409, "Personne à relancer : tout le monde a signé ou refusé.")
    envois = [(_prepare(db, node, member, s, s.person_id, s.name, s.email), True) for s in gens]
    return _dispatch(docs, db, member, node, bloc, fige, envois, client)


def _prepare(db: Session, node: DocNode, member: Member, s: DocSend | None, pid: int | None, nom: str, email: str) -> DocSend:
    if s is None:
        s = DocSend(org_id=node.org_id, node_id=node.id, token=secrets.token_urlsafe(24), person_id=pid, channel=SIGN, test=False)
        db.add(s)
    s.name, s.email, s.status, s.error, s.sent_by = nom, email, "pending", None, member.person_id
    return s


def _dispatch(
    docs: Documents, db: Session, member: Member, node: DocNode, bloc: dict, fige: DocSignEvent,
    envois: list[tuple[DocSend, bool]], client: Client,
) -> tuple[dict, list[dict]]:
    db.flush()
    for s, relance in envois:
        _event(db, node, "reminded" if relance else "sent", s.id, client, email=s.email, by=member.person_id, by_name=member.display_name)
    docs._log(db, member, node, "sent", {"count": len(envois), "signature": True})
    db.commit()
    ecole, adresse = docs.mailer.org(db, node.org_id)
    moi = docs.directory.recipients(db, member.org_id, [("member", str(member.person_id))]) if member.person_id else []
    reply_to = moi[0].email if moi and moi[0].email else None
    bureau = minutes._board(docs, db, node.org_id)
    p = props(bloc)
    document, pages = _document(fige, node), fige.detail["pages"]
    expire = (utcnow() + timedelta(days=LINK_DAYS)).strftime("%d/%m/%Y")
    jobs = []
    for s, relance in envois:
        demande = (
            f"{_who(bureau, member.person_id, member.display_name)} vous demande de signer ce document : "
            f"« {document} » ({pages} page{'s' if pages > 1 else ''})."
        )
        texte, html = _invitation(
            s.name, [f"Rappel : {demande}" if relance else demande, *([p["message"]] if p["message"] else [])],
            f"{adresse}/r/{s.token}",
            [
                f"Ce lien vous est personnel, ne le transférez pas. Il expire le {expire}.",
                f"Message envoyé par {member.display_name} pour {ecole}."
                + (" Pour lui écrire, répondez simplement à ce mail." if reply_to else ""),
            ],
        )
        jobs.append({"send_id": s.id, "to": s.email, "subject": f"À signer : {document}", "text": texte, "html": html,
                     "sender_name": ecole, "reply_to": reply_to})
    return {"sent": len(envois)}, jobs


def _invitation(person: str, paragraphs: list[str], link: str, small: list[str]) -> tuple[str, str]:
    """Le mail du signataire, avec le bouton « Lire et signer » (comme ceux de Diffuser)."""
    texte = "\n\n".join([f"Bonjour {person},", *paragraphs, f"Lire et signer :\n{link}", *small]) + "\n"
    p = '<p style="margin:0 0 16px;white-space:pre-line">{}</p>'
    html = (
        '<div style="font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:1.5;color:#222;max-width:520px">'
        + p.format(f"Bonjour {escape(person)},")
        + "".join(p.format(escape(x)) for x in paragraphs)
        + '<div style="margin:24px 0;text-align:center">'
        + f'<a href="{escape(link)}" style="display:inline-block;min-width:220px;padding:14px 26px;border-radius:999px;'
        'background:#d9732b;color:#ffffff;font-size:17px;font-weight:bold;text-decoration:none">Lire et signer</a></div>'
        + "".join(f'<p style="margin:0 0 8px;font-size:13px;color:#777">{escape(x)}</p>' for x in small)
        + "</div>"
    )
    return texte, html


# ----------------------------------------------------------------------
# Le lien du signataire (public, sans compte)
# ----------------------------------------------------------------------

CLOSED = {
    "signed": "Vous avez déjà signé ce document.",
    "draft": "Le document est en cours de correction. Vous recevrez un nouveau mail.",
}


def is_link(content: dict) -> bool:
    """Un lien personnel vers un document à signer (et pas un PV) ?"""
    return block_of(content) is not None


def _link(docs: Documents, db: Session, token: str) -> tuple[DocSend, DocNode, dict, DocSignEvent | None, str]:
    s = db.scalar(select(DocSend).where(DocSend.token == token, DocSend.channel == SIGN)) if token else None
    node = db.get(DocNode, s.node_id) if s is not None else None
    version = docs.apps.current_version(db, node) if node is not None and node.deleted_at is None else None
    bloc = block_of(version.content) if version is not None else None
    if bloc is None:
        raise _error(404, "Ce lien ne mène plus à rien.")
    fige = frozen(db, node)
    if s.answered_at:
        etat = "signed"
    elif node.status not in ("validated", "official") or fige is None:
        etat = "draft"
    elif utcnow() > _expires(s):
        etat = "expired"
    else:
        etat = "open"
    return s, node, bloc, fige, etat


def _sender(docs: Documents, db: Session, s: DocSend) -> tuple[str, str | None]:
    """Qui a envoyé le lien : son nom et son adresse email."""
    trouves = docs.directory.recipients(db, s.org_id, [("member", str(s.sent_by))]) if s.sent_by else []
    return (trouves[0].name, trouves[0].email) if trouves else ("l'école", None)


def _open_or_raise(docs: Documents, db: Session, s: DocSend, etat: str) -> None:
    if etat == "expired":
        raise _error(410, f"Ce lien a expiré. Demandez à {_sender(docs, db, s)[0]} de vous le renvoyer.")
    if etat != "open":
        raise _error(409, CLOSED[etat])


def link_view(docs: Documents, db: Session, token: str, client: Client = NO_CLIENT) -> dict:
    """Ce que voit le signataire ; l'ouverture est notée au journal."""
    s, node, bloc, fige, etat = _link(docs, db, token)
    if etat == "open":
        _event(db, node, "opened", s.id, client)
        s.opened_at = s.opened_at or utcnow()
        db.commit()
    bureau = minutes._board(docs, db, node.org_id)
    document = _document(fige, node)
    mine = [e for e in _since(db, node, fige) if e.send_id == s.id]
    refus = next((e for e in reversed(mine) if e.event == "refused"), None)
    p = props(bloc)
    return {
        "signing": True,
        "state": etat,
        "org_id": node.org_id,
        "person": s.name,
        "sender": _sender(docs, db, s)[0],
        "document": document,
        "pages": fige.detail["pages"] if fige is not None and etat in ("open", "signed") else 0,
        "mode": p["mode"],
        "mention": p["mention"],
        "message": p["message"],
        "consent": consent_text(bureau, s, document),
        "read": any(e.event == "read" for e in mine),
        "refused": (refus.detail or {}).get("reason") if refus is not None and etat != "signed" else None,
        "signed_at": s.answered_at.isoformat() if s.answered_at else None,
        "expires_at": _expires(s).isoformat(),
    }


def link_page_png(docs: Documents, db: Session, token: str, number: int) -> bytes:
    _, node, _, fige, etat = _link(docs, db, token)
    if fige is None or etat not in ("open", "signed"):
        raise _error(404, "Page introuvable")
    stocke = db.get(StoredFile, fige.detail["stored_file_id"])
    pdf = _open_pdf(docs.storage.path(node.org_id, stocke.sha256).read_bytes())
    if not 1 <= number <= pdf.page_count:
        raise _error(404, "Page introuvable")
    return pdf[number - 1].get_pixmap(dpi=PAGE_DPI).tobytes("png")


def link_read(docs: Documents, db: Session, token: str, client: Client = NO_CLIENT) -> dict:
    """Le navigateur prévient quand le document a défilé jusqu'en bas (§1, obligation 3)."""
    s, node, _, fige, etat = _link(docs, db, token)
    _open_or_raise(docs, db, s, etat)
    if not any(e.event == "read" and e.send_id == s.id for e in _since(db, node, fige)):
        _event(db, node, "read", s.id, client)
        db.commit()
    return {"read": True}


def _png(data: str | None) -> bytes | None:
    """Un tracé au doigt, tel que l'envoie le navigateur (data:image/png;base64,…)."""
    prefixe = "data:image/png;base64,"
    if not isinstance(data, str) or not data.startswith(prefixe) or len(data) > MAX_IMAGE * 4 // 3 + 100:
        return None
    try:
        brut = base64.b64decode(data[len(prefixe):], validate=True)
    except ValueError:
        return None
    return brut if brut.startswith(b"\x89PNG") and len(brut) <= MAX_IMAGE else None


def link_sign(
    docs: Documents, db: Session, token: str, consent: bool, signature: str | None, initials: str | None,
    client: Client = NO_CLIENT,
) -> dict:
    """Signer (§2.4, étape 3) : refusé sans lecture enregistrée, sans la case
    cochée ou sans tracé (§1, obligations 3 et 4)."""
    s, node, bloc, fige, etat = _link(docs, db, token)
    _open_or_raise(docs, db, s, etat)
    if not any(e.event == "read" and e.send_id == s.id for e in _since(db, node, fige)):
        raise _error(409, "Lisez d'abord le document jusqu'en bas.")
    if consent is not True:
        raise _error(422, "Cochez la case pour signer.")
    trace = _png(signature)
    if trace is None:
        raise _error(422, "Signez avec le doigt dans le cadre.")
    p = props(bloc)
    paraphe = _png(initials) if p["mode"] == "initials" else None
    if p["mode"] == "initials" and paraphe is None:
        raise _error(422, "Dessinez vos initiales dans le petit cadre.")
    phrase = consent_text(minutes._board(docs, db, node.org_id), s, _document(fige, node))
    version = docs.apps.current_version(db, node)
    reponse = DocResponse(
        org_id=node.org_id, node_id=node.id, version_id=version.id, person_id=s.person_id, email=s.email,
        is_test=False, source="link", status="answered",
        values={bloc["id"]: {"signature": signature, "initials": initials if paraphe else None, "consent": phrase, "mention": p["mention"]}},
    )
    db.add(reponse)
    db.flush()
    s.response_id, s.answered_at = reponse.id, utcnow()
    _event(db, node, "consented", s.id, client, text=phrase)
    _event(
        db, node, "signed", s.id, client, response_id=reponse.id, document_sha256=fige.detail["sha256"],
        signature_sha256=hashlib.sha256(trace).hexdigest(),
        initials_sha256=hashlib.sha256(paraphe).hexdigest() if paraphe else None,
    )
    db.commit()
    return {"signed_at": s.answered_at.isoformat()}


def link_refuse(docs: Documents, db: Session, token: str, reason: str, client: Client = NO_CLIENT) -> dict:
    """« Je ne signe pas » : le motif au journal et par mail à l'expéditeur ;
    le lien reste ouvert (la personne peut changer d'avis)."""
    s, node, _, fige, etat = _link(docs, db, token)
    _open_or_raise(docs, db, s, etat)
    motif = (reason or "").strip()
    if not motif or len(motif) > MAX_REASON:
        raise _error(422, "Écrivez pourquoi vous ne signez pas.")
    _event(db, node, "refused", s.id, client, reason=motif)
    db.commit()
    nom, email = _sender(docs, db, s)
    adresse = email or (docs.association.contact_email(db, node.org_id) if docs.association else None)
    if adresse and docs.mailer is not None and docs.mailer.available:
        document = _document(fige, node)
        ecole = docs.mailer.org(db, node.org_id)[0]
        texte, html = minutes._mail([
            f"{s.name} ne signe pas le document « {document} ».",
            f"Son motif : « {motif} »",
            "Son lien reste ouvert : après une correction ou une explication, la personne pourra signer.",
        ], ecole, greeting=nom if email else None)
        try:
            docs.mailer.send(adresse, f"{s.name} ne signe pas « {document} »", texte, html, ecole, s.email)
        except Exception as erreur:  # noqa: BLE001 (le refus est noté au journal)
            logger.warning("Signature : email de refus non envoyé à %s : %s", adresse, erreur)
    return {"refused": True}


# ----------------------------------------------------------------------
# Étape 3 : le journal de preuves (§2.5) et le document signé (§3)
# ----------------------------------------------------------------------

_BROWSERS = (
    ("Edg/", "Edge"), ("OPR/", "Opera"), ("SamsungBrowser", "Samsung Internet"), ("Firefox/", "Firefox"),
    ("FxiOS", "Firefox"), ("CriOS", "Chrome"), ("Chrome/", "Chrome"), ("Safari/", "Safari"),
)
_SYSTEMS = (
    ("Android", "Android"), ("iPhone", "iPhone"), ("iPad", "iPad"), ("Windows", "Windows"), ("Mac OS X", "Mac"),
    ("CrOS", "ChromeOS"), ("Linux", "Linux"),
)


def device(user_agent: str | None) -> str:
    """L'appareil en clair (« Chrome sur Android ») ; le texte brut reste au journal."""
    if not user_agent:
        return ""
    navigateur = next((nom for cle, nom in _BROWSERS if cle in user_agent), "Navigateur")
    systeme = next((nom for cle, nom in _SYSTEMS if cle in user_agent), None)
    return f"{navigateur} sur {systeme}" if systeme else navigateur


def _paris(at: datetime) -> datetime:
    return at.replace(tzinfo=UTC).astimezone(assembly.TZ)


def _when(at: datetime) -> str:
    return f"{_paris(at):%d/%m/%Y à %H h %M}"


def _what(e: DocSignEvent, names: dict[int, str]) -> str:
    """Un événement du journal, en français."""
    d, qui = e.detail or {}, names.get(e.send_id or 0, "")
    return {
        "validated": f"Document validé et figé par {d.get('by_name', '')}, empreinte enregistrée",
        "sent": f"Lien personnel envoyé à {qui} ({d.get('email', '')})",
        "reminded": f"Relance envoyée à {qui} ({d.get('email', '')})",
        "opened": f"Lien ouvert par {qui}",
        "read": f"Document lu jusqu'en bas par {qui}",
        "consented": f"Consentement coché par {qui} : « {d.get('text', '')} »",
        "signed": f"Signature de {qui} enregistrée",
        "refused": f"{qui} ne signe pas : « {d.get('reason', '')} »",
        "produced": f"Document signé produit par {d.get('by_name', '')}, empreinte {d.get('sha256', '')}",
    }.get(e.event, e.event)


def journal(db: Session, node: DocNode, fige: DocSignEvent | None) -> list[dict]:
    """Le journal de preuves du document figé en cours, dans l'ordre."""
    if fige is None:
        return []
    names = {s.id: s.name for s in minutes.signers(db, node)}
    return [
        {"at": e.at.isoformat(), "event": e.event, "text": _what(e, names), "ip": e.ip or "", "device": device(e.user_agent)}
        for e in [fige, *_since(db, node, fige)]
    ]


def _produced(evenements: list[DocSignEvent]) -> dict | None:
    dernier = next((e for e in reversed(evenements) if e.event == "produced"), None)
    if dernier is None:
        return None
    d = dernier.detail or {}
    return {"id": d.get("file_id"), "name": d.get("name"), "sha256": d.get("sha256"), "at": dernier.at.isoformat()}


def _signed_name(fige: DocSignEvent) -> str:
    return f"{_stem(fige.detail['source_name'])} (signé).pdf"


def _frozen_bytes(docs: Documents, db: Session, node: DocNode, fige: DocSignEvent) -> bytes:
    """Le PDF figé, relu dans le stockage : son empreinte doit être celle de Valider."""
    stocke = db.get(StoredFile, fige.detail["stored_file_id"])
    chemin = docs.storage.path(node.org_id, stocke.sha256) if stocke is not None else None
    data = chemin.read_bytes() if chemin is not None and chemin.exists() else b""
    if hashlib.sha256(data).hexdigest() != fige.detail["sha256"]:
        logger.error("Signature : le PDF figé du fichier %s a changé ou a disparu", node.id)
        raise _error(409, "Le document figé a changé depuis la validation : le document signé n'est pas produit. Prévenez l'administrateur.")
    return data


def _png_bytes(data: str) -> bytes:
    return base64.b64decode(data.split(",", 1)[1])


def _signatures_html(docs: Documents, db: Session, node: DocNode, bloc: dict, gens: list[DocSend], archive: pymupdf.Archive) -> str:
    """La section Signatures : une case par signataire (mention, tracé, nom,
    fonction ou adresse, date et heure)."""
    bureau = minutes._board(docs, db, node.org_id)
    cases = []
    for i, s in enumerate(gens):
        reponse = db.get(DocResponse, s.response_id) if s.response_id else None
        v = ((reponse.values or {}).get(bloc["id"]) or {}) if reponse is not None else {}
        qualite = minutes._labels(bureau[s.person_id].functions) if s.person_id in bureau else ""
        archive.add(_png_bytes(v["signature"]), f"sig{i}.png")
        cases.append(
            "<td>"
            + (f"<i>{escape(v['mention'])}</i><br/>" if v.get("mention") else "")
            + f"<img src='sig{i}.png' width='160' height='60'/><br/><b>{escape(s.name)}</b>"
            + f"<br/><span class='small'>{escape(qualite or s.email or '')}</span>"
            + f"<br/><span class='small'>Signé en ligne le {_when(s.answered_at)}</span></td>"
        )
    lignes = "".join(f"<tr>{''.join(cases[i:i + 2])}</tr>" for i in range(0, len(cases), 2))
    # Seb, 22 octobre : en bas, qui a signé d'un coup d'œil (« Signé_MLP_MT »).
    qui = "_".join(initials(s.name) for s in gens)
    return f"<h2>Signatures</h2><table class='t sign'>{lignes}</table><p><b>Signé_{escape(qui)}</b></p>"


def initials(name: str) -> str:
    """« Marie-Laure Pesenti » -> « MLP »."""
    return "".join(mot[0] for mot in re.split(r"[\s\-]+", name) if mot).upper()


def _initials(pdf: pymupdf.Document, pages: int, images: list[bytes]) -> None:
    """Le paraphe : une petite case par signataire en bas à droite de chaque
    page du document, dans la marge."""
    for page in list(pdf)[:pages]:
        largeur, hauteur = page.rect.width, page.rect.height
        for i, image in enumerate(reversed(images)):
            case = pymupdf.Rect(largeur - 24 - (i + 1) * 46, hauteur - 32, largeur - 24 - i * 46 - 4, hauteur - 10)
            page.draw_rect(case, color=(0.84, 0.87, 0.86), width=0.5)
            page.insert_image(case, stream=image, keep_proportion=True)


def signed_pdf(docs: Documents, db: Session, node: DocNode, fige: DocSignEvent, bloc: dict) -> bytes:
    """Le PDF figé, avec les signatures (à la suite du texte d'un Word, sur
    une page ajoutée pour un PDF venu d'ailleurs), les paraphes, puis la page
    Certificat de preuves (§3)."""
    pdf = _open_pdf(_frozen_bytes(docs, db, node, fige))
    pages = pdf.page_count
    gens = minutes.signers(db, node)
    p = props(bloc)
    if p["mode"] == "initials":
        reponses = [db.get(DocResponse, s.response_id) for s in gens]
        _initials(pdf, pages, [_png_bytes(r.values[bloc["id"]]["initials"]) for r in reponses])
    archive = pymupdf.Archive()
    section = _signatures_html(docs, db, node, bloc, gens, archive)
    pose = False
    if kind_of(fige.detail["source_name"]) == "word":
        # À la suite du texte, s'il reste de la place sur la dernière page
        # (sinon rien n'est écrit et la section part sur une page ajoutée).
        derniere = pdf[pages - 1]
        bas = max((b[3] for b in derniere.get_text("blocks")), default=48)
        zone = pymupdf.Rect(48, bas + 12, derniere.rect.width - 48, derniere.rect.height - 48)
        if zone.height > 40:
            pose = derniere.insert_htmlbox(zone, section, css=assembly._CSS, archive=archive, scale_low=1)[0] >= 0
    if not pose:
        titre = f"<p class='org'>{escape(_document(fige, node))}</p>"
        pdf.insert_pdf(pymupdf.open(stream=minutes._render(titre + section, archive), filetype="pdf"))
    pdf.insert_pdf(pymupdf.open(stream=minutes._render(_certificate_html(docs, db, node, fige, gens, pages)), filetype="pdf"))
    sortie = pdf.tobytes(garbage=3, deflate=True)
    pdf.close()
    return sortie


def _certificate_html(docs: Documents, db: Session, node: DocNode, fige: DocSignEvent, gens: list[DocSend], pages: int) -> str:
    ecole, adresse = docs.mailer.org(db, node.org_id) if docs.mailer is not None else ("", "")
    bureau = minutes._board(docs, db, node.org_id)
    evenements = _since(db, node, fige)
    envoi = next((e for e in evenements if e.event == "sent"), None)
    par = (envoi.detail or {}).get("by_name", "") if envoi is not None else ""
    signataires = "".join(
        f"<tr><td>{escape(s.name)}</td><td>{escape(minutes._labels(bureau[s.person_id].functions) if s.person_id in bureau else '')}</td>"
        f"<td>{escape(s.email or '')}</td><td>{_when(s.answered_at)}</td></tr>"
        for s in gens
    )
    lignes = "".join(
        f"<tr><td>{_paris(datetime.fromisoformat(e['at'])):%d/%m/%Y %H:%M:%S}</td><td>{escape(e['text'])}</td>"
        f"<td>{escape(e['ip'])}</td><td>{escape(e['device'])}</td></tr>"
        for e in journal(db, node, fige)
    )
    return (
        f"<p class='org'>{escape(ecole.upper())}</p><h1>Certificat de preuves</h1>"
        f"<p><b>Document :</b> {escape(_document(fige, node))} ({pages} page{'s' if pages > 1 else ''})"
        + (f"<br/><b>Envoyé par :</b> {escape(par)}, le {_when(envoi.at)}" if envoi is not None else "")
        + f"<br/><b>Validé et figé le</b> {_when(fige.at)}</p>"
        f"<p><b>Empreinte SHA-256 du document validé :</b><br/>{fige.detail['sha256']}</p>"
        f"<h2>Signataires</h2><table class='t'><tr><th>Nom</th><th>Fonction</th><th>Adresse du lien</th><th>Signé le</th></tr>{signataires}</table>"
        f"<h2>Journal (heure de Paris)</h2><table class='t'><tr><th class='w24'>Date et heure</th><th>Événement</th>"
        f"<th class='w12'>Adresse IP</th><th class='w12'>Appareil</th></tr>{lignes}</table>"
        "<p class='foot'>Signature électronique simple au sens de l'article 1367 du Code civil et du règlement (UE) "
        f"n° 910/2014. Les preuves sont conservées par {escape(ecole)} ({escape(adresse)}). L'empreinte du présent "
        "document signé est enregistrée dans le journal de preuves de l'appli.</p>"
    )


def _store_next_to(docs: Documents, db: Session, member: Member, place: DocNode, nom: str, pdf: bytes) -> int:
    """Rangé à côté de `place` ; s'il y est déjà, une nouvelle version."""
    parent = DocNode.parent_id == place.parent_id if place.parent_id is not None else DocNode.parent_id.is_(None)
    deja = db.scalar(select(DocNode).where(
        DocNode.org_id == place.org_id, DocNode.space == place.space, parent, DocNode.name == nom,
        DocNode.kind == KIND_FILE, DocNode.deleted_at.is_(None),
    ))
    if deja is not None:
        docs.new_version(db, member, deja.id, nom, io.BytesIO(pdf))
        return deja.id
    return docs.upload(db, member, place.space, place.parent_id, nom, io.BytesIO(pdf))["id"]


def produce(docs: Documents, db: Session, member: Member, node_id: int, client: Client = NO_CLIENT) -> tuple[dict, list[dict]]:
    """« Produire le document signé » : seulement quand tout le monde a signé
    (décision de Seb, 22 octobre). Le refaire range une nouvelle version."""
    node, _, bloc = _node_for(docs, db, member, node_id, LEVEL_MANAGE)
    fige = frozen(db, node)
    if node.status not in ("validated", "official") or fige is None:
        raise _error(409, "Validez d'abord le document.")
    gens = minutes.signers(db, node)
    if not gens:
        raise _error(409, "Personne n'a encore été invité à signer.")
    manque = [s.name for s in gens if not s.answered_at]
    if manque:
        raise _error(409, f"Possible quand tout le monde a signé : il manque {', '.join(manque)}.")
    pdf = signed_pdf(docs, db, node, fige, bloc)
    source = db.get(DocNode, fige.detail["source_id"])
    vivant = source is not None and source.org_id == node.org_id and source.deleted_at is None
    nom = _signed_name(fige)
    file_id = _store_next_to(docs, db, member, source if vivant else node, nom, pdf)
    empreinte = hashlib.sha256(pdf).hexdigest()
    _event(db, node, "produced", None, client, sha256=empreinte, file_id=file_id, name=nom, by=member.person_id, by_name=member.display_name)
    if node.status == "validated":
        node.status, node.updated_at = "official", utcnow()
        docs._log(db, member, node, "status", {"from": "validated", "to": "official"})
    db.commit()
    return {"id": file_id, "name": nom, "sha256": empreinte}, _signed_mails(docs, db, member, node, fige, gens, nom, pdf)


def _signed_mails(
    docs: Documents, db: Session, member: Member, node: DocNode, fige: DocSignEvent, gens: list[DocSend], nom: str, pdf: bytes,
) -> list[dict]:
    """Le PDF signé par mail : à chaque signataire, à l'expéditeur et à
    l'adresse de contact de l'école (une seule fois par adresse)."""
    if docs.mailer is None or not docs.mailer.available:
        return []
    ecole = docs.mailer.org(db, node.org_id)[0]
    document = _document(fige, node)
    moi = docs.directory.recipients(db, member.org_id, [("member", str(member.person_id))]) if member.person_id else []
    contact = docs.association.contact_email(db, node.org_id) if docs.association else None
    gens_ = [(s.name, s.email) for s in gens if s.email]
    if moi and moi[0].email:
        gens_.append((moi[0].name, moi[0].email))
    vus, jobs = set(), []
    for qui, email in gens_:
        if email.lower() in vus:
            continue
        vus.add(email.lower())
        texte, html = minutes._mail([
            f"Le document « {document} » est signé par tous ({len(gens)} signature{'s' if len(gens) > 1 else ''}).",
            "Le PDF signé est joint à ce mail, avec en dernière page le certificat de preuves. Gardez-le : il fait foi.",
        ], ecole, greeting=qui)
        jobs.append({"to": email, "subject": f"Signé : {document}", "text": texte, "html": html, "sender_name": ecole, "attachments": [(nom, pdf)]})
    if contact and contact.lower() not in vus:
        texte, html = minutes._mail([
            f"Le document « {document} » est signé par tous ({len(gens)} signature{'s' if len(gens) > 1 else ''}).",
            f"Le PDF signé est joint ; il est aussi rangé dans Docs à côté de l'original (produit par {member.display_name}).",
        ], ecole)
        jobs.append({"to": contact, "subject": f"Signé : {document}", "text": texte, "html": html, "sender_name": ecole, "attachments": [(nom, pdf)]})
    return jobs


def deliver_signed(mailer, jobs: list[dict]) -> None:
    """Fait partir les mails du document signé (après la réponse)."""
    for job in jobs:
        try:
            mailer.send(job["to"], job["subject"], job["text"], job["html"], job["sender_name"], None, job["attachments"])
        except Exception as erreur:  # noqa: BLE001 (le document signé est rangé)
            logger.warning("Signature : document signé non envoyé à %s : %s", job["to"], erreur)


def status_text(docs: Documents, db: Session, node: DocNode) -> str:
    """Pour l'assistant (lire_fichier) : où en sont les signatures (§5)."""
    fige = frozen(db, node)
    gens = minutes.signers(db, node)
    if fige is None or not gens:
        return "Pas encore envoyé pour signature."
    evenements = _since(db, node, fige)
    mots = {"signed": "a signé", "refused": "ne signe pas", "read": "a lu, pas encore signé", "opened": "a ouvert le lien, pas encore signé"}
    lignes = []
    for s in gens:
        etat, _ = _state(s, [e for e in evenements if e.send_id == s.id])
        lignes.append(f"- {s.name} : {mots.get(etat, 'pas encore signé')}")
    signe = sum(1 for s in gens if s.answered_at)
    fait = _produced(evenements)
    fin = f"\nDocument signé produit : « {fait['name']} »." if fait else (
        "\nTout le monde a signé : le document signé peut être produit (produce_signed)." if signe == len(gens) else ""
    )
    return f"{signe} signature{'s' if signe > 1 else ''} sur {len(gens)} :\n" + "\n".join(lignes) + fin
