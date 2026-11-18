"""Members entirely imposed by HelloAsso (spec/modules/helloasso.md §7): a
season with a campaign has no other source of members. The lock refuses
student cards created, imported or deleted by hand; the rest reads the copy
made by the synchronisation (`helloasso_registrations`) for the members
table and card: amount, discount code, photo, HelloAsso status, answers,
payer, payments. Uploaded files (photo, medical certificate...) stay at
HelloAsso: the server relays them, and keeps only the photo thumbnail."""

from __future__ import annotations

import io
import os
import re
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

from saisons import saison_courante_id
from sqlalchemy import select
from sqlalchemy.orm import Session

from .campaign import Campaigns
from .models import HelloAssoRegistration
from .sync import is_cancelled

LOCKED = (
    "Les adhérents de cette saison viennent de HelloAsso : on les ajoute sur HelloAsso "
    "(paiement en espèces ou par chèque compris), ils arrivent par la synchronisation, "
    "et on ne les supprime pas."
)
# Thumbnails only: a photo does not change once uploaded (Sambo Admin).
PHOTOS_DIR = Path(os.environ.get("HELLOASSO_PHOTOS_DIR", "./data/helloasso-photos"))
# A file uploaded in a HelloAsso form (the only URLs the server relays).
_FILE_URL = re.compile(r"^/customFieldsAnswer/\d+$")


def lock(db: Session, org_id: int) -> str | None:
    """The `Eleves.locks` entry: the current season has a campaign and the
    module is on (switching it off, or « Nos champs », opens the cards)."""
    from registry.activation import disabled

    season_id = saison_courante_id(db, org_id)
    if season_id is None or Campaigns.current(db, season_id) is None:
        return None
    return None if "helloasso" in disabled(db, org_id) else LOCKED


def _key(text: str | None) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode().lower()


def is_file_url(url) -> bool:
    if not isinstance(url, str):
        return False
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.netloc == "docs.helloasso.com" and bool(_FILE_URL.match(parsed.path))


def files(answers: list[dict]) -> list[dict]:
    """The files uploaded with the form: [{index, name}], `index` being the
    answer's position (what the relay route asks for)."""
    return [
        {"index": i, "name": a.get("name") or "Fichier"}
        for i, a in enumerate(answers or [])
        if is_file_url(a.get("answer"))
    ]


def photo_index(answers: list[dict]) -> int | None:
    """The ID photo: the first uploaded file whose question says « photo »
    (« photo d'identité » at Alliance Sambo Combat)."""
    for f in files(answers):
        if "photo" in _key(f["name"]):
            return f["index"]
    return None


def _main(registrations: list[HelloAssoRegistration]) -> HelloAssoRegistration:
    """The registration a card shows: an active one before a cancelled one,
    the latest first."""
    return sorted(registrations, key=lambda r: (not is_cancelled(r.state), r.order_date or "", r.id))[-1]


def _by_member(db: Session, org_id: int, season_id: int) -> dict[int, list[HelloAssoRegistration]]:
    grouped: dict[int, list[HelloAssoRegistration]] = {}
    for r in db.scalars(
        select(HelloAssoRegistration).where(
            HelloAssoRegistration.org_id == org_id,
            HelloAssoRegistration.season_id == season_id,
            HelloAssoRegistration.member_id.is_not(None),
            HelloAssoRegistration.gone_at.is_(None),
        )
    ):
        grouped.setdefault(r.member_id, []).append(r)
    return grouped


def table(db: Session, org_id: int, season_id: int) -> dict[int, dict]:
    """{card: the HelloAsso columns of the members table} (spec §7.2), the
    counters of the Contact buttons included (§7.6)."""
    from .checks import season_checks, view
    from .contact import counts, phone

    mails, sms = counts(db, org_id)
    grouped = _by_member(db, org_id, season_id)
    checks = season_checks(db, org_id, [_main(rs).item_id for rs in grouped.values()])
    out = {}
    for member_id, registrations in grouped.items():
        r = _main(registrations)
        out[member_id] = {
            "rank": 0,
            "check": view(checks.get(r.item_id)),
            "mails": mails.get(r.item_id, 0),
            "sms": sms.get(r.item_id, 0),
            "has_phone": phone(r) is not None,
            "amount": r.amount,
            "discount_code": r.discount_code,
            "state": r.state,
            "cancelled": is_cancelled(r.state),
            "photo": photo_index(r.answers) is not None,
        }
    # Order of Sambo Admin, which shows HelloAsso's (Seb, 18 November 2026):
    # newest order first, then the members of an order in their order.
    mains = sorted(((member_id, _main(rs)) for member_id, rs in grouped.items()), key=lambda m: _item_key(m[1]))
    mains.sort(key=lambda m: m[1].order_date or "", reverse=True)
    for rank, (member_id, _) in enumerate(mains):
        out[member_id]["rank"] = rank
    return out


def _item_key(r: HelloAssoRegistration) -> tuple[int, str]:
    return (int(r.item_id), "") if r.item_id.isdigit() else (0, r.item_id)


def table_answers(db: Session, org_id: int, season_id: int) -> dict[int, list[dict]]:
    """{card: the answers of its HelloAsso form} (the FFST module reads the
    gender there, spec/modules/ffst.md §5)."""
    return {member_id: _main(rs).answers or [] for member_id, rs in _by_member(db, org_id, season_id).items()}


def registration(db: Session, org_id: int, season_id: int, member_id: int) -> HelloAssoRegistration | None:
    registrations = _by_member(db, org_id, season_id).get(member_id)
    return _main(registrations) if registrations else None


def card(db: Session, r: HelloAssoRegistration) -> dict:
    """The HelloAsso part of a member's card (spec §7.3): membership, files,
    answers (files apart), payer, payments, messages sent."""
    from .checks import row, view
    from .contact import messages

    file_indexes = {f["index"] for f in files(r.answers)}
    return {
        "tier_name": r.tier_name,
        "amount": r.amount,
        "discount_code": r.discount_code,
        "state": r.state,
        "cancelled": is_cancelled(r.state),
        "order_date": r.order_date,
        "photo": photo_index(r.answers) is not None,
        "files": files(r.answers),
        "answers": [
            {"name": a.get("name") or "", "answer": a.get("answer")}
            for i, a in enumerate(r.answers or [])
            if i not in file_indexes and a.get("answer") not in (None, "")
        ],
        "payer_name": r.payer_name,
        "payer_email": r.payer_email,
        "payments": r.payments or [],
        "messages": messages(db, r.org_id, r.item_id),
        "check": view(row(db, r.org_id, r.item_id)),
    }


def thumbnail(content: bytes, size: int) -> bytes:
    """Square JPEG thumbnail (Sambo Admin, `get_photo_thumbnail`): EXIF
    orientation, centred crop. A PDF uploaded instead of a photo gives its
    first page."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        image = Image.open(io.BytesIO(content))
        image.load()
    except UnidentifiedImageError:
        import pymupdf

        with pymupdf.open(stream=content, filetype="pdf") as pdf:
            if pdf.page_count == 0:
                raise ValueError("PDF vide") from None
            pixmap = pdf[0].get_pixmap(matrix=pymupdf.Matrix(2, 2))
        mode = "RGBA" if pixmap.alpha else "RGB"
        image = Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
    image = ImageOps.exif_transpose(image).convert("RGB")
    width, height = image.size
    side = min(width, height)
    left, top = (width - side) // 2, (height - side) // 2
    image = image.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=82)
    return buffer.getvalue()


def thumbnail_path(org_id: int, url: str, size: int) -> Path:
    return PHOTOS_DIR / str(org_id) / f"{url.rsplit('/', 1)[-1]}_{size}.jpg"


# A payment refused or failed for good (spec §7.4, Sambo Admin
# FAILED_PAYMENT_STATES): an instalment still to come (Pending, Waiting...)
# is not unpaid.
FAILED_PAYMENTS = ("Refused", "Error", "Canceled", "Abandoned", "Deleted", "Inconsistent")


def unpaid(db: Session, org_id: int, season_id: int) -> list[dict]:
    """« Impayés HelloAsso » (spec §7.4): the registrations with at least one
    failed payment, read from the copy made by the synchronisation."""
    out = []
    for r in db.scalars(
        select(HelloAssoRegistration)
        .where(
            HelloAssoRegistration.org_id == org_id,
            HelloAssoRegistration.season_id == season_id,
            HelloAssoRegistration.gone_at.is_(None),
        )
        .order_by(HelloAssoRegistration.last_name, HelloAssoRegistration.first_name)
    ):
        refused = [p for p in r.payments or [] if p.get("state") in FAILED_PAYMENTS]
        if refused:
            out.append({
                "member_id": r.member_id,
                "first_name": r.first_name,
                "last_name": r.last_name,
                "email": r.payer_email,
                "total": r.amount,
                "unpaid": sum(p.get("amount") or 0 for p in refused),
                "refused": [{"date": p.get("date"), "amount": p.get("amount") or 0} for p in refused],
            })
    return out


def upcoming(db: Session, org_id: int, season_id: int, today: date | None = None) -> list[dict]:
    """« À encaisser » (Seb, 18 November 2026): the instalments the members
    still have to pay, first due first: neither paid nor refunded, of
    memberships that are not cancelled. `overdue`: its day has passed
    without payment (refused, or never tried)."""
    from .stats import PAID, REFUNDED

    today_iso = (today or date.today()).isoformat()

    out = []
    for r in db.scalars(
        select(HelloAssoRegistration).where(
            HelloAssoRegistration.org_id == org_id,
            HelloAssoRegistration.season_id == season_id,
            HelloAssoRegistration.gone_at.is_(None),
        )
    ):
        if is_cancelled(r.state):
            continue
        for p in r.payments or []:
            if p.get("state") not in PAID | REFUNDED:
                out.append({
                    "member_id": r.member_id,
                    "first_name": r.first_name,
                    "last_name": r.last_name,
                    "amount": p.get("amount") or 0,
                    "date": p.get("date"),
                    "installment": p.get("installment"),
                    "overdue": (p.get("date") or "")[:10] < today_iso,
                })
    return sorted(out, key=lambda e: (e["date"] or "", e["last_name"], e["first_name"]))
