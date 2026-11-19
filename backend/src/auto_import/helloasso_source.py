"""Source HelloAsso (spec/modules/import-auto-pieces.md §4.2) : un
versement HelloAsso = les paiements versés le même jour. Chaque versement
devient une vente À valider, une ligne par compte de produits d'après la
formule de chaque paiement (`helloasso_accounts` de la fiche). Le PDF du
détail est reconstitué par l'appli et dit qu'il l'est ; il n'est déposé
que si la fiche a une destination (seule exception à la règle du 10
novembre, accordée par Seb le 19 novembre)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from .models import AutoImportRule
from .service import SourceFile

CASHED_OUT = "CashedOut"
MENTION = "Pièce reconstituée par l'appli à partir du versement HelloAsso"


@dataclass(frozen=True)
class Payment:
    """Un paiement versé : qui, quelle formule, quelle échéance."""

    name: str
    formula: str
    amount: int  # centimes
    installment: int | None
    paid_on: str  # AAAA-MM-JJ, jour du paiement
    cash_out_date: date


def payouts(payments: list[Payment]) -> dict[date, list[Payment]]:
    """Les versements : paiements groupés par jour de versement."""
    result: dict[date, list[Payment]] = {}
    for p in sorted(payments, key=lambda p: (p.cash_out_date, p.paid_on, p.name)):
        result.setdefault(p.cash_out_date, []).append(p)
    return result


def lines(payments: list[Payment], accounts: dict) -> list[tuple[int | None, int, str]]:
    """Une ligne par formule (même compte = une ligne) : (compte, montant,
    formules). Une échéance d'une adhésion en plusieurs fois compte dans le
    versement qui l'a versée, rien de plus (Seb, 19 novembre)."""
    by_account: dict = {}
    for p in payments:
        account = accounts.get(p.formula)
        total, formulas = by_account.get(account, (0, []))
        if p.formula not in formulas:
            formulas = [*formulas, p.formula]
        by_account[account] = (total + p.amount, formulas)
    return [(account, total, ", ".join(f or "Sans formule" for f in formulas))
            for account, (total, formulas) in by_account.items() if total > 0]


def _euros(cents: int) -> str:
    return f"{cents / 100:,.2f} €".replace(",", " ").replace(".", ",")


def pdf(day: date, payments: list[Payment]) -> bytes:
    """Le détail du versement, marqué « reconstitué par l'appli »."""
    import pymupdf

    doc = pymupdf.open()
    page, y = None, 0

    def write(text: str, size: int = 10, bold: bool = False):
        nonlocal page, y
        if page is None or y > 800:
            page, y = doc.new_page(width=595, height=842), 50
        page.insert_text((50, y), text, fontsize=size, fontname="hebo" if bold else "helv")
        y += size + 6

    write(MENTION, 11, bold=True)
    write(f"Versement HelloAsso du {day.strftime('%d/%m/%Y')} : {_euros(sum(p.amount for p in payments))}", 14, bold=True)
    write(f"{len(payments)} paiement{'s' if len(payments) > 1 else ''}")
    y += 6
    for p in payments:
        echeance = f" (paiement {p.installment})" if p.installment else ""
        write(f"{p.paid_on[:10]}  {p.name} — {p.formula or 'Sans formule'}{echeance}  {_euros(p.amount)}")
    data = doc.tobytes()
    doc.close()
    return data


def helloasso_source(read_payments: Callable[[Session, int, int | None], list[Payment]]):
    """La source « helloasso » de `AutoImport`. `read_payments(db, org_id,
    season_id)` : les paiements versés de la copie HelloAsso."""

    def files(db: Session, rule: AutoImportRule) -> list[SourceFile]:
        accounts = {k: v for k, v in (rule.helloasso_accounts or {}).items() if v}
        result = []
        for day, group in payouts(read_payments(db, rule.organization_id, rule.season_id)).items():
            total = sum(p.amount for p in group)
            if total <= 0:
                continue
            result.append(SourceFile(
                key=f"helloasso:{rule.season_id or 0}:{day.isoformat()}",
                name=f"Versement HelloAsso {day.isoformat()} (reconstituée par l'appli).pdf",
                modified=None, read=lambda group=group, day=day: pdf(day, group), mime="application/pdf",
                day=day, nature="vente", sale_lines=lines(group, accounts), supplier="HelloAsso",
                description=f"Versement HelloAsso : {len(group)} paiement{'s' if len(group) > 1 else ''}",
            ))
        return result

    return files
