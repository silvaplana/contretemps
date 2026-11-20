"""Source HelloAsso (spec/modules/import-auto-pieces.md §4.2) : un
versement HelloAsso = les paiements versés le même jour. Chaque versement
devient une vente À valider, une ligne par compte de produits d'après la
formule de chaque paiement (`helloasso_accounts` de la fiche), la part
licence de la formule (`helloasso_licences`) vers le compte des licences à
reverser, un remboursement en moins dans le versement qui le reprend. Le PDF du
détail est reconstitué par l'appli et dit qu'il l'est ; il n'est déposé
que si la fiche a une destination (seule exception à la règle du 10
novembre, accordée par Seb le 19 novembre)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date
from html import escape

from sqlalchemy.orm import Session

from .models import AutoImportRule
from .service import SourceFile

CASHED_OUT = "CashedOut"
MENTION = "Pièce reconstituée par l'appli à partir du versement HelloAsso"


@dataclass(frozen=True)
class Payment:
    """Un paiement versé : qui, quelle formule, quelle échéance. Un
    remboursement d'un paiement déjà versé : montant négatif, `paid_on` le
    jour du remboursement, pas encore de `cash_out_date` (HelloAsso le reprend
    sur le versement suivant)."""

    name: str
    formula: str
    amount: int  # centimes
    installment: int | None
    paid_on: str  # AAAA-MM-JJ, jour du paiement (ou du remboursement)
    cash_out_date: date | None


def payouts(payments: list[Payment]) -> dict[date, list[Payment]]:
    """Les versements : paiements groupés par jour de versement. Un
    remboursement va dans le premier versement d'après son jour ; sans
    versement après lui, il attend le suivant."""
    result: dict[date, list[Payment]] = {}
    paid = [p for p in payments if p.amount > 0 and p.cash_out_date is not None]
    for p in sorted(paid, key=lambda p: (p.cash_out_date, p.paid_on, p.name)):
        result.setdefault(p.cash_out_date, []).append(p)
    days = sorted(result)
    for r in sorted((p for p in payments if p.amount < 0), key=lambda p: (p.paid_on, p.name)):
        day = next((d for d in days if d.isoformat() > r.paid_on[:10]), None)
        if day is not None:
            result[day].append(replace(r, cash_out_date=day))
    return result


def licence_part(p: Payment, licences: dict) -> int:
    """La part licence d'un paiement (centimes, du signe du paiement) : la
    part de la formule, prise sur le premier paiement de l'inscription (une
    adhésion en plusieurs fois la paie avec sa première échéance)."""
    if p.installment not in (None, 1):
        return 0
    part = min(licences.get(p.formula) or 0, abs(p.amount))
    return part if p.amount > 0 else -part


def lines(payments: list[Payment], accounts: dict, licences: dict | None = None,
          licence_account: int | None = None) -> list[tuple[int | None, int, str]]:
    """Une ligne par formule (même compte = une ligne) : (compte, montant,
    formules). Une échéance d'une adhésion en plusieurs fois compte dans le
    versement qui l'a versée, rien de plus (Seb, 19 novembre). La part
    licence va sur le compte des licences ; un remboursement vient en moins
    sur les mêmes comptes."""
    by_account: dict = {}

    def add(account, amount: int, label: str):
        total, formulas = by_account.get(account, (0, []))
        if label not in formulas:
            formulas = [*formulas, label]
        by_account[account] = (total + amount, formulas)

    for p in payments:
        licence = licence_part(p, licences or {})
        add(accounts.get(p.formula), p.amount - licence, p.formula)
        if licence:
            add(licence_account, licence, "Part licence")
    return [(account, total, ", ".join(f or "Sans formule" for f in formulas))
            for account, (total, formulas) in by_account.items() if total != 0]


def _euros(cents: int) -> str:
    return f"{cents / 100:,.2f} €".replace(",", " ").replace(".", ",")


def pdf(day: date, payments: list[Payment]) -> bytes:
    """Le détail du versement, marqué « reconstitué par l'appli »."""
    import pymupdf

    doc = pymupdf.open()
    doc.set_metadata({"title": f"Versement HelloAsso du {day.strftime('%d/%m/%Y')} (reconstituée par l'appli)"})
    page, y = None, 0

    def write(text: str, size: int = 10, bold: bool = False):
        # insert_htmlbox : police Noto intégrée, qui a « € » et « — »
        # (la Helvetica de base les affiche « · »).
        nonlocal page, y
        if page is None or y > 790:
            page, y = doc.new_page(width=595, height=842), 40
        weight = "bold" if bold else "normal"
        page.insert_htmlbox(pymupdf.Rect(50, y, 545, y + 3 * size),
                            f'<p style="font-size:{size}px;font-weight:{weight};margin:0">{escape(text)}</p>')
        y += size + 6

    write(MENTION, 11, bold=True)
    write(f"Versement HelloAsso du {day.strftime('%d/%m/%Y')} : {_euros(sum(p.amount for p in payments))}", 14, bold=True)
    paid = sum(1 for p in payments if p.amount > 0)
    refunds = len(payments) - paid
    write(f"{paid} paiement{'s' if paid > 1 else ''}"
          + (f", {refunds} remboursement{'s' if refunds > 1 else ''}" if refunds else ""))
    y += 6
    for p in payments:
        echeance = f" (paiement {p.installment})" if p.installment else ""
        quoi = "Remboursement " if p.amount < 0 else ""
        write(f"{p.paid_on[:10]}  {p.name} — {quoi}{p.formula or 'Sans formule'}{echeance}  {_euros(p.amount)}")
    data = doc.tobytes()
    doc.close()
    return data


def _description(group: list[Payment]) -> str:
    paid = sum(1 for p in group if p.amount > 0)
    refunds = len(group) - paid
    text = f"Versement HelloAsso : {paid} paiement{'s' if paid > 1 else ''}"
    return text + (f", {refunds} remboursement{'s' if refunds > 1 else ''}" if refunds else "")


def helloasso_source(read_payments: Callable[[Session, int, int | None], list[Payment]],
                     licence_account: Callable[[Session, int], dict | None] | None = None):
    """La source « helloasso » de `AutoImport`. `read_payments(db, org_id,
    season_id)` : les paiements versés (et remboursés) de la copie HelloAsso ;
    `licence_account(db, org_id)` : le compte des licences à reverser
    ({id, code, libelle} de sa catégorie), None s'il n'est pas au plan."""

    def files(db: Session, rule: AutoImportRule) -> list[SourceFile]:
        accounts = {k: v for k, v in (rule.helloasso_accounts or {}).items() if v}
        licences = {k: v for k, v in (rule.helloasso_licences or {}).items() if v and v > 0}
        compte = licence_account(db, rule.organization_id) if licences and licence_account else None
        result = []
        for day, group in payouts(read_payments(db, rule.organization_id, rule.season_id)).items():
            total = sum(p.amount for p in group)
            if total <= 0:
                continue
            result.append(SourceFile(
                key=f"helloasso:{rule.season_id or 0}:{day.isoformat()}",
                name=f"Versement HelloAsso {day.isoformat()} (reconstituée par l'appli).pdf",
                modified=None, read=lambda group=group, day=day: pdf(day, group), mime="application/pdf",
                day=day, nature="vente", sale_lines=lines(group, accounts, licences, compte and compte["id"]),
                supplier="HelloAsso", description=_description(group),
            ))
        return result

    return files
