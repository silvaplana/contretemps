"""Source boîte mail (spec/modules/import-auto-pieces.md §4.1) : l'appli lit
la boîte de réception sans rien déplacer ni marquer lu. Un mail sans pièce
jointe PDF ou photo est ignoré ; avec, chaque pièce jointe devient une pièce
si le mail répond à l'un des critères de la fiche."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AutoImportRule
from .service import ACCEPTES, SkipRule, SourceFile, mime_of

PAGES = 3  # 3 × 40 mails par passage, les plus récents ; le reste est déjà vu
DEFAULT_SENDERS = ("urssaf",)
DEFAULT_WORDS = ("facture", "note d'honoraires", "note d’honoraires", "reçu", "recu", "remboursement")


def _words(text: str) -> list[str]:
    return [w.strip().lower() for w in text.replace(";", ",").split(",") if w.strip()]


def _day(value) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def mail_source(connection, who: Callable[[Session, int, str], str | None], reader=None):
    """La source « mail » de `AutoImport`.

    `connection` : `core.mail_connection` ; `who(db, org_id, adresse)` : la
    nature que donne un expéditeur connu (« honoraires » pour un prof,
    « frais » pour un adhérent), sinon None ; `reader(db, rule, contenu,
    mime, nom)` : vrai si la pièce jointe montre un montant, une date, un
    SIRET ou un numéro de facture (lecteur des factures)."""

    def suppliers(db: Session, org_id: int) -> set[str]:
        from notes_frais.models import NoteFrais

        rows = db.scalars(select(NoteFrais.supplier).where(NoteFrais.org_id == org_id, NoteFrais.supplier.is_not(None)))
        return {s.strip().lower() for s in rows if s and len(s.strip()) > 2}

    def files(db: Session, rule: AutoImportRule) -> list[SourceFile]:
        from mail.connection import NotConnected

        org_id, box = rule.organization_id, rule.source_ref
        try:
            client = connection.client(db, org_id, box)
            messages, before = [], None
            for _ in range(PAGES):
                page = client.list("inbox", before=before)
                messages += page["messages"]
                if not page["hasMore"] or not page["messages"]:
                    break
                before = min(m["uid"] for m in page["messages"])
        except NotConnected:
            raise SkipRule("La boîte mail n'est pas connectée.") from None
        except Exception as erreur:
            raise SkipRule(f"La boîte mail ne répond pas : {erreur}") from erreur

        senders = _words(rule.mail_senders)
        words = _words(rule.mail_words) or list(DEFAULT_WORDS)
        known = None
        result = []
        for m in messages:
            if not m.get("hasAttachments"):
                continue
            uid = m["uid"]
            sender = (m.get("from") or [{}])[0]
            address = (sender.get("address") or "").lower()
            nature = who(db, org_id, address) if address else None
            text = f"{m.get('subject') or ''} {m.get('snippet') or ''}".lower()
            label = f"{sender.get('name') or ''} {address}".lower()
            if known is None:
                known = suppliers(db, org_id)
            by_sender = (nature is not None or any(s in label for s in (senders or DEFAULT_SENDERS))
                         or (not senders and any(s in label for s in known)))
            by_words = any(w in text for w in words)
            try:
                detail = client.peek("inbox", uid)
            except Exception:
                continue
            for a in detail["attachments"]:
                mime = a["contentType"] if a["contentType"] in ACCEPTES else mime_of(a["filename"])
                if mime not in ACCEPTES:
                    continue

                def read(index=a["index"], uid=uid):
                    return client.attachment("inbox", uid, index)[0]

                check = None
                if not (by_sender or by_words):
                    if not (rule.mail_need_amount and reader is not None):
                        continue
                    check = reader
                result.append(SourceFile(
                    key=f"mail:{box}:{detail.get('messageId') or uid}:{a['index']}", name=a["filename"],
                    modified=None, read=read, mime=mime, day=_day(m.get("date")), nature=nature, check=check,
                ))
        return result

    return files
