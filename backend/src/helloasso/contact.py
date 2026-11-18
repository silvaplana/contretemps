"""Contact and cancellation from the members table (spec/modules/helloasso.md
§7.6, §7.7), taken from Sambo Admin (`helloasso/mails.py`,
`summary.cancellation_preview`): a mail to the payer, a text message
prepared in the phone, preset messages, and the preview of a cancellation.
Everything is filed under the HelloAsso id of the membership (`item_id`)."""

from __future__ import annotations

import html
import re
from collections.abc import Callable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import HelloAssoMail, HelloAssoRegistration, HelloAssoSms, HelloAssoTemplate
from .sync import is_cancelled

KINDS = ("mail", "sms")
# Sambo Admin `summary.py`: cashed, or neither cashed nor to come.
PAID = ("Authorized", "Registered", "Corrected")
REFUNDED = ("Refunded", "Refunding", "Contested")
FAILED = ("Refused", "Error", "Canceled", "Abandoned", "Deleted", "Inconsistent")

# send(db, org_id, to, subject, text, html) -> the address in copy (the
# school's), or raises: the core's mail service, in the school's name.
SendMail = Callable[[Session, int, str, str, str, str], "str | None"]


class ContactError(ValueError):
    """Shown as is under the form."""


# --- Preset messages ---


def templates(db: Session, org_id: int, kind: str) -> list[dict]:
    if kind not in KINDS:
        raise ContactError("Genre de message inconnu")
    rows = db.scalars(
        select(HelloAssoTemplate)
        .where(HelloAssoTemplate.org_id == org_id, HelloAssoTemplate.kind == kind)
        .order_by(HelloAssoTemplate.id.desc())
    )
    return [{"id": t.id, "subject": t.subject, "body": t.body} for t in rows]


def save_template(db: Session, org_id: int, kind: str, subject: str, body: str) -> list[dict]:
    if kind not in KINDS:
        raise ContactError("Genre de message inconnu")
    subject = " ".join((subject or "").split()) if kind == "mail" else ""
    body = (body or "").strip()
    if not body:
        raise ContactError("Le message est vide")
    if kind == "mail" and not subject:
        raise ContactError("L’objet est vide")
    exists = db.scalar(
        select(HelloAssoTemplate.id).where(
            HelloAssoTemplate.org_id == org_id,
            HelloAssoTemplate.kind == kind,
            HelloAssoTemplate.subject == subject,
            HelloAssoTemplate.body == body,
        )
    )
    if exists is None:
        db.add(HelloAssoTemplate(org_id=org_id, kind=kind, subject=subject, body=body))
        db.flush()
    return templates(db, org_id, kind)


def delete_template(db: Session, org_id: int, kind: str, template_id: int) -> list[dict]:
    template = db.get(HelloAssoTemplate, template_id)
    if template is not None and template.org_id == org_id and template.kind == kind:
        db.delete(template)
        db.flush()
    return templates(db, org_id, kind)


# --- Mail and text message ---


def send_mail(db: Session, send: SendMail, r: HelloAssoRegistration, subject: str, text: str) -> HelloAssoMail:
    """Mails the payer of this membership: the address kept from HelloAsso,
    never one given by the screen. A failure is logged too."""
    subject, text = (subject or "").strip(), (text or "").strip()
    if not subject or not text:
        raise ContactError("L’objet et le message sont obligatoires")
    if "\n" in subject or "\r" in subject:
        raise ContactError("L’objet doit tenir sur une ligne")
    to = (r.payer_email or "").strip()
    if not to:
        raise ContactError("Cet adhérent n’a pas d’adresse email chez HelloAsso")
    paragraphs = "".join(
        f"<p>{html.escape(block).replace(chr(10), '<br>')}</p>" for block in re.split(r"\n\s*\n", text) if block.strip()
    )
    mail = HelloAssoMail(
        org_id=r.org_id, item_id=r.item_id, first_name=r.first_name, last_name=r.last_name,
        to_email=to, subject=subject, body=text,
    )
    try:
        mail.cc = send(db, r.org_id, to, subject, text, paragraphs)
    except Exception as erreur:  # noqa: BLE001 - kept in the log, then shown
        mail.error = str(erreur) or "Le mail n’est pas parti"
    db.add(mail)
    db.flush()
    return mail


def normalize_phone(value) -> str | None:
    """« 06 12 34 56 78 » -> « +33612345678 », ready for an « sms: » link
    (Sambo Admin); None when missing or too short."""
    text = str(value or "").strip()
    digits = "".join(c for c in text if c.isdigit())
    if len(digits) < 9:
        return None
    if text.startswith("+"):
        return "+" + digits
    if digits.startswith("00"):
        return "+" + digits[2:]
    if len(digits) == 10 and digits.startswith("0"):
        return "+33" + digits[1:]
    if len(digits) == 9:
        return "+33" + digits
    return digits


def phone(r: HelloAssoRegistration) -> str | None:
    """The answer to the form's phone question."""
    for a in r.answers or []:
        if a.get("type") == "Phone" or "phone" in (a.get("name") or "").lower().replace("é", "e"):
            return normalize_phone(a.get("answer"))
    return None


def prepare_sms(db: Session, r: HelloAssoRegistration, text: str) -> HelloAssoSms:
    text = (text or "").strip()
    if not text:
        raise ContactError("Le message est obligatoire")
    number = phone(r)
    if number is None:
        raise ContactError("Cet adhérent n’a pas de numéro de téléphone chez HelloAsso")
    sms = HelloAssoSms(
        org_id=r.org_id, item_id=r.item_id, first_name=r.first_name, last_name=r.last_name, phone=number, body=text
    )
    db.add(sms)
    db.flush()
    return sms


def counts(db: Session, org_id: int) -> tuple[dict[str, int], dict[str, int]]:
    """({item_id: mails really sent}, {item_id: text messages prepared}):
    the counters on the Mail and SMS buttons."""
    mails = db.execute(
        select(HelloAssoMail.item_id, func.count())
        .where(HelloAssoMail.org_id == org_id, HelloAssoMail.error.is_(None))
        .group_by(HelloAssoMail.item_id)
    )
    sms = db.execute(
        select(HelloAssoSms.item_id, func.count()).where(HelloAssoSms.org_id == org_id).group_by(HelloAssoSms.item_id)
    )
    return dict(mails.all()), dict(sms.all())


def messages(db: Session, org_id: int, item_id: str) -> list[dict]:
    """« Messages envoyés » in the card, the latest first."""
    mails = db.scalars(select(HelloAssoMail).where(HelloAssoMail.org_id == org_id, HelloAssoMail.item_id == item_id))
    sms = db.scalars(select(HelloAssoSms).where(HelloAssoSms.org_id == org_id, HelloAssoSms.item_id == item_id))
    out = [
        {"kind": "mail", "at": m.sent_at, "subject": m.subject, "body": m.body, "sent": m.error is None,
         "error": m.error}
        for m in mails
    ] + [{"kind": "sms", "at": s.prepared_at, "subject": "", "body": s.body, "sent": True, "error": None} for s in sms]
    return sorted(out, key=lambda m: m["at"], reverse=True)


# --- Cancellation (spec §7.7) ---


def order(db: Session, org_id: int, season_id: int, order_id: str) -> list[HelloAssoRegistration]:
    return list(
        db.scalars(
            select(HelloAssoRegistration).where(
                HelloAssoRegistration.org_id == org_id,
                HelloAssoRegistration.season_id == season_id,
                HelloAssoRegistration.order_id == order_id,
                HelloAssoRegistration.gone_at.is_(None),
            ).order_by(HelloAssoRegistration.id)
        )
    )


def cancellation(registrations: list[HelloAssoRegistration]) -> dict:
    """What cancelling the order would change, shown before: its members
    (all cancelled together), what was cashed (not refunded) and the
    instalments to come (cancelled). Amounts in cents."""
    paid = scheduled = scheduled_count = 0
    for r in registrations:
        for p in r.payments or []:
            state, amount = p.get("state"), p.get("amount") or 0
            if state in PAID:
                paid += amount
            elif state not in FAILED and state not in REFUNDED:
                scheduled += amount
                scheduled_count += 1
    return {
        "members": [
            {"first_name": r.first_name, "last_name": r.last_name, "amount": r.amount} for r in registrations
        ],
        "paid": paid,
        "scheduled": scheduled,
        "scheduled_count": scheduled_count,
        "cancelled": bool(registrations) and all(is_cancelled(r.state) for r in registrations),
    }
