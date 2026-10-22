"""Signer un document (spec signature-documents.md), étape 1 : Préparer.

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
  en Brouillon écrit `reset`.

Le journal ne se modifie jamais : on n'y fait que des INSERT.
"""

from __future__ import annotations

import io
import re
import uuid
from html.parser import HTMLParser
from typing import TYPE_CHECKING

import pymupdf
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import app_content, minutes, preview
from .models import (
    KIND_FILE,
    LEVEL_EDIT,
    LEVEL_VIEW,
    DocNode,
    DocSignEvent,
    DocVersion,
    StoredFile,
)
from .ports import Member

if TYPE_CHECKING:
    from .service import Documents

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
        db.add(DocSignEvent(
            org_id=node.org_id, node_id=node.id, event="reset",
            detail={"by": member.person_id, "by_name": member.display_name},
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
