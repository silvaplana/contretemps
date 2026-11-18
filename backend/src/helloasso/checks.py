"""Check of the members' files (spec/modules/helloasso.md §7.5), taken from
Sambo Admin (`helloasso/verification.py`).

For one member: checks without the model (missing document, unreadable
birth date, unreadable file), then, if they uploaded at least one document,
ONE call to the model with the documents as images and the answers: it says,
for each item, whether it is right and if not why. The result is kept in
`helloasso_checks`; a file that is OK is not checked again.

The documents (the medical certificate is health data) are sent to the
model for this check only and never kept (Seb, 18 November 2026). The check
is off by default: each school turns it on (`OrgHelloAsso.check_files`).
"""

from __future__ import annotations

import base64
import io
import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timezone

import anthropic
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import HelloAssoCheck, HelloAssoRegistration
from .sync import is_cancelled

OK, PROBLEM, ERROR = "ok", "problem", "error"
ADULT_AGE = 18
# The form's documents, found by the name of their question.
DOCUMENTS = {
    "photo": ("Photo d'identité", re.compile(r"photo", re.I)),
    "certificat": ("Certificat médical", re.compile(r"certificat", re.I)),
    "autorisation": ("Autorisation parentale", re.compile(r"autorisation parentale", re.I)),
}
DATA = "donnees"
# Pages of a PDF sent to the model, and longest side of an image (pixels).
MAX_PAGES = 2
MAX_SIDE = 1400
# A simple check: Sonnet is enough. Dollars per million tokens (in, out).
MODEL = "claude-sonnet-5-5"
PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0), "claude-opus-5": (5.0, 25.0),
          "claude-opus-4-8": (5.0, 25.0)}

INSTRUCTIONS = """Tu aides le secrétaire d'une association sportive, {club}, à contrôler les dossiers d'inscription de ses adhérents.
On te donne les réponses d'un adhérent au formulaire d'inscription et les documents qu'il a déposés, en images. Pour chaque élément, dis s'il est correct ("ok": true) ou non ("ok": false), avec dans "raison" une phrase courte en français qui explique le problème (vide si tout va bien).

- photo : sois très tolérant. La photo est correcte dès qu'on y voit une personne, quels que soient le cadrage, la qualité, la tenue ou le décor : un selfie, une photo de groupe, une photo de vacances, et même la photo d'une carte d'identité, d'un passeport ou d'un autre document sur lequel figure le portrait de quelqu'un, sont acceptés. Ne refuse que s'il n'y a personne du tout sur l'image : un objet, un animal, un logo, un texte sans portrait, une image vide ou illisible.
- certificat : ce doit être un certificat médical (ou une attestation médicale) qui autorise la pratique du sport, établi pour cet adhérent (nom et prénom concordants, en tolérant la casse, les accents et l'ordre), daté, et signé ou tamponné par un médecin. Signale un certificat daté de plus d'un an avant la date du jour, un document qui n'est pas un certificat médical, un autre nom, ou un document illisible.
- autorisation : ce doit être une autorisation parentale pour un mineur, signée par un parent ou un représentant légal, et qui concerne cet adhérent. Signale un document qui n'en est pas une, non signé, ou illisible.
- donnees : signale seulement une anomalie nette dans les réponses (date de naissance impossible, téléphone ou e-mail manifestement faux, nom et prénom inversés ou fantaisistes). Ne signale ni les fautes de frappe mineures ni les différences de casse.

Si un document n'est pas fourni, réponds "ok": true et une raison vide pour lui : son absence est traitée ailleurs. En cas de doute raisonnable, laisse "ok": true ; ne signale que ce qu'un bénévole devrait vraiment aller regarder.
"""

_VERDICT = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}, "raison": {"type": "string"}},
    "required": ["ok", "raison"],
    "additionalProperties": False,
}
SCHEMA = {
    "type": "object",
    "properties": {key: _VERDICT for key in (*DOCUMENTS, DATA)},
    "required": [*DOCUMENTS, DATA],
    "additionalProperties": False,
}


class InspectionError(Exception):
    """The call failed (message shown as is); `cost`: what it cost anyway ($)."""

    def __init__(self, message: str, cost: float = 0.0) -> None:
        super().__init__(message)
        self.cost = cost


@dataclass
class Verdict:
    results: dict[str, dict]  # item -> {"ok": bool, "raison": str}
    cost: float  # dollars


def cost_usd(model_id: str, usage) -> float:
    input_price, output_price = next(
        (prices for key, prices in PRICES.items() if model_id.startswith(key)), PRICES[MODEL]
    )
    tokens_in = (
        (usage.input_tokens or 0)
        + 1.25 * (getattr(usage, "cache_creation_input_tokens", 0) or 0)
        + 0.1 * (getattr(usage, "cache_read_input_tokens", 0) or 0)
    )
    return (tokens_in * input_price + (usage.output_tokens or 0) * output_price) / 1_000_000


def to_images(content: bytes) -> list[bytes]:
    """An uploaded file (phone photo, scan, PDF) -> JPEG images for the
    model: the first MAX_PAGES pages of a PDF, or the image itself, turned
    upright (EXIF) and reduced. ValueError if unreadable."""
    import pymupdf
    from PIL import Image, ImageOps

    try:
        if content.startswith(b"%PDF"):
            with pymupdf.open(stream=content, filetype="pdf") as pdf:
                pages = []
                for page in list(pdf)[:MAX_PAGES]:
                    pixmap = page.get_pixmap(matrix=pymupdf.Matrix(2, 2), alpha=False)
                    pages.append(Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples))
        else:
            pages = [ImageOps.exif_transpose(Image.open(io.BytesIO(content))).convert("RGB")]
    except Exception as exc:  # noqa: BLE001 - any unreadable file, whatever its format
        raise ValueError("fichier illisible") from exc
    if not pages:
        raise ValueError("fichier vide")
    images = []
    for page in pages:
        page.thumbnail((MAX_SIDE, MAX_SIDE))
        buffer = io.BytesIO()
        page.save(buffer, format="JPEG", quality=80)
        images.append(buffer.getvalue())
    return images


class Inspector:
    """The call to the Claude API (key ANTHROPIC_API_KEY, like the Financier)."""

    def __init__(self, client: anthropic.Anthropic | None = None) -> None:
        self._client = client

    def inspect(self, club: str, answers: dict, documents: dict[str, list[bytes]], today: date) -> Verdict:
        if self._client is None:
            self._client = anthropic.Anthropic()
        content: list[dict] = [
            {
                "type": "text",
                "text": f"Date du jour : {today.isoformat()}\nAdhérent et réponses au formulaire (JSON) :\n"
                + json.dumps(answers, ensure_ascii=False, indent=1),
            }
        ]
        for key, images in documents.items():
            for number, image in enumerate(images, start=1):
                content.append({"type": "text", "text": f"Document « {key} » : {DOCUMENTS[key][0]}, page {number}"})
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/jpeg", "data": base64.b64encode(image).decode()},
                })
        missing = [key for key in DOCUMENTS if key not in documents]
        if missing:
            content.append({"type": "text", "text": "Documents non fournis : " + ", ".join(missing) + "."})
        params = {
            "model": MODEL,
            "max_tokens": 8000,
            "system": INSTRUCTIONS.format(club=club),
            "messages": [{"role": "user", "content": content}],
            "output_config": {"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
            # If the model declines, the API retries on the recommended fallback.
            "betas": ["server-side-fallback-2026-07-01"],
            "fallbacks": "default",
        }
        try:
            with self._client.beta.messages.stream(**params) as stream:
                response = stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 - any error of the call (no key, network...) as a clear message
            raise InspectionError(f"La vérification n’a pas pu se faire : {exc}") from exc
        cost = cost_usd(response.model or MODEL, response.usage)
        if response.stop_reason == "refusal":
            raise InspectionError("La vérification de ce dossier a été refusée.", cost)
        text = next((block.text for block in response.content if block.type == "text"), "")
        try:
            results = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InspectionError("Résultat de la vérification illisible.", cost) from exc
        return Verdict(results=results, cost=cost)


def age(birth, today: date) -> int | None:
    """« 14/03/2009 » or « 2009-03-14 » -> age, None if unreadable."""
    text = str(birth or "").strip()
    match = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", text)
    parts = (match.group(3), match.group(2), match.group(1)) if match else None
    if parts is None:
        match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", text)
        parts = match.groups() if match else None
    if parts is None:
        return None
    try:
        born = date(*(int(p) for p in parts))
    except ValueError:
        return None
    years = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return years if 0 <= years <= 110 else None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def row(db: Session, org_id: int, item_id: str) -> HelloAssoCheck | None:
    return db.scalar(select(HelloAssoCheck).where(HelloAssoCheck.org_id == org_id, HelloAssoCheck.item_id == item_id))


def is_ok(check: HelloAssoCheck | None) -> bool:
    return check is not None and (check.manual or check.status == OK)


def view(check: HelloAssoCheck | None) -> dict | None:
    """What the table and the card show: {ok, issues} (None: not checked)."""
    if check is None:
        return None
    return {"ok": is_ok(check), "issues": [] if is_ok(check) else list(check.issues or [])}


def check(
    db: Session,
    r: HelloAssoRegistration,
    fetch: Callable[[str], bytes],
    inspector: Inspector,
    club: str,
    today: date | None = None,
) -> HelloAssoCheck:
    """Checks one member and keeps the result (flush, no commit). `fetch(url)`
    reads an uploaded file at HelloAsso."""
    today = today or date.today()
    answers = {a.get("name"): a.get("answer") for a in r.answers or [] if a.get("type") != "File"}
    files = {
        key: next(
            (a["answer"] for a in r.answers or []
             if a.get("type") == "File" and a.get("answer") and pattern.search(a.get("name") or "")),
            None,
        )
        for key, (_, pattern) in DOCUMENTS.items()
    }
    issues: list[str] = []
    years = age(next((v for name, v in answers.items() if "naissance" in (name or "").lower()), None), today)
    if years is None:
        issues.append("Date de naissance absente ou illisible")
    if files["photo"] is None:
        issues.append("Photo d'identité manquante")
    if files["certificat"] is None:
        issues.append("Certificat médical manquant")
    if years is not None and years < ADULT_AGE and files["autorisation"] is None:
        issues.append("Autorisation parentale manquante (adhérent mineur)")

    documents: dict[str, list[bytes]] = {}
    for key, url in files.items():
        # An adult's parental authorisation is not checked.
        if url is None or (key == "autorisation" and years is not None and years >= ADULT_AGE):
            continue
        try:
            documents[key] = to_images(fetch(url))
        except ValueError as exc:
            issues.append(f"{DOCUMENTS[key][0]} : {exc}")
        except Exception:  # noqa: BLE001 - HelloAsso out of reach for this file
            issues.append(f"{DOCUMENTS[key][0]} : fichier indisponible sur HelloAsso")

    cost, status = 0.0, None
    if documents:
        identity = {
            "prenom": r.first_name,
            "nom": r.last_name,
            "age": years,
            "inscritLe": (r.order_date or "")[:10],
            "payeur": r.payer_name or "",
            "reponses": answers,
        }
        try:
            verdict = inspector.inspect(club, identity, documents, today)
            cost = verdict.cost
            labels = {**{key: label for key, (label, _) in DOCUMENTS.items()}, DATA: "Réponses au formulaire"}
            for key, label in labels.items():
                result = verdict.results.get(key) or {}
                if key != DATA and key not in documents:
                    continue
                if result.get("ok") is False:
                    issues.append(f"{label} : {(result.get('raison') or 'à vérifier').strip()}")
        except InspectionError as exc:
            cost, status = exc.cost, ERROR
            issues.append(str(exc))
    status = status or (PROBLEM if issues else OK)

    found = row(db, r.org_id, r.item_id)
    if found is None:
        found = HelloAssoCheck(org_id=r.org_id, item_id=r.item_id, cost=0.0)
        db.add(found)
    found.first_name, found.last_name = r.first_name, r.last_name
    found.status, found.issues, found.manual = status, issues, False
    found.model, found.checked_at = MODEL if documents else None, _now()
    found.cost = (found.cost or 0.0) + cost
    db.flush()
    return found


def validate(db: Session, r: HelloAssoRegistration, manual: bool = True) -> HelloAssoCheck:
    """« Valider le dossier » (or its undo): the file counts as OK and is not
    checked again; the reasons are kept for the undo."""
    found = row(db, r.org_id, r.item_id)
    if found is None:
        found = HelloAssoCheck(org_id=r.org_id, item_id=r.item_id, first_name=r.first_name,
                               last_name=r.last_name, status=PROBLEM, issues=[], cost=0.0)
        db.add(found)
    found.manual = manual
    db.flush()
    return found


def season_checks(db: Session, org_id: int, item_ids: list[str]) -> dict[str, HelloAssoCheck]:
    if not item_ids:
        return {}
    return {
        c.item_id: c
        for c in db.scalars(
            select(HelloAssoCheck).where(HelloAssoCheck.org_id == org_id, HelloAssoCheck.item_id.in_(item_ids))
        )
    }


def total_cost(db: Session, org_id: int) -> float:
    return sum(db.scalars(select(HelloAssoCheck.cost).where(HelloAssoCheck.org_id == org_id)))


def to_check(db: Session, org_id: int, season_id: int) -> list[HelloAssoRegistration]:
    """The season's members whose file is not OK (cancelled ones left out)."""
    registrations = [
        r for r in db.scalars(
            select(HelloAssoRegistration).where(
                HelloAssoRegistration.org_id == org_id,
                HelloAssoRegistration.season_id == season_id,
                HelloAssoRegistration.gone_at.is_(None),
            ).order_by(HelloAssoRegistration.last_name, HelloAssoRegistration.first_name)
        )
        if not is_cancelled(r.state)
    ]
    done = season_checks(db, org_id, [r.item_id for r in registrations])
    return [r for r in registrations if not is_ok(done.get(r.item_id))]


def report(club: str, results: list[HelloAssoCheck], cost: float, eur_per_usd: float) -> tuple[str, str]:
    """The mail at the end of « Vérifier les adhérents »: (subject, text)."""
    problems = [c for c in results if not is_ok(c)]
    lines = [f"Vérification des dossiers terminée : {len(results)} dossier(s) vérifié(s), "
             f"{len(results) - len(problems)} OK, {len(problems)} à regarder."]
    for c in problems:
        lines.append("")
        lines.append(f"{c.first_name} {c.last_name}")
        lines += [f"- {issue}" for issue in c.issues]
    lines.append("")
    lines.append(f"Coût de cette vérification : {cost * eur_per_usd:.2f} €".replace(".", ","))
    return f"{club} : vérification des dossiers", "\n".join(lines)


class Runs:
    """« Vérifier les adhérents » in the background, one at a time per
    school; `background=False` runs it right away (tests)."""

    def __init__(self, background: bool = True) -> None:
        self.background = background
        self._running: set[int] = set()
        self._lock = threading.Lock()

    def running(self, org_id: int) -> bool:
        return org_id in self._running

    def start(self, org_id: int, work: Callable[[], None]) -> bool:
        with self._lock:
            if org_id in self._running:
                return False
            self._running.add(org_id)

        def run() -> None:
            try:
                work()
            finally:
                self._running.discard(org_id)

        if self.background:
            threading.Thread(target=run, daemon=True).start()
        else:
            run()
        return True
