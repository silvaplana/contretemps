"""Documents de l'AG (spec/modules/financier.md §8.6) : Synthèse
Dépenses-Recettes, Balance, Grand livre, Honoraires par professeur, calculés
au centime depuis les lignes de banque (compte du plan confirmé, voir
accounting.py) et la caisse, pour la saison d'un bilan. Jamais un chiffre
écrit par un modèle : des additions.

Comptabilité de trésorerie : chaque ligne de banque est une écriture à deux
lignes (compte du plan contre 512x la banque, 530 la caisse) ; les soldes de
départ des comptes de trésorerie sont repris dans 110 « Report à nouveau »
pour que la Balance soit équilibrée. Les écritures de la partie double
(401, 411, lettrage, §8.7) viennent à l'étape 4.

Une ligne sans compte confirmé va dans « À classer » (dépense ou recette
selon le sens) plutôt que d'être inventée.
"""

from __future__ import annotations

import html
import io
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session

from .accounting import Accounting
from .exports import _CSS, _eur, _fr, html_to_pdf
from .models import EXPENSE, INCOME, FinCashLine
from .ports import Member, Season

# Numéros des comptes de trésorerie et de report (plan associatif).
BANK_BASE = "512"
CASH = "530"
CARRY_FORWARD = "110"
UNCLASSIFIED = {EXPENSE: ("65900", "Dépenses à classer"), INCOME: ("75900", "Recettes à classer")}

CLASS_LABELS = {
    "60": "Achats",
    "61": "Services extérieurs",
    "62": "Autres services extérieurs",
    "63": "Impôts et taxes",
    "64": "Charges de personnel",
    "65": "Autres charges",
    "66": "Charges financières",
    "67": "Charges exceptionnelles",
    "68": "Dotations",
    "70": "Ventes et prestations",
    "74": "Subventions",
    "75": "Produits de gestion courante",
    "76": "Produits financiers",
    "77": "Produits exceptionnels",
    "78": "Reprises",
}

KINDS = {
    "synthese": ("Synthèse Dépenses-Recettes", "xlsx", "simple"),
    "balance": ("Balance", "pdf", "complet"),
    "grand-livre": ("Grand livre", "pdf", "complet"),
    "honoraires": ("Honoraires par professeur", "xlsx", "complet"),
}


@dataclass
class AgPorts:
    """Ce que l'appli hôte fournit : les pièces à payer (fournisseurs,
    Synthèse), les honoraires payés par prof et par mois (DAS-2), et le
    rangement d'un fichier dans Docs › Financier › AG (ids des fichiers)."""

    unpaid: Callable[[Session, int], list[dict]] | None = None
    fees: Callable[[Session, int, str, str], list[dict]] | None = None
    store: Callable[[Session, Member, list[str], list[tuple[str, Path]]], list[int]] | None = None
    org_name: Callable[[Session, int], str] | None = None


@dataclass
class Line:
    """Une ligne du grand livre : date, journal, libellé, pièce, débit et
    crédit en centimes."""

    date: str
    journal: str
    label: str
    piece: str
    debit: int = 0
    credit: int = 0


@dataclass
class Account:
    number: str
    label: str
    nature: str  # depense, recette, banque, caisse, report
    event: str | None = None
    lines: list[Line] = field(default_factory=list)

    @property
    def debit(self) -> int:
        return sum(l.debit for l in self.lines)

    @property
    def credit(self) -> int:
        return sum(l.credit for l in self.lines)

    @property
    def balance(self) -> int:
        """Solde signé : positif = débiteur."""
        return self.debit - self.credit


class AgDocuments:
    def __init__(
        self,
        ledger: Callable[[Session, Member], dict],
        accounting: Accounting,
        seasons: Callable[[Session, int], list[Season]],
        ports: AgPorts | None = None,
    ) -> None:
        self.ledger = ledger
        self.accounting = accounting
        self.seasons = seasons
        self.ports = ports or AgPorts()

    # ----- le grand livre en mémoire -----

    def books(self, db: Session, member: Member, season: Season) -> dict[str, Account]:
        """Tous les comptes mouvementés sur la saison, avec leurs lignes, les
        soldes de départ de la trésorerie et le report à nouveau."""
        ledger = self.ledger(db, member)
        rows = [r for r in reversed(ledger["rows"]) if season.start_date <= r["date"] <= season.end_date]
        # Arrêté au dernier jour connu des comptes (jamais avant le début).
        as_of = max((a["asOf"] for a in ledger["accounts"] if a.get("asOf")), default=season.end_date)
        cutoff = max(season.start_date, min(season.end_date, as_of))
        chart = {a.id: a for a in self.accounting.accounts(db, member.org_id)}
        books: dict[str, Account] = {}

        def account(number: str, label: str, nature: str, event: str | None = None) -> Account:
            return books.setdefault(number, Account(number, label, nature, event))

        bank_numbers = {}
        for i, a in enumerate(sorted(ledger["allAccounts"], key=lambda a: a["id"])):
            bank_numbers[a["id"]] = (f"{BANK_BASE}{i + 1}", a["name"])

        # Soldes de départ de la trésorerie (banque : solde de la veille de la
        # saison, ou premier solde connu moins les opérations qui y mènent ;
        # caisse : lignes antérieures) contre 110.
        def effect(r: dict, aid: int, name: str) -> int:
            """Ce qu'une ligne de l'historique fait au compte aid (centimes)."""
            cents = round(r["amount"] * 100)
            if r.get("transfer"):
                return (-cents if r["accountId"] == aid else 0) + (cents if r["transfer"]["to"] == name else 0)
            return cents if r["accountId"] == aid else 0

        opening_total = 0
        all_rows = list(reversed(ledger["rows"]))
        for aid, (number, name) in bank_numbers.items():
            known = [r for r in all_rows if r["balances"].get(str(aid)) is not None]
            before = [r for r in known if r["date"] < season.start_date]
            if before:
                opening_cents = round(before[-1]["balances"][str(aid)] * 100)
            else:
                first = next((r for r in known if r["date"] >= season.start_date), None)
                if first is None:
                    continue
                until = all_rows[: all_rows.index(first) + 1]
                opening_cents = round(first["balances"][str(aid)] * 100) - sum(effect(r, aid, name) for r in until)
            acc = account(number, name, "banque")
            acc.lines.append(Line(season.start_date, "AN", "Solde au début de la saison", "", max(opening_cents, 0), max(-opening_cents, 0)))
            opening_total += opening_cents
        cash_before = sum(
            l.amount for l in db.scalars(select(FinCashLine).where(FinCashLine.org_id == member.org_id, FinCashLine.date < date.fromisoformat(season.start_date)))
        )
        if cash_before:
            account(CASH, "Caisse", "caisse").lines.append(Line(season.start_date, "AN", "Solde au début de la saison", "", max(cash_before, 0), max(-cash_before, 0)))
            opening_total += cash_before
        if opening_total:
            account(CARRY_FORWARD, "Report à nouveau", "report").lines.append(
                Line(season.start_date, "AN", "Trésorerie au début de la saison", "", max(-opening_total, 0), max(opening_total, 0))
            )

        # Caisse de la saison, et les retraits au distributeur (la ligne de
        # banque va alors dans 530, pas dans un compte du plan).
        cash_lines = list(
            db.scalars(
                select(FinCashLine).where(
                    FinCashLine.org_id == member.org_id,
                    FinCashLine.date >= date.fromisoformat(season.start_date),
                    FinCashLine.date <= date.fromisoformat(season.end_date),
                ).order_by(FinCashLine.date, FinCashLine.id)
            )
        )
        withdrawals = {l.transfer_operation_id for l in cash_lines if l.transfer_operation_id is not None}

        # Lignes de banque : compte du plan (ou à classer) contre 512x.
        confirmed = self.accounting._lines(db, member.org_id)
        for r in rows:
            cents = round(r["amount"] * 100)
            if r.get("transfer"):
                # Virement interne : 512a → 512b (le débit porte la ligne).
                src = bank_numbers[r["accountId"]]
                dst = next((n for aid, n in bank_numbers.items() if n[1] == r["transfer"]["to"]), None)
                account(*src, "banque").lines.append(Line(r["date"], "BQ", r["label"], "", 0, cents))
                if dst:
                    account(*dst, "banque").lines.append(Line(r["date"], "BQ", r["label"], "", cents, 0))
                continue
            bank_number, bank_name = bank_numbers[r["accountId"]]
            journal = f"BQ{bank_number[-1]}"
            piece = r["piece"]["title"] if r.get("piece") else ""
            account(bank_number, bank_name, "banque").lines.append(Line(r["date"], journal, r["label"], piece, max(cents, 0), max(-cents, 0)))
            if r["id"] in withdrawals:
                account(CASH, "Caisse", "caisse").lines.append(Line(r["date"], journal, r["label"], "", -cents, 0))
                continue
            splits = confirmed.get(r["id"])
            parts = [(chart[l.account_id], l.amount) for l in splits] if splits else [(None, cents)]
            for acc_row, amount in parts:
                if acc_row is None:
                    number, label = UNCLASSIFIED[EXPENSE if amount < 0 else INCOME]
                    acc = account(number, label, EXPENSE if amount < 0 else INCOME)
                else:
                    acc = account(acc_row.number, acc_row.label, acc_row.nature, acc_row.event)
                acc.lines.append(Line(r["date"], journal, r["label"], piece, max(-amount, 0), max(amount, 0)))

        # Caisse : compte du plan contre 530 (un retrait est déjà passé par
        # la banque ci-dessus).
        for l in cash_lines:
            if l.transfer_operation_id is not None:
                continue
            day = l.date.isoformat()
            account(CASH, "Caisse", "caisse").lines.append(Line(day, "CA", l.label, "", max(l.amount, 0), max(-l.amount, 0)))
            acc_row = chart.get(l.account_id)
            if acc_row is None:
                number, label = UNCLASSIFIED[EXPENSE if l.amount < 0 else INCOME]
                acc = account(number, label, EXPENSE if l.amount < 0 else INCOME)
            else:
                acc = account(acc_row.number, acc_row.label, acc_row.nature, acc_row.event)
            acc.lines.append(Line(day, "CA", l.label, "", max(-l.amount, 0), max(l.amount, 0)))
        for acc in books.values():
            acc.lines.sort(key=lambda l: l.date)
        books["_cutoff"] = cutoff  # type: ignore[assignment]
        return books

    # ----- Synthèse -----

    def synthese(self, db: Session, member: Member, season: Season) -> dict:
        """La Synthèse à l'écran (forme du modèle Excel) : charges et produits
        par classe, totaux, résultat, trésorerie, fournisseurs à payer, un
        bloc par événement."""
        books = self.books(db, member, season)
        cutoff = books.pop("_cutoff")
        accounts = [a for a in books.values() if a.nature in (EXPENSE, INCOME)]

        def grouped(nature: str) -> list[dict]:
            classes: dict[str, list] = defaultdict(list)
            for a in sorted(accounts, key=lambda a: a.number):
                if a.nature == nature:
                    amount = a.balance if nature == EXPENSE else -a.balance
                    if amount:
                        classes[a.number[:2]].append({"number": a.number, "label": a.label, "amount": amount / 100})
            return [
                {"code": code, "label": CLASS_LABELS.get(code, "Autres"), "lines": lines, "total": round(sum(l["amount"] for l in lines), 2)}
                for code, lines in sorted(classes.items())
            ]

        charges, produits = grouped(EXPENSE), grouped(INCOME)
        total_charges = round(sum(c["total"] for c in charges), 2)
        total_produits = round(sum(p["total"] for p in produits), 2)
        treasury = [
            {"label": a.label, "amount": a.balance / 100} for a in sorted(books.values(), key=lambda a: a.number) if a.nature in ("banque", "caisse")
        ]
        unpaid = self.ports.unpaid(db, member.org_id) if self.ports.unpaid else []
        events: dict[str, dict] = {}
        for a in accounts:
            if a.event:
                e = events.setdefault(a.event, {"event": a.event, "resources": 0.0, "cost": 0.0})
                if a.nature == INCOME:
                    e["resources"] += -a.balance / 100
                else:
                    e["cost"] += a.balance / 100
        for e in events.values():
            e["profit"] = round(e["resources"] - e["cost"], 2)
        return {
            "season": season.name,
            "start": season.start_date,
            "end": season.end_date,
            "cutoff": cutoff,
            "charges": charges,
            "produits": produits,
            "totalCharges": total_charges,
            "totalProduits": total_produits,
            "result": round(total_produits - total_charges, 2),
            "treasury": treasury,
            "treasuryTotal": round(sum(t["amount"] for t in treasury), 2),
            "unpaid": unpaid,
            "unpaidTotal": round(sum(u["amount"] for u in unpaid), 2),
            "events": sorted(events.values(), key=lambda e: e["event"]),
            "unclassified": round(sum(a.balance for a in accounts if a.number == UNCLASSIFIED[EXPENSE][0]) / 100
                                  - sum(a.balance for a in accounts if a.number == UNCLASSIFIED[INCOME][0]) / 100, 2),
        }

    def synthese_xlsx(self, synthese: dict, org_name: str) -> bytes:
        bold = Font(bold=True)
        head = PatternFill("solid", fgColor="E9E3F5")
        money = '#,##0.00 "€";-#,##0.00 "€";""'
        wb = Workbook()
        ws = wb.active
        ws.title = "Synthèse"
        ws.append([f"{org_name} — Synthèse Dépenses-Recettes {synthese['season']}"])
        ws["A1"].font = Font(bold=True, size=14)
        ws.append([f"Du {_fr(synthese['start'])} au {_fr(synthese['cutoff'])}"])
        ws.append([])

        def block(title: str, groups: list[dict], total_label: str, total: float) -> None:
            ws.append([title])
            ws.cell(ws.max_row, 1).font, ws.cell(ws.max_row, 1).fill = bold, head
            for g in groups:
                ws.append([f"{g['code']} · {g['label']}"])
                ws.cell(ws.max_row, 1).font = bold
                for line in g["lines"]:
                    ws.append([f"{line['number']} {line['label']}", line["amount"]])
                    ws.cell(ws.max_row, 2).number_format = money
            ws.append([total_label, total])
            ws.cell(ws.max_row, 1).font = ws.cell(ws.max_row, 2).font = bold
            ws.cell(ws.max_row, 2).number_format = money
            ws.append([])

        block("CHARGES", synthese["charges"], "Total des charges", synthese["totalCharges"])
        block("PRODUITS", synthese["produits"], "Total des produits", synthese["totalProduits"])
        ws.append(["Déficit" if synthese["result"] < 0 else "Excédent", synthese["result"]])
        ws.cell(ws.max_row, 1).font = ws.cell(ws.max_row, 2).font = bold
        ws.cell(ws.max_row, 2).number_format = money
        ws.append([])
        ws.append([f"Trésorerie au {_fr(synthese['cutoff'])}"])
        ws.cell(ws.max_row, 1).font, ws.cell(ws.max_row, 1).fill = bold, head
        for t in synthese["treasury"]:
            ws.append([t["label"], t["amount"]])
            ws.cell(ws.max_row, 2).number_format = money
        ws.append(["Solde de trésorerie", synthese["treasuryTotal"]])
        ws.cell(ws.max_row, 1).font = ws.cell(ws.max_row, 2).font = bold
        ws.cell(ws.max_row, 2).number_format = money
        ws.append(["Fournisseurs à payer", synthese["unpaidTotal"]])
        ws.cell(ws.max_row, 2).number_format = money
        for e in synthese["events"]:
            ws.append([])
            ws.append([e["event"].capitalize()])
            ws.cell(ws.max_row, 1).font, ws.cell(ws.max_row, 1).fill = bold, head
            for label, key in (("Ressources", "resources"), ("Coût", "cost"), ("Bénéfice", "profit")):
                ws.append([f"{label} : {e['event']}", e[key]])
                ws.cell(ws.max_row, 2).number_format = money
        ws.column_dimensions["A"].width = 44
        ws.column_dimensions["B"].width = 16
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    # ----- Balance et Grand livre -----

    def balance_pdf(self, db: Session, member: Member, season: Season, org_name: str) -> bytes:
        books = self.books(db, member, season)
        cutoff = books.pop("_cutoff")
        e = html.escape
        rows, total_d, total_c = [], 0, 0
        for a in sorted(books.values(), key=lambda a: a.number):
            d, c = a.debit, a.credit
            total_d, total_c = total_d + d, total_c + c
            sd, sc = max(a.balance, 0), max(-a.balance, 0)
            rows.append(
                f"<tr><td>{e(a.number)}</td><td class='l'>{e(a.label)}</td><td>{_c(d)}</td><td>{_c(c)}</td><td>{_c(sd)}</td><td>{_c(sc)}</td></tr>"
            )
        result = sum(a.balance for a in books.values() if a.nature in (EXPENSE, INCOME))
        body = (
            f"<h1>{e(org_name)} — Balance {e(season.name)}</h1>"
            f"<p class='muted'>Du {_fr(season.start_date)} au {_fr(cutoff)}. Comptabilité de trésorerie : "
            "chaque ligne de banque et de caisse contre son compte du plan.</p>"
            "<table><tr><th>Compte</th><th class='l'>Libellé</th><th>Débit</th><th>Crédit</th><th>Solde débiteur</th><th>Solde créditeur</th></tr>"
            + "".join(rows)
            + f"<tr class='total'><td></td><td class='l'>Totaux</td><td>{_c(total_d)}</td><td>{_c(total_c)}</td><td></td><td></td></tr></table>"
            f"<h2>{'Déficit' if result > 0 else 'Excédent'} de la saison : {_c(abs(result))}</h2>"
        )
        return html_to_pdf(body, _CSS + " th.l, td.l { text-align: left; }")

    def grand_livre_pdf(self, db: Session, member: Member, season: Season, org_name: str) -> bytes:
        books = self.books(db, member, season)
        cutoff = books.pop("_cutoff")
        e = html.escape
        parts = [
            f"<h1>{e(org_name)} — Grand livre {e(season.name)}</h1>",
            f"<p class='muted'>Du {_fr(season.start_date)} au {_fr(cutoff)}. Journaux : AN à-nouveaux, BQn banque, CA caisse.</p>",
        ]
        total_d = total_c = 0
        for a in sorted(books.values(), key=lambda a: a.number):
            running = 0
            lines = []
            for l in a.lines:
                running += l.debit - l.credit
                lines.append(
                    f"<tr><td>{_fr(l.date)}</td><td>{e(l.journal)}</td><td class='l'>{e(l.piece)}</td><td class='l'>{e(l.label)}</td>"
                    f"<td>{_c(l.debit)}</td><td>{_c(l.credit)}</td><td>{_signed(running)}</td></tr>"
                )
            total_d, total_c = total_d + a.debit, total_c + a.credit
            parts.append(
                f"<h2>{e(a.number)} {e(a.label)}</h2><table class='small'>"
                "<tr><th>Date</th><th>Journal</th><th class='l'>Pièce</th><th class='l'>Libellé</th><th>Débit</th><th>Crédit</th><th>Solde</th></tr>"
                + "".join(lines)
                + f"<tr class='total'><td></td><td></td><td></td><td class='l'>Total du compte</td><td>{_c(a.debit)}</td><td>{_c(a.credit)}</td><td>{_signed(a.balance)}</td></tr></table>"
            )
        parts.append(f"<h2>Total général : débit {_c(total_d)}, crédit {_c(total_c)}</h2>")
        return html_to_pdf("".join(parts), _CSS + " th.l, td.l { text-align: left; }")

    # ----- Honoraires par professeur -----

    def fees_xlsx(self, db: Session, member: Member, season: Season, org_name: str) -> bytes:
        fees = self.ports.fees(db, member.org_id, season.start_date, season.end_date) if self.ports.fees else []
        months = sorted({f["month"] for f in fees})
        by_person: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        for f in fees:
            by_person[f["person"]][f["month"]] += f["amount"]
        bold = Font(bold=True)
        money = '#,##0.00 "€";-#,##0.00 "€";""'
        wb = Workbook()
        ws = wb.active
        ws.title = "Honoraires"
        ws.append([f"{org_name} — Honoraires par professeur {season.name} (DAS-2)"])
        ws["A1"].font = Font(bold=True, size=14)
        ws.append(["Professeur", *months, "Total"])
        for cell in ws[2]:
            cell.font = bold
        for person in sorted(by_person):
            amounts = [by_person[person].get(m, 0.0) for m in months]
            ws.append([person, *amounts, round(sum(amounts), 2)])
            for col in range(2, len(months) + 3):
                ws.cell(ws.max_row, col).number_format = money
        ws.append(["Total", *[round(sum(by_person[p].get(m, 0.0) for p in by_person), 2) for m in months], round(sum(f["amount"] for f in fees), 2)])
        for cell in ws[ws.max_row]:
            cell.font = bold
        for col in range(2, len(months) + 3):
            ws.cell(ws.max_row, col).number_format = money
        ws.column_dimensions["A"].width = 30
        buffer = io.BytesIO()
        wb.save(buffer)
        return buffer.getvalue()

    # ----- production et rangement -----

    def produce(self, db: Session, member: Member, season: Season, kind: str) -> tuple[bytes, str, str]:
        """(contenu, nom de fichier, type) d'un document ; rangé dans Docs ›
        Financier › AG si l'appli le permet."""
        if kind not in KINDS:
            raise ValueError("Document inconnu")
        title, extension, _ = KINDS[kind]
        org_name = self.ports.org_name(db, member.org_id) if self.ports.org_name else ""
        if kind == "synthese":
            content = self.synthese_xlsx(self.synthese(db, member, season), org_name)
        elif kind == "balance":
            content = self.balance_pdf(db, member, season, org_name)
        elif kind == "grand-livre":
            content = self.grand_livre_pdf(db, member, season, org_name)
        else:
            content = self.fees_xlsx(db, member, season, org_name)
        name = f"{title} {season.name}.{extension}"
        media = "application/pdf" if extension == "pdf" else "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if self.ports.store is not None:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / name
                path.write_bytes(content)
                self.ports.store(db, member, ["AG"], [(name, path)])
        return content, name, media

    @staticmethod
    def kinds(level: str) -> list[dict]:
        """Les documents du niveau (Simple : Synthèse ; Complet : tous)."""
        return [
            {"id": key, "title": title, "format": extension, "level": needed}
            for key, (title, extension, needed) in KINDS.items()
            if level == "complet" or needed == "simple"
        ]


def _c(cents: int) -> str:
    return "" if not cents else _eur(cents / 100)


def _signed(cents: int) -> str:
    return _eur(cents / 100) if cents else ""
