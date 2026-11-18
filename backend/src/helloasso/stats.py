"""« Statistiques des adhérents de la saison » (spec/modules/helloasso.md
§7.8), taken from Sambo Admin (helloasso/summary.py, seasons/projection.py):
adults and minors, average price, where the membership money is, the
accounts' balances and a projection to the end of the season. No model:
every figure can be explained line by line.

The accounts and the FFST licences belong to other modules: they come
through `Sources`, filled in by the school's application
(helloasso_contretemps); without them, those parts are left out.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from comptes import Compte, rbac, roles
from fastapi import Depends, FastAPI, HTTPException
from saisons import Saison, saison_courante_id
from saisons.portee import saison_demandee
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db

from .checks import age
from .models import HelloAssoRegistration
from .sync import is_cancelled

ADULT_AGE = 18

# HelloAsso payment states (PaymentState): paid, refunded, failed; any
# other state (Pending, Waiting...) is an instalment still to come.
PAID = {"Authorized", "Registered", "Corrected"}
REFUNDED = {"Refunded", "Refunding", "Contested"}
FAILED = {"Refused", "Error", "Canceled", "Abandoned", "Deleted", "Inconsistent", "NoDonation"}
# Where the money of a paid payment is (cashOutState): on the school's
# account, on its way (cash_out_date: day of the transfer), or still at
# HelloAsso (transfer not started, around the 10th of next month).
CASHED_OUT = {"CashedOut"}
CASH_OUT_PENDING = {"WaitingForCashOutConfirmation", "TransferInProgress"}
# Card or direct debit: the only payments that go through HelloAsso.
ONLINE = {"Card", "Sepa", None}

# Payroll projected to the end of the season (Financier categories).
PAYROLL = ("Salaires", "URSSAF", "Mutuelle")
REGULAR_MONTHS = 3
AVERAGE_MONTHS = 6


@dataclass
class Sources:
    """What other modules give (helloasso_contretemps): `ledger(db, org_id)`,
    the accounts as the Financier reads them (get_ledger), or None; and
    `licences(db, org_id, members)`, the FFST licences still to pay
    ({"count", "price"}), or None."""

    ledger: Callable[[Session, int], dict | None] | None = None
    licences: Callable[[Session, int, int], dict | None] | None = None


def _birth(r: HelloAssoRegistration):
    return next(
        (a.get("answer") for a in r.answers or [] if "naissance" in (a.get("name") or "").lower()), None
    )


def members(registrations: list[HelloAssoRegistration], today: date) -> dict:
    """Adults, minors, average price (euros), cancelled ones left out."""
    active = [r for r in registrations if not is_cancelled(r.state)]
    ages = [age(_birth(r), today) for r in active]
    total = sum(r.amount or 0 for r in active)
    return {
        "members": len(active),
        "adults": sum(1 for a in ages if a is not None and a >= ADULT_AGE),
        "minors": sum(1 for a in ages if a is not None and a < ADULT_AGE),
        "unknown_age": sum(1 for a in ages if a is None),
        "average_price": round(total / len(active)) / 100 if active else None,
        "total_price": total / 100,
    }


# HelloAsso transfer seen at the bank: its label ends with the day of the
# transfer ("VIR HELLOASSOPAY ... HELLOASSO 3711911 07-10-2026").
_BANK_CASH_OUT = re.compile(r"(\d{2})-(\d{2})-(\d{4})\s*$")


def bank_cash_outs(ledger: dict) -> dict[str, str]:
    """{day of the HelloAsso transfer: day it reached the bank}."""
    received: dict[str, str] = {}
    for row in ledger.get("rows", []):
        label = str(row.get("label") or "")
        match = _BANK_CASH_OUT.search(label)
        if "HELLOASSO" not in label.upper() or not match or (row.get("amount") or 0) <= 0:
            continue
        day, month, year = match.groups()
        key = f"{year}-{month}-{day}"
        received[key] = min(received.get(key, row["date"]), row["date"])
    return received


def cash(registrations: list[HelloAssoRegistration], received: dict[str, str] | None) -> dict:
    """Where the membership money is (euros, ISO days). `received`: the
    HelloAsso transfers seen at the bank (bank_cash_outs); it is the bank
    that says a transfer arrived, HelloAsso keeps « waiting » long after.
    Without it, HelloAsso's state is trusted.

    {"on_account": [{"date", "requested", "amount", "payments"}],
     "in_transit", "held", "upcoming": [{"month", "amount", "payments"}],
     "to_receive"}"""
    on_account: dict[str, list[int]] = {}
    in_transit, held = [], []
    upcoming: dict[str, list[int]] = {}
    for r in registrations:
        if is_cancelled(r.state):
            continue
        for p in r.payments or []:
            cents, state = p.get("amount") or 0, p.get("state")
            if state in FAILED or state in REFUNDED:
                continue
            if state not in PAID:
                upcoming.setdefault((p.get("date") or "")[:7], []).append(cents)
                continue
            out = p.get("cash_out_state")
            if out in REFUNDED or p.get("means") not in ONLINE:
                continue  # refunded, or paid to the school directly
            day = (p.get("cash_out_date") or "")[:10]
            if out not in CASHED_OUT and out not in CASH_OUT_PENDING:
                held.append(cents)
            elif (day in received) if received is not None else out in CASHED_OUT:
                on_account.setdefault(day, []).append(cents)
            else:
                in_transit.append(cents)
    arrived = sorted(
        (
            {"date": received[day] if received is not None else day, "requested": day,
             "amount": sum(c) / 100, "payments": len(c)}
            for day, c in on_account.items()
        ),
        key=lambda row: row["date"],
    )
    months = [
        {"month": month, "amount": sum(c) / 100, "payments": len(c)} for month, c in sorted(upcoming.items())
    ]
    in_transit_cents, held_cents = sum(in_transit), sum(held)
    upcoming_cents = sum(sum(c) for c in upcoming.values())
    return {
        "on_account": arrived,
        "on_account_total": sum(row["amount"] for row in arrived),
        "in_transit": in_transit_cents / 100,
        "held": held_cents / 100,
        "upcoming": months,
        "to_receive": (in_transit_cents + held_cents + upcoming_cents) / 100,
    }


def _add_months(year: int, month: int, delta: int) -> tuple[int, int]:
    index = year * 12 + month - 1 + delta
    return index // 12, index % 12 + 1


def _key(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def payroll(rows: list[dict], season_end: date, today: date) -> dict:
    """Salaries and contributions until the end of the season, from the
    accounts' operations (expenses positive). Per category: the amount of
    the last 3 months if identical (regular), else the average of the last
    6 full months (not before the first payment); months left: from this
    month if not yet paid, else next month, to the season's last month.

    {"total", "monthly", "months", "regular"}: `months` is None when the
    categories do not have the same number of months left."""
    current, last = (today.year, today.month), (season_end.year, season_end.month)
    lines = []
    for category in PAYROLL:
        cents: dict[str, int] = {}
        for row in rows:
            if row.get("category") == category:
                month = row["date"][:7]
                cents[month] = cents.get(month, 0) - round(row["amount"] * 100)
        if not cents:
            continue
        paid = sorted(m for m in cents if m <= _key(*current))
        recent = paid[-REGULAR_MONTHS:]
        if len(recent) == REGULAR_MONTHS and len({cents[m] for m in recent}) == 1:
            regular, monthly = True, cents[recent[-1]]
        else:
            used = [_key(*_add_months(*current, -k)) for k in range(AVERAGE_MONTHS, 0, -1)]
            used = [m for m in used if m >= paid[0]] if paid else []
            used = used or paid[-1:] or sorted(cents)[-1:]
            regular, monthly = False, round(sum(cents.get(m, 0) for m in used) / len(used))
        first = _add_months(*current, 1) if _key(*current) in cents else current
        months = max(0, last[0] * 12 + last[1] - (first[0] * 12 + first[1]) + 1)
        lines.append((monthly, months, regular))
    months = {m for _, m, _ in lines}
    return {
        "total": sum(monthly * m for monthly, m, _ in lines) / 100,
        "monthly": sum(monthly for monthly, _, _ in lines) / 100,
        "months": months.pop() if len(months) == 1 else None,
        "regular": all(regular for _, _, regular in lines),
    }


def accounts(ledger: dict) -> list[dict]:
    return [
        {"name": a["name"], "balance": a["balance"], "as_of": a.get("asOf")}
        for a in ledger.get("accounts", [])
        if a.get("balance") is not None
    ]


def statistics(
    db: Session, org_id: int, season: Saison, sources: Sources, finances: bool, today: date | None = None
) -> dict:
    """Everything the screen shows; balances and projection only when
    `finances` (Accès au Financier)."""
    today = today or date.today()
    registrations = list(db.scalars(
        select(HelloAssoRegistration).where(
            HelloAssoRegistration.org_id == org_id, HelloAssoRegistration.season_id == season.id
        )
    ))
    try:
        ledger = sources.ledger(db, org_id) if sources.ledger else None
    except Exception as erreur:  # noqa: BLE001 (the statistics never depend on it)
        print(f"HelloAsso, statistiques de l'école {org_id} : comptes illisibles ({erreur})")
        ledger = None
    figures = members(registrations, today)
    result = {
        "season": season.nom,
        "season_end": season.date_fin.isoformat(),
        **figures,
        "cash": cash(registrations, bank_cash_outs(ledger) if ledger else None),
        "finances": finances,
        "accounts": None,
        "balance": None,
        "payroll": None,
        "licences": None,
        "projected": None,
    }
    if not finances or not ledger:
        return result
    result["accounts"] = accounts(ledger)
    result["balance"] = sum(a["balance"] for a in result["accounts"])
    result["payroll"] = payroll(ledger.get("rows", []), season.date_fin, today)
    try:
        result["licences"] = sources.licences(db, org_id, figures["members"]) if sources.licences else None
    except Exception as erreur:  # noqa: BLE001
        print(f"HelloAsso, statistiques de l'école {org_id} : licences FFST illisibles ({erreur})")
    licences = result["licences"]["count"] * result["licences"]["price"] if result["licences"] else 0
    result["projected"] = round(
        (result["balance"] + result["cash"]["to_receive"] - result["payroll"]["total"] - licences) * 100
    ) / 100
    return result


class StatsReceiver:
    def __init__(self, app: FastAPI, sources: Sources) -> None:
        self.sources = sources
        app.get("/ecoles/{ecole_id}/helloasso/statistiques")(self.statistiques)

    def statistiques(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """Tout admin ; soldes et projection avec l'Accès au Financier."""
        rbac.require_admin(appelant, ecole_id)
        season_id = saison_demandee() or saison_courante_id(db, ecole_id)
        season = db.get(Saison, season_id) if season_id else None
        if season is None or season.ecole_id != ecole_id:
            raise HTTPException(status_code=404, detail="Pas de saison")
        return statistics(db, ecole_id, season, self.sources, roles.has_right(appelant, roles.DROIT_FINANCIER))
