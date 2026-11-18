"""L'argent HelloAsso qui arrivera sur le compte de l'association après une
date (prévisionnel du Financier, spec/modules/financier.md §6.4).

Des faits seulement, lus dans la copie faite par la synchronisation : les
échéances à venir, et ce que HelloAsso a encaissé sans l'avoir versé avant
cette date. Aucune règle n'en est déduite (jour du virement mensuel, dates
fixes) : c'est le modèle du prévisionnel qui les trouve. Montants en euros.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .contact import FAILED, PAID, REFUNDED
from .models import HelloAssoRegistration, SeasonHelloAsso
from .sync import is_cancelled

# Versement arrivé sur le compte de l'association (Sambo Admin summary.py).
CASHED_OUT = "CashedOut"
# Paiements qui passent par HelloAsso (un chèque ou des espèces arrivent au
# club directement).
ONLINE_MEANS = ("Card", "Sepa", None)


def _euros(cents: int) -> float:
    return round(cents / 100, 2)


def to_come(db: Session, org_id: int, season_id: int, start: str) -> dict | None:
    """Ce que HelloAsso versera après `start` (AAAA-MM-JJ) pour la campagne
    de la saison, ou None (pas de campagne). Une échéance à venir compte
    toujours ; un paiement encaissé compte s'il n'est pas encore versé, ou
    versé après `start`."""
    campaign = db.scalar(
        select(SeasonHelloAsso).where(SeasonHelloAsso.org_id == org_id, SeasonHelloAsso.season_id == season_id)
    )
    if campaign is None or campaign.mode != "master":
        return None
    rows = db.scalars(
        select(HelloAssoRegistration).where(
            HelloAssoRegistration.org_id == org_id,
            HelloAssoRegistration.season_id == season_id,
            HelloAssoRegistration.gone_at.is_(None),
        )
    ).all()
    upcoming: dict[tuple[str, int | None], dict] = {}
    held = unpaid = once = several = cancelled = 0
    unknown = False
    for r in rows:
        if is_cancelled(r.state):
            cancelled += 1
            continue
        payments = r.payments or []
        if len(payments) > 1:
            several += 1
        else:
            once += 1
        for p in payments:
            state, amount = p.get("state"), p.get("amount") or 0
            if state in FAILED:
                unpaid += amount
            elif state in REFUNDED or p.get("means") not in ONLINE_MEANS:
                continue
            elif state in PAID:
                if "cash_out_state" not in p:
                    unknown = True  # copie faite avant le suivi des versements
                elif p["cash_out_state"] != CASHED_OUT or (p.get("cash_out_date") or "")[:10] > start:
                    held += amount
            else:
                key = ((p.get("date") or "")[:10], p.get("installment"))
                line = upcoming.setdefault(key, {"date": key[0], "echeance": key[1], "montant": 0, "adherents": 0})
                line["montant"] += amount
                line["adherents"] += 1
    lines = [{**line, "montant": _euros(line["montant"])} for _, line in sorted(upcoming.items(), key=lambda kv: (kv[0][0], kv[0][1] or 0))]
    total = sum(round(line["montant"] * 100) for line in lines) + held
    return {
        "campagne": campaign.form_name,
        "relueLe": campaign.synced_at.date().isoformat() if campaign.synced_at else None,
        "adherentsEnUneFois": once,
        "adherentsEnPlusieursFois": several,
        "echeancesAVenir": lines,
        "encaisseNonVerse": _euros(held),
        "totalSur": _euros(total),
        "nonComptes": {"impayes": _euros(unpaid), "resilies": cancelled},
        "aResynchroniser": unknown,
    }
