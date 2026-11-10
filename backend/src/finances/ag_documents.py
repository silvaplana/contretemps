"""Documents de l'AG (spec/modules/financier.md §8.6) : Synthèse
Dépenses-Recettes, Balance, Grand livre, Honoraires par professeur, calculés
au centime depuis les lignes de banque (compte du plan confirmé, voir
accounting.py) et la caisse, pour la saison d'un bilan. Jamais un chiffre
écrit par un modèle : des additions.

Comptabilité de trésorerie : chaque ligne de banque est une écriture à deux
lignes (compte du plan contre 512x la banque, 530 la caisse) ; les soldes de
départ des comptes de trésorerie sont repris dans 110 « Report à nouveau »
pour que la Balance soit équilibrée.

Niveau Complet (partie double, §8.7) : une ligne de banque qui a une pièce
passe par le tiers (achat du jour de la facture 6xx contre 401, honoraires et
notes de frais contre 467x ; paiement 401 contre 512x, même lettre) ; les
soldes de départ viennent de la saisie du trésorier (fin_opening_balances)
ou de la clôture de la saison précédente (fin_closings), sinon de la
trésorerie des relevés. Les écritures ne sont pas stockées : elles sont
recalculées depuis les lignes de banque, de caisse et les pièces, donc
toujours justes ; la clôture fige le résultat et les soldes reportés.

Une ligne sans compte confirmé va dans « À classer » (dépense ou recette
selon le sens) plutôt que d'être inventée.
"""

from __future__ import annotations

import html
import io
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
from sqlalchemy import select
from sqlalchemy.orm import Session

from .accounting import Accounting
from .exports import _CSS, _eur, _fr, html_to_pdf
from .chart import is_cheque_deposit
from .models import EXPENSE, FULL, INCOME, THIRD_PARTY, FinCashLine, FinClosing, FinManualEntry, FinOpeningBalance, FinSeasonNote
from .ports import Member, Season

# Numéros des comptes de trésorerie et de report (plan associatif).
BANK_BASE = "512"
CASH = "530"
CARRY_FORWARD = "110"
# Compte de tiers par nature de pièce (préfixe du plan associatif).
THIRD_PARTY_PREFIX = {"achat": "401", "honoraires": "467", "frais": "467"}
FEE_PREFIX = "467"
THIRD_PARTY_JOURNAL = {"achat": "AC", "honoraires": "HO", "frais": "NF"}
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
    "bilan": ("Bilan actif-passif", "pdf", "complet"),
    "honoraires": ("Honoraires par professeur", "xlsx", "complet"),
    "fec": ("FEC", "txt", "simple"),
}

# Fichier des écritures comptables (article A47 A-1 du livre des procédures
# fiscales) : 18 colonnes séparées par une tabulation, dates AAAAMMJJ,
# montants à virgule.
FEC_COLUMNS = [
    "JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum", "CompteLib", "CompAuxNum", "CompAuxLib",
    "PieceRef", "PieceDate", "EcritureLib", "Debit", "Credit", "EcritureLet", "DateLet", "ValidDate", "Montantdevise", "Idevise",
]
JOURNALS = {"AN": "A-nouveaux", "BQ": "Banque", "CA": "Caisse", "AC": "Achats", "HO": "Honoraires", "NF": "Notes de frais", "OD": "Opérations diverses"}
# Mise en page des états comptables (Grand livre, Balance) : bandeau, titre
# centré, bloc par compte, totaux en gras ; sobre, le nom de l'association seul.
_REPORT_CSS = """
th.l, td.l { text-align: left; } th.c { text-align: center; }
table.bandeau { border: 1px solid #8a6; background: #eef7ee; }
table.bandeau td { border: 0; padding: 4pt 6pt; text-align: left; }
table.bandeau .org { font-size: 13pt; font-weight: bold; color: #264; }
td.edition { text-align: right !important; color: #666; }
h1.titre { text-align: center; font-size: 14pt; margin: 8pt 0 4pt; }
h1.titre .periode { font-size: 12pt; font-weight: bold; }
table.ligne td { border: 0; font-weight: bold; padding: 2pt 0 8pt; text-align: left; }
table.ligne td.edition { color: #222; }
table.compte { margin-top: 6pt; table-layout: fixed; }
tr.compte th { background: #f3e2cf; font-size: 8pt; padding: 2pt 3pt; }
tr.total.grand td { font-size: 10pt; border-top: 2px solid #333; border-bottom: 2px solid #333; padding: 4pt 3pt; }
"""
# Le cadenas de la colonne Type du Grand livre (écriture validée), en SVG : pas d'emoji dans le PDF.
_PADLOCK = (
    "<svg width='9' height='11' viewBox='0 0 24 28' aria-label='validée'><rect x='3' y='12' width='18' height='14' rx='2' fill='#333'/>"
    "<path d='M7 12V8a5 5 0 0 1 10 0v4' fill='none' stroke='#333' stroke-width='3'/></svg>"
)


@dataclass
class AgPorts:
    """Ce que l'appli hôte fournit : les pièces à payer (fournisseurs,
    Synthèse), les honoraires payés par prof et par mois (DAS-2), et le
    rangement d'un fichier dans Docs › Financier › AG (ids des fichiers)."""

    unpaid: Callable[[Session, int], list[dict]] | None = None
    fees: Callable[[Session, int, str, str], list[dict]] | None = None
    store: Callable[[Session, Member, list[str], list[tuple[str, Path]]], list[int]] | None = None
    folder: Callable[[Session, Member], int | None] | None = None  # le dossier AG de Docs, pour l'ouvrir
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
    letter: str = ""
    operation_id: int | None = None


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

    def books(self, db: Session, member: Member, season: Season, full: bool | None = None) -> dict[str, Account]:
        """Tous les comptes mouvementés sur la saison, avec leurs lignes, les
        soldes de départ et le report à nouveau. full : partie double (par
        défaut selon le niveau de l'organisation)."""
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

        if full is None:
            full = self.accounting.level(db, member.org_id) == FULL
        opening_total = 0
        all_rows = list(reversed(ledger["rows"]))
        entered = self._opening_lines(db, member.org_id, season) if full else None
        if entered is not None:
            for number, label, nature, balance in entered:
                account(number, label, nature).lines.append(
                    Line(season.start_date, "AN", "Solde au début de la saison", "", max(balance, 0), max(-balance, 0))
                )
            bank_numbers_for_opening = {}
        else:
            bank_numbers_for_opening = bank_numbers
        for aid, (number, name) in bank_numbers_for_opening.items():
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
        ) if entered is None else 0
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

        # Lignes de banque : compte du plan (ou à classer) contre 512x ; en
        # Complet, une ligne avec pièce passe par le tiers, avec une lettre.
        confirmed = self.accounting._lines(db, member.org_id)
        if full:
            unpaid = list(self.ports.unpaid(db, member.org_id)) if self.ports.unpaid else []
            if self._create_fee_accounts(db, member, [r["piece"] for r in rows if r.get("piece")] + unpaid, chart.values()):
                chart = {a.id: a for a in self.accounting.accounts(db, member.org_id)}
        third_parties = [a for a in chart.values() if a.nature == THIRD_PARTY and a.active] if full else []
        letters: dict[str, int] = defaultdict(int)
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
            # Colonne Pièce : le numéro donné à la validation (AC-2025-001), sinon le titre de la pièce.
            piece = (r["piece"].get("number") or r["piece"]["title"]) if r.get("piece") else ""
            account(bank_number, bank_name, "banque").lines.append(
                Line(r["date"], journal, r["label"], piece, max(cents, 0), max(-cents, 0), operation_id=r["id"])
            )
            if r["id"] in withdrawals:
                account(CASH, "Caisse", "caisse").lines.append(Line(r["date"], journal, r["label"], "", -cents, 0, operation_id=r["id"]))
                continue
            splits = confirmed.get(r["id"])
            parts = [(chart[l.account_id], l.amount) for l in splits] if splits else [(None, cents)]
            third = _third_party(third_parties, r.get("piece")) if cents < 0 and splits else None
            if third is not None:
                # Achat du jour de la facture : 6xx contre le tiers, au montant de
                # la facture ; paiement : tiers contre 512x, au montant de la
                # banque. Même montant : lettrés ; sinon (acompte, écart à
                # régler) les deux lignes restent ouvertes sur le tiers (§8.7).
                invoice = round(float(r["piece"].get("amount") or 0) * 100) or -cents
                letter = ""
                if invoice == -cents:
                    letters[third.number] += 1
                    letter = _letter(letters[third.number])
                day = max(r["piece"]["date"], season.start_date) if r["piece"].get("date") else r["date"]
                buy = THIRD_PARTY_JOURNAL[r["piece"]["nature"]]
                tiers = account(third.number, third.label, THIRD_PARTY)
                tiers.lines.append(Line(day, buy, r["piece"]["title"], piece, 0, invoice, letter, r["id"]))
                tiers.lines.append(Line(r["date"], journal, r["label"], piece, -cents, 0, letter, r["id"]))
                # La charge au montant de la facture, répartie comme la banque l'a été.
                for acc_row, amount in parts:
                    share = round(amount * invoice / -cents) if cents else -invoice
                    acc = account(acc_row.number, acc_row.label, acc_row.nature, acc_row.event)
                    acc.lines.append(Line(day, buy, r["piece"]["title"], piece, -share, 0, operation_id=r["id"]))
                continue
            for acc_row, amount in parts:
                if acc_row is None:
                    number, label = UNCLASSIFIED[EXPENSE if amount < 0 else INCOME]
                    acc = account(number, label, EXPENSE if amount < 0 else INCOME)
                else:
                    acc = account(acc_row.number, acc_row.label, acc_row.nature, acc_row.event)
                acc.lines.append(Line(r["date"], journal, r["label"], piece, max(-amount, 0), max(amount, 0), operation_id=r["id"]))

        # Complet : les factures validées pas encore payées, datées de la saison,
        # entrent en charge le jour de la facture contre leur tiers (401 / 467x),
        # sans lettre : elles sont dues au dernier jour de la saison (§8.10, étape 4).
        if full and self.ports.unpaid:
            by_number = {a.number: a for a in chart.values() if a.active}
            for u in unpaid:
                day = u.get("date")
                if not day or not (season.start_date <= day <= season.end_date):
                    continue
                third = _third_party(third_parties, u)
                if third is None:
                    continue
                cents = round(u["amount"] * 100)
                charge = by_number.get(u.get("account") or "")
                if charge is None or charge.nature != EXPENSE:
                    number, label = UNCLASSIFIED[EXPENSE]
                    acc = account(number, label, EXPENSE)
                else:
                    acc = account(charge.number, charge.label, charge.nature, charge.event)
                journal = THIRD_PARTY_JOURNAL[u["nature"]]
                ref = u.get("number") or u["title"]
                acc.lines.append(Line(day, journal, u["title"], ref, cents, 0))
                account(third.number, third.label, THIRD_PARTY).lines.append(Line(day, journal, u["title"], ref, 0, cents))

        # Complet : les écritures saisies à la main (journal OD, §8.10 étape 4).
        if full:
            for e in self._manual_entries(db, member.org_id, season):
                debit, credit = chart.get(e.debit_account_id), chart.get(e.credit_account_id)
                if debit is None or credit is None:
                    continue
                day = e.date.isoformat()
                account(debit.number, debit.label, debit.nature, debit.event).lines.append(Line(day, "OD", e.label, "", e.amount, 0))
                account(credit.number, credit.label, credit.nature, credit.event).lines.append(Line(day, "OD", e.label, "", 0, e.amount))

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

    # ----- soldes de départ et clôture (Complet, §8.7) -----

    def _previous(self, db: Session, org_id: int, season: Season) -> Season | None:
        seasons = sorted(self.seasons(db, org_id), key=lambda s: s.start_date)
        index = next((i for i, s in enumerate(seasons) if s.id == season.id), None)
        return seasons[index - 1] if index else None

    def closing(self, db: Session, org_id: int, season_id: int) -> FinClosing | None:
        """La clôture en vigueur d'une saison (pas rouverte)."""
        return db.scalar(
            select(FinClosing).where(FinClosing.org_id == org_id, FinClosing.season_id == season_id, FinClosing.reopened_at.is_(None))
        )

    def _create_fee_accounts(self, db: Session, member: Member, pieces: list[dict], accounts) -> bool:
        """Un prof sans compte d'honoraires (Seb, 10/11) : à sa première facture,
        l'appli crée « 467n Honoraires Nom » (prochain numéro libre) plutôt que
        de le ranger chez un autre prof. Rend True si un compte a été créé."""
        fee_accounts = [a for a in accounts if a.number.startswith(FEE_PREFIX)]
        taken = {a.number for a in accounts}
        created = False
        for piece in pieces:
            person = str(piece.get("person") or "").strip()
            if piece.get("nature") != "honoraires" or not person:
                continue
            if _third_party(fee_accounts, piece) is not None and any(_named(a, person) for a in fee_accounts):
                continue
            n = 1
            while f"{FEE_PREFIX}{n}" in taken:
                n += 1
            number = f"{FEE_PREFIX}{n}"
            new = self.accounting.create_account(db, member, {"number": number, "label": f"Honoraires {person}", "nature": THIRD_PARTY})
            fee_accounts.append(SimpleNamespace(number=number, label=new["label"], nature=THIRD_PARTY, active=True))
            taken.add(number)
            created = True
        return created

    def _opening_lines(self, db: Session, org_id: int, season: Season) -> list[tuple[str, str, str, int]] | None:
        """Les soldes de départ (numéro, libellé, nature, solde signé) :
        saisis par le trésorier, sinon reportés de la clôture précédente,
        sinon None (trésorerie des relevés). Toujours équilibrés par 110."""
        entered = list(
            db.scalars(select(FinOpeningBalance).where(FinOpeningBalance.org_id == org_id, FinOpeningBalance.season_id == season.id))
        )
        if entered:
            lines = [(b.number, b.label, _nature_of(b.number, db, self.accounting, org_id), b.balance) for b in entered]
        else:
            previous = self._previous(db, org_id, season)
            closing = self.closing(db, org_id, previous.id) if previous else None
            if closing is None:
                return None
            lines = [(b["number"], b["label"], b["nature"], b["balance"]) for b in closing.balances]
        lines = [l for l in lines if l[3]]
        gap = sum(l[3] for l in lines)
        if gap:
            lines = [l for l in lines if l[0] != CARRY_FORWARD]
            carried = next((l[3] for l in lines if l[0] == CARRY_FORWARD), 0)
            lines.append((CARRY_FORWARD, "Report à nouveau", "report", carried - gap))
        return lines

    def opening(self, db: Session, member: Member, season: Season) -> dict:
        """Les soldes de départ à l'écran : d'où ils viennent, un solde par
        compte du bilan (en euros), et la vérification des 512x contre les
        relevés."""
        entered = self._opening_lines(db, member.org_id, season)
        source = "saisie" if db.scalar(
            select(FinOpeningBalance.id).where(FinOpeningBalance.org_id == member.org_id, FinOpeningBalance.season_id == season.id)
        ) else ("cloture" if entered is not None else "releves")
        # Trésorerie des relevés au début de la saison : sans soldes saisis,
        # c'est ce que books() prend ; sinon la référence de la vérification.
        statements = self._statement_opening(db, member, season)
        if entered is None:
            lines = [(n, label, nature, balance) for n, (label, nature, balance) in statements.items()]
            total = sum(l[3] for l in lines)
            if total:
                lines.append((CARRY_FORWARD, "Report à nouveau", "report", -total))
        else:
            lines = entered
        by_number = {l[0]: l for l in lines}
        for a in self.accounting.accounts(db, member.org_id, active_only=True):
            if a.nature == THIRD_PARTY or a.number.startswith("47"):
                by_number.setdefault(a.number, (a.number, a.label, a.nature, 0))
        for number, (label, nature, _) in statements.items():
            by_number.setdefault(number, (number, label, nature, 0))
        by_number.setdefault(CARRY_FORWARD, (CARRY_FORWARD, "Report à nouveau", "report", 0))
        accounts = [
            {"number": n, "label": label, "nature": nature, "balance": balance / 100}
            for n, label, nature, balance in sorted(by_number.values(), key=lambda l: l[0])
        ]
        check = [
            {"number": n, "label": label, "statements": balance / 100, "entered": by_number.get(n, (0, 0, 0, 0))[3] / 100}
            for n, (label, _, balance) in statements.items()
        ]
        return {"season": season.name, "source": source, "accounts": accounts, "bankCheck": check, "closed": self.closing(db, member.org_id, season.id) is not None}

    def _statement_opening(self, db: Session, member: Member, season: Season) -> dict[str, tuple[str, str, int]]:
        """Trésorerie des relevés et de la caisse à la veille de la saison :
        {numéro: (libellé, nature, centimes)}, comme books() sans saisie."""
        books = self.books(db, member, season, full=False)
        out = {}
        for a in books.values():
            if isinstance(a, Account) and a.nature in ("banque", "caisse"):
                opening = sum(l.debit - l.credit for l in a.lines if l.journal == "AN")
                out[a.number] = (a.label, a.nature, opening)
        return out

    def set_opening(self, db: Session, member: Member, season: Season, accounts: list[dict]) -> dict:
        """« Reprendre ces soldes » : les soldes de départ saisis (euros,
        positif = débiteur) ; la différence va dans 110."""
        if not member.is_treasurer:
            raise PermissionError("Réservé au trésorier")
        if self.closing(db, member.org_id, season.id) is not None:
            raise ValueError("Saison clôturée : rouvrez-la d'abord.")
        for old in db.scalars(select(FinOpeningBalance).where(FinOpeningBalance.org_id == member.org_id, FinOpeningBalance.season_id == season.id)):
            db.delete(old)
        for a in accounts:
            number = str(a.get("number", "")).strip()
            balance = round(float(a.get("balance", 0) or 0) * 100)
            if not number or not balance:
                continue
            db.add(FinOpeningBalance(org_id=member.org_id, season_id=season.id, number=number[:10], label=str(a.get("label", ""))[:80], balance=balance, created_by=member.person_id))
        db.commit()
        return self.opening(db, member, season)

    def close(self, db: Session, member: Member, season: Season) -> dict:
        """Clôture (§8.7) : le résultat va dans 110, les soldes des comptes de
        bilan sont reportés sur la saison suivante, la saison est verrouillée."""
        if not member.is_treasurer:
            raise PermissionError("Réservé au trésorier")
        if self.accounting.level(db, member.org_id) != FULL:
            raise ValueError("La clôture est au niveau Complet (Comptes › ⋯ › Plan comptable).")
        if self.closing(db, member.org_id, season.id) is not None:
            raise ValueError("Saison déjà clôturée.")
        books = self.books(db, member, season)
        books.pop("_cutoff")
        result = sum(a.balance for a in books.values() if a.nature in (EXPENSE, INCOME))
        balances = {a.number: {"number": a.number, "label": a.label, "nature": a.nature, "balance": a.balance} for a in books.values() if a.nature not in (EXPENSE, INCOME)}
        carry = balances.setdefault(CARRY_FORWARD, {"number": CARRY_FORWARD, "label": "Report à nouveau", "nature": "report", "balance": 0})
        carry["balance"] += result
        db.add(
            FinClosing(
                org_id=member.org_id, season_id=season.id, start_date=date.fromisoformat(season.start_date), end_date=date.fromisoformat(season.end_date),
                result=result, balances=[b for b in sorted(balances.values(), key=lambda b: b["number"]) if b["balance"]], closed_by=member.person_id,
            )
        )
        db.commit()
        return self.closing_status(db, member.org_id, season)

    def reopen(self, db: Session, member: Member, season: Season) -> dict:
        if not member.is_treasurer:
            raise PermissionError("Réservé au trésorier")
        closing = self.closing(db, member.org_id, season.id)
        if closing is None:
            raise ValueError("Saison pas clôturée.")
        closing.reopened_by, closing.reopened_at = member.person_id, datetime.now(timezone.utc).replace(tzinfo=None)
        db.commit()
        return self.closing_status(db, member.org_id, season)

    def closing_status(self, db: Session, org_id: int, season: Season) -> dict | None:
        closing = self.closing(db, org_id, season.id)
        if closing is None:
            return None
        return {"closedAt": closing.closed_at.isoformat(timespec="seconds"), "result": closing.result / 100}

    def closing_history(self, db: Session, org_id: int, season: Season) -> list[dict]:
        """Les clôtures rouvertes de la saison (§8.7, trace gardée) : clôturée le…, rouverte le…"""
        rows = db.scalars(
            select(FinClosing).where(FinClosing.org_id == org_id, FinClosing.season_id == season.id, FinClosing.reopened_at.is_not(None)).order_by(FinClosing.closed_at)
        )
        return [{"closedAt": c.closed_at.isoformat(timespec="seconds"), "reopenedAt": c.reopened_at.isoformat(timespec="seconds")} for c in rows]

    def operation_entries(self, db: Session, member: Member, operation_id: int, day: str) -> list[dict]:
        """Les écritures générées pour une opération (fiche, §8.4) : une
        ligne par compte mouvementé."""
        season = next((s for s in self.seasons(db, member.org_id) if s.start_date <= day <= s.end_date), None)
        if season is None:
            return []
        books = self.books(db, member, season)
        books.pop("_cutoff")
        entries = []
        for a in sorted(books.values(), key=lambda a: a.number):
            for l in a.lines:
                if l.operation_id == operation_id:
                    entries.append({"date": l.date, "journal": l.journal, "account": f"{a.number} {a.label}", "label": l.label, "debit": l.debit / 100, "credit": l.credit / 100, "letter": l.letter})
        entries.sort(key=lambda e: (e["date"], e["journal"]))
        return entries

    # ----- Le bilan en parcours (financier.md §8.10) -----

    def preparation(self, db: Session, member: Member, season: Season, calendar: dict | None = None) -> dict:
        """L'état des six étapes de Préparer pour une saison : relevés complets
        (`calendar` : la grille statement_calendar de la saison), soldes de
        départ, un compte sur chaque transaction bancaire (à confirmer une par
        une quand l'appli ne propose rien, sinon regroupées par compte proposé
        pour « Valider le compte »), hors banque (pas encore), contrôles,
        documents. Rien n'est écrit."""
        if not member.keeps_accounts:
            raise PermissionError("Réservé aux trésoriers")
        # 1. Relevés.
        cells = [m for a in (calendar or {}).get("accounts", []) for m in a["months"]]
        missing = sum(m["state"] in ("missing", "before", "bank") for m in cells)
        waiting = sum(m["state"] == "waiting" for m in cells)
        statements = {"missing": missing, "waiting": waiting, "accounts": len((calendar or {}).get("accounts", [])), "ok": missing == 0}
        # 2. Soldes de départ.
        opening = self.opening(db, member, season)
        mismatches = [c for c in opening["bankCheck"] if round(c["statements"] - c["entered"], 2) != 0]
        opening_step = {"source": opening["source"], "mismatches": len(mismatches), "ok": not mismatches}
        # 3. Un compte sur chaque transaction bancaire.
        rows = [r for r in self.ledger(db, member)["rows"] if season.start_date <= r["date"] <= season.end_date and not r.get("transfer")]
        self.accounting.annotate(db, member.org_id, rows)
        unsure, by_account = [], {}
        for r in rows:
            if r["account"] is not None:
                continue
            cheque = is_cheque_deposit(r["label"], r.get("details", ""))
            line = {"id": r["id"], "date": r["date"], "label": r["label"], "amount": r["amount"], "piece": r.get("piece"), "chequeDeposit": cheque}
            if r["proposal"] is None or cheque:
                # Une remise de chèques n'est jamais « sûre » : la banque ne dit
                # pas ce que payent les chèques, le trésorier la ventile.
                unsure.append(line)
            else:
                group = by_account.setdefault(r["proposal"]["id"], {"account": {k: r["proposal"][k] for k in ("id", "number", "label")}, "operations": []})
                group["operations"].append({**line, "reason": r["proposal"]["reason"]})
        sure = sorted(by_account.values(), key=lambda g: g["account"]["number"])
        classify = {"withoutAccount": len(unsure) + sum(len(g["operations"]) for g in sure), "unsure": unsure, "sure": sure, "ok": not unsure and not sure}
        # 5. Contrôles, en clair.
        fec = self.fec_check(db, member, season)
        controls = [
            {"label": "Relevés complets sur la saison", "ok": statements["ok"], "detail": "" if statements["ok"] else f"{missing} mois à importer"},
            {"label": "Soldes de départ égaux aux relevés", "ok": opening_step["ok"], "detail": "" if opening_step["ok"] else f"{len(mismatches)} compte(s) en écart"},
            {"label": "Un compte du plan sur chaque transaction bancaire", "ok": classify["ok"], "detail": "" if classify["ok"] else f"{classify['withoutAccount']} transaction(s) sans compte"},
            {"label": "FEC juste", "ok": fec["ok"], "detail": "" if fec["ok"] else " ".join(fec["problems"])},
        ]
        # 4. Hors banque : caisse, factures non payées (401 / 467x au niveau Complet).
        level = self.accounting.level(db, member.org_id)
        cash = self.accounting.cash(db, member)
        unpaid = self.ports.unpaid(db, member.org_id) if self.ports.unpaid else []
        unpaid = [u for u in unpaid if not u.get("date") or u["date"] <= season.end_date]
        off_bank = {
            "cash": cash["balance"], "cashLines": len(cash["lines"]),
            "unpaid": unpaid, "unpaidTotal": round(sum(u["amount"] for u in unpaid), 2),
            "unpaidInBooks": level == FULL,
            "entries": self.manual_entries(db, member, season),
        }
        # 6. Comparaison avec la saison précédente, compte par compte.
        comparison = self.comparison(db, member, season)
        controls.append({
            "label": "Écarts avec la saison précédente expliqués", "ok": not comparison["unexplained"],
            "detail": "" if not comparison["unexplained"] else f"{comparison['unexplained']} compte(s) marqué(s) « ? »",
        })
        return {
            "season": {"id": season.id, "name": season.name, "startDate": season.start_date, "endDate": season.end_date},
            "level": level,
            "statements": statements,
            "opening": opening_step,
            "classify": classify,
            "offBank": off_bank,
            "controls": controls,
            "comparison": comparison,
            "closed": opening["closed"],
        }

    # ----- Écritures à la main (journal OD, §8.10 étape 4) -----

    def _manual_entries(self, db: Session, org_id: int, season: Season) -> list[FinManualEntry]:
        return list(db.scalars(
            select(FinManualEntry).where(FinManualEntry.org_id == org_id, FinManualEntry.season_id == season.id)
            .order_by(FinManualEntry.date, FinManualEntry.id)
        ))

    def manual_entries(self, db: Session, member: Member, season: Season) -> list[dict]:
        """Les écritures à la main de la saison, à l'écran (montants en euros)."""
        if not member.keeps_accounts:
            raise PermissionError("Réservé aux trésoriers")
        chart = {a.id: a for a in self.accounting.accounts(db, member.org_id)}

        def acc(account_id: int) -> dict:
            a = chart.get(account_id)
            return {"id": account_id, "number": a.number if a else "?", "label": a.label if a else ""}

        return [
            {"id": e.id, "date": e.date.isoformat(), "label": e.label, "debit": acc(e.debit_account_id), "credit": acc(e.credit_account_id), "amount": e.amount / 100}
            for e in self._manual_entries(db, member.org_id, season)
        ]

    def add_manual_entry(self, db: Session, member: Member, season: Season, data: dict) -> list[dict]:
        """Une écriture OD : date dans la saison, libellé, compte débité, compte
        crédité (deux comptes actifs du plan, ni banque ni caisse : ceux-là
        passent par les relevés et la caisse), montant positif. Niveau Complet."""
        if not member.is_treasurer:
            raise PermissionError("Réservé au trésorier")
        if self.accounting.level(db, member.org_id) != FULL:
            raise ValueError("Les écritures à la main sont au niveau Complet (Comptes › ⋯ › Plan comptable).")
        if self.closing(db, member.org_id, season.id) is not None:
            raise ValueError("Saison clôturée : rouvrez-la d'abord.")
        try:
            day = date.fromisoformat(str(data.get("date", "")))
        except ValueError as exc:
            raise ValueError("Date invalide.") from exc
        if not (season.start_date <= day.isoformat() <= season.end_date):
            raise ValueError(f"La date doit être dans la saison {season.name}.")
        label = " ".join(str(data.get("label", "")).split())[:120]
        if not label:
            raise ValueError("Donnez un libellé à l'écriture.")
        amount = round(float(data.get("amount", 0) or 0) * 100)
        if amount <= 0:
            raise ValueError("Le montant doit être positif : le sens est donné par les comptes débité et crédité.")
        active = {a.id: a for a in self.accounting.accounts(db, member.org_id, active_only=True)}
        accounts = []
        for key in ("debitAccountId", "creditAccountId"):
            a = active.get(int(data.get(key) or 0))
            if a is None:
                raise ValueError("Compte inconnu ou inactif.")
            if a.nature in ("banque", "caisse"):
                raise ValueError("La banque et la caisse ne se saisissent pas à la main : relevés et Comptes › Caisse.")
            accounts.append(a)
        if accounts[0].id == accounts[1].id:
            raise ValueError("Le compte débité et le compte crédité doivent être différents.")
        db.add(FinManualEntry(
            org_id=member.org_id, season_id=season.id, date=day, label=label,
            debit_account_id=accounts[0].id, credit_account_id=accounts[1].id, amount=amount, created_by=member.person_id,
        ))
        db.commit()
        return self.manual_entries(db, member, season)

    def delete_manual_entry(self, db: Session, member: Member, entry_id: int) -> None:
        if not member.is_treasurer:
            raise PermissionError("Réservé au trésorier")
        entry = db.scalar(select(FinManualEntry).where(FinManualEntry.id == entry_id, FinManualEntry.org_id == member.org_id))
        if entry is None:
            raise LookupError("Écriture inconnue.")
        season = next((s for s in self.seasons(db, member.org_id) if s.id == entry.season_id), None)
        if season is not None and self.closing(db, member.org_id, season.id) is not None:
            raise ValueError("Saison clôturée : rouvrez-la d'abord.")
        db.delete(entry)
        db.commit()

    # Au-delà de cet écart (en %), un compte est marqué « ? » jusqu'à son explication.
    FLAG_PCT = 30

    def comparison(self, db: Session, member: Member, season: Season) -> dict:
        """Compte par compte, la saison et la précédente (Synthèse) : montant,
        écart, % ; « ? » (flag) quand l'écart dépasse FLAG_PCT ou que le compte
        apparaît ou disparaît, tant que la trésorière ne l'a pas expliqué en
        une ligne (fin_season_notes)."""
        previous = self._previous(db, member.org_id, season)
        current = self.synthese(db, member, season)
        before = self.synthese(db, member, previous) if previous is not None else None
        notes = {n.number: n.note for n in db.scalars(select(FinSeasonNote).where(FinSeasonNote.org_id == member.org_id, FinSeasonNote.season_id == season.id))}

        def lines(synthese: dict | None, side: str) -> dict[str, dict]:
            return {l["number"]: l for group in (synthese or {}).get(side, []) for l in group["lines"]}

        out = []
        for side in ("produits", "charges"):
            now, old = lines(current, side), lines(before, side)
            for number in sorted(set(now) | set(old)):
                a, b = now.get(number, {}).get("amount", 0.0), old.get(number, {}).get("amount", 0.0)
                label = (now.get(number) or old.get(number))["label"]
                delta = round(a - b, 2)
                pct = round(delta / abs(b) * 100, 1) if b else None
                flag = before is not None and ((pct is None and abs(delta) > 0) or (pct is not None and abs(pct) > self.FLAG_PCT))
                out.append({
                    "side": side, "number": number, "label": label, "current": a, "previous": b, "delta": delta, "pct": pct,
                    "flag": flag, "note": notes.get(number, ""),
                })
        return {
            "previousSeason": previous.name if previous else None,
            "lines": out,
            "unexplained": sum(1 for l in out if l["flag"] and not l["note"]),
            "totals": {"produits": (current["totalProduits"], before["totalProduits"] if before else None),
                       "charges": (current["totalCharges"], before["totalCharges"] if before else None),
                       "result": (current["result"], before["result"] if before else None)},
        }

    def set_note(self, db: Session, member: Member, season: Season, number: str, note: str) -> dict:
        """L'explication d'un compte en une ligne ; vide = effacée."""
        if not member.is_treasurer:
            raise PermissionError("Réservé au trésorier")
        number, note = number.strip()[:10], " ".join(note.split())[:300]
        row = db.scalar(select(FinSeasonNote).where(FinSeasonNote.org_id == member.org_id, FinSeasonNote.season_id == season.id, FinSeasonNote.number == number))
        if not note:
            if row is not None:
                db.delete(row)
        elif row is None:
            db.add(FinSeasonNote(org_id=member.org_id, season_id=season.id, number=number, note=note, created_by=member.person_id))
        else:
            row.note, row.created_by = note, member.person_id
        db.commit()
        return self.comparison(db, member, season)

    def notes(self, db: Session, org_id: int, season: Season) -> dict[str, str]:
        """Les explications de la trésorière sur la saison : {numéro: note}."""
        return {n.number: n.note for n in db.scalars(select(FinSeasonNote).where(FinSeasonNote.org_id == org_id, FinSeasonNote.season_id == season.id))}

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
        """La Balance au format comptable standard (celui des logiciels de
        la trésorière, §8.6) : Total Période débit / crédit, Solde Période
        débit / crédit, totaux des comptes de Bilan (classes 1 à 5), de
        Résultat (6 et 7) et de la Balance."""
        books = self.books(db, member, season)
        cutoff = books.pop("_cutoff")
        e = html.escape
        accounts = sorted(books.values(), key=lambda a: a.number)
        rows = []
        for a in accounts:
            sd, sc = max(a.balance, 0), max(-a.balance, 0)
            rows.append(f"<tr><td>{e(a.number)}</td><td class='l'>{e(a.label)}</td><td>{_c(a.debit)}</td><td>{_c(a.credit)}</td><td>{_c(sd)}</td><td>{_c(sc)}</td></tr>")

        def total(label: str, group: list) -> str:
            d, c = sum(a.debit for a in group), sum(a.credit for a in group)
            net = d - c
            return f"<tr class='total'><td></td><td class='l'>{label}</td><td>{_c(d)}</td><td>{_c(c)}</td><td>{_c(max(net, 0))}</td><td>{_c(max(-net, 0))}</td></tr>"

        bilan = [a for a in accounts if a.number[:1] in "12345"]
        resultat = [a for a in accounts if a.number[:1] in "67"]
        grand = (
            f"<tr class='total grand'><td></td><td class='l'>Total de la Balance</td><td>{_c(sum(a.debit for a in accounts))}</td><td>{_c(sum(a.credit for a in accounts))}</td>"
            f"<td>{_c(sum(max(a.balance, 0) for a in accounts))}</td><td>{_c(sum(max(-a.balance, 0) for a in accounts))}</td></tr>"
        )
        body = (
            self._report_header(org_name, f"Balance {season.name}", season.start_date, cutoff, accounts)
            + "<table><tr><th rowspan='2'>N° Compte</th><th rowspan='2' class='l'>Intitulé</th><th colspan='2' class='c'>Total Période</th><th colspan='2' class='c'>Solde Période</th></tr>"
            "<tr><th>Débit</th><th>Crédit</th><th>Débit</th><th>Crédit</th></tr>"
            + "".join(rows)
            + total("Total des comptes de Bilan", bilan)
            + total("Total des comptes de Résultat", resultat)
            + grand
            + "</table>"
        )
        return html_to_pdf(body, _CSS + _REPORT_CSS)

    @staticmethod
    def _report_header(org_name: str, title: str, start: str, end: str, accounts: list) -> str:
        """En-tête des états comptables (Grand livre, Balance) : nom de
        l'association, édition du, titre, période, devise, comptes de … à …"""
        e = html.escape
        numbers = [a.number for a in accounts]
        span = f"Comptes {e(min(numbers))} à {e(max(numbers))}" if numbers else "Aucun compte"
        return (
            f"<table class='bandeau'><tr><td class='org'>{e(org_name)}</td><td class='edition'>Édition du {datetime.now():%d/%m/%Y à %H:%M}</td></tr></table>"
            f"<h1 class='titre'>{e(title)}<br><span class='periode'>Du {_fr(start)} au {_fr(end)}</span></h1>"
            f"<table class='ligne'><tr><td>{span}</td><td class='edition'>Devise : EUR</td></tr></table>"
        )

    # ----- Bilan actif / passif -----

    def bilan(self, db: Session, member: Member, season: Season) -> dict:
        """Le bilan au dernier jour de la saison (PCA 2018, forme simplifiée des
        petites associations) : à l'actif ce qu'on a (créances, banque, caisse),
        au passif ce qu'on doit et les fonds propres (report à nouveau, résultat
        de la saison). Depuis les soldes des comptes de bilan de `books()` : un
        solde débiteur va à l'actif, un solde créditeur au passif ; le résultat
        de la saison (comptes 6 et 7) est porté aux fonds associatifs, ce qui
        équilibre les deux colonnes. Montants en centimes."""
        books = self.books(db, member, season)
        cutoff = books.pop("_cutoff")
        actif = {"creances": [], "tresorerie": []}
        passif = {"fonds": [], "dettes": []}
        result = -sum(a.balance for a in books.values() if a.nature in (EXPENSE, INCOME))  # excédent positif
        for a in sorted(books.values(), key=lambda a: a.number):
            if a.nature in (EXPENSE, INCOME) or not a.balance:
                continue
            line = {"number": a.number, "label": a.label, "amount": abs(a.balance)}
            if a.number.startswith("1"):
                passif["fonds"].append({**line, "amount": -a.balance})  # créditeur = positif ; un report débiteur se lit en négatif
            elif a.balance > 0:
                actif["tresorerie" if a.number.startswith("5") else "creances"].append(line)
            else:
                passif["dettes"].append(line)
        passif["fonds"].append({"number": "", "label": "Résultat de la saison" + (" (déficit)" if result < 0 else ""), "amount": result})
        total_actif = sum(l["amount"] for g in actif.values() for l in g)
        total_passif = sum(l["amount"] for g in passif.values() for l in g)
        return {"cutoff": cutoff, "actif": actif, "passif": passif, "result": result, "totalActif": total_actif, "totalPassif": total_passif}

    def bilan_pdf(self, db: Session, member: Member, season: Season, org_name: str) -> bytes:
        b = self.bilan(db, member, season)
        e = html.escape

        def bloc(title: str, lines: list[dict]) -> str:
            rows = "".join(f"<tr><td class='l'>{e(l['number'])} {e(l['label'])}</td><td>{_signed(l['amount'])}</td></tr>" for l in lines)
            total = sum(l["amount"] for l in lines)
            return f"<tr class='sous'><td class='l'>{e(title)}</td><td>{_signed(total)}</td></tr>{rows}"

        actif = bloc("Créances", b["actif"]["creances"]) + bloc("Trésorerie", b["actif"]["tresorerie"])
        passif = bloc("Fonds associatifs", b["passif"]["fonds"]) + bloc("Dettes", b["passif"]["dettes"])
        ecart = b["totalActif"] - b["totalPassif"]
        body = (
            f"<h1>{e(org_name)} — Bilan {e(season.name)}</h1>"
            f"<p class='muted'>Au {_fr(b['cutoff'])}. Ce que l'association possède (actif) et ce qu'elle doit, y compris à elle-même (passif).</p>"
            "<div class='cols'>"
            f"<table><tr><th class='l'>Actif</th><th></th></tr>{actif}<tr class='total'><td class='l'>Total actif</td><td>{_signed(b['totalActif'])}</td></tr></table>"
            f"<table><tr><th class='l'>Passif</th><th></th></tr>{passif}<tr class='total'><td class='l'>Total passif</td><td>{_signed(b['totalPassif'])}</td></tr></table>"
            "</div>"
            + (f"<p class='muted'>Écart actif − passif : {_signed(ecart)} (une ligne de banque sans compte, ou des soldes de départ incomplets).</p>" if ecart else "")
        )
        return html_to_pdf(body, _CSS + " th.l, td.l { text-align: left; } .cols { display: flex; gap: 24px; align-items: flex-start; } .cols table { flex: 1; } tr.sous td { font-weight: bold; padding-top: 10px; }")

    def grand_livre_pdf(self, db: Session, member: Member, season: Season, org_name: str) -> bytes:
        """Le Grand livre au format comptable standard (§8.6) : un bloc par
        compte, Type / Date / Journal / Pièce / Libellé / Lettre / Débit /
        Crédit / Solde, « Total pour le compte », « Total du Grand-Livre »."""
        books = self.books(db, member, season)
        cutoff = books.pop("_cutoff")
        e = html.escape
        accounts = sorted(books.values(), key=lambda a: a.number)
        # Colonne Type : le cadenas = écriture validée, ce que la clôture de
        # la saison fait de toutes ses écritures (§8.7).
        closing = self.closing(db, member.org_id, season.id)
        kind = _PADLOCK if closing is not None else ""
        parts = [self._report_header(org_name, f"Grand livre {season.name}", season.start_date, cutoff, accounts)]
        parts.append("<p class='muted'>Journaux : AN à-nouveaux, BQn banque, CA caisse, AC achats, HO honoraires, NF notes de frais, OD écritures à la main.</p>")
        if closing is not None:
            parts.append(f"<p class='muted'>{_PADLOCK} Écritures validées par la clôture du {closing.closed_at:%d/%m/%Y} : elles ne changent plus.</p>")
        # Mêmes largeurs de colonnes d'un compte à l'autre.
        cols = "<colgroup><col style='width:4%'><col style='width:9%'><col style='width:7%'><col style='width:12%'><col style='width:35%'><col style='width:6%'><col style='width:9%'><col style='width:9%'><col style='width:9%'></colgroup>"
        head = "<tr><th>Type</th><th>Date</th><th>Journal</th><th class='l'>Pièce</th><th class='l'>Libellé</th><th>Lettre</th><th>Débit</th><th>Crédit</th><th>Solde</th></tr>"
        total_d = total_c = 0
        for a in accounts:
            running = 0
            lines = []
            for l in a.lines:
                running += l.debit - l.credit
                lines.append(
                    f"<tr><td>{kind}</td><td>{_fr(l.date)}</td><td>{e(l.journal)}</td><td class='l'>{e(l.piece)}</td><td class='l'>{e(l.label)}</td><td>{e(l.letter)}</td>"
                    f"<td>{_c(l.debit)}</td><td>{_c(l.credit)}</td><td>{_signed(running)}</td></tr>"
                )
            total_d, total_c = total_d + a.debit, total_c + a.credit
            parts.append(
                f"<table class='small compte'>{cols}<tr class='compte'><th colspan='9' class='l'>{e(a.number)}&nbsp;&nbsp;&nbsp;{e(a.label)}</th></tr>"
                + head
                + "".join(lines)
                + f"<tr class='total'><td></td><td></td><td></td><td></td><td class='l'>Total pour le compte {e(a.number)}</td><td></td><td>{_c(a.debit)}</td><td>{_c(a.credit)}</td><td>{_signed(a.balance)}</td></tr></table>"
            )
        parts.append(
            f"<table class='small compte'>{cols}<tr class='total grand'><td colspan='6' class='l'>Total du Grand-Livre</td><td>{_c(total_d)}</td><td>{_c(total_c)}</td><td>{_signed(total_d - total_c)}</td></tr></table>"
        )
        return html_to_pdf("".join(parts), _CSS + _REPORT_CSS)

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

    # ----- FEC et son contrôle -----

    def fec_entries(self, db: Session, member: Member, season: Season) -> list[dict]:
        """Les écritures de la saison (celles du Grand livre), regroupées :
        une écriture = les lignes d'un même journal, d'un même jour, d'une
        même opération de banque (ou du même libellé ; les à-nouveaux en une
        seule), numérotées par date."""
        books = self.books(db, member, season)
        books.pop("_cutoff")
        groups: dict[tuple, list[tuple[Account, Line]]] = defaultdict(list)
        for a in books.values():
            for l in a.lines:
                same = "" if l.journal == "AN" else l.operation_id if l.operation_id is not None else l.label
                groups[(l.date, l.journal, same)].append((a, l))
        lettered: dict[tuple[str, str], str] = {}
        for a in books.values():
            for l in a.lines:
                if l.letter:
                    key = (a.number, l.letter)
                    lettered[key] = max(lettered.get(key, ""), l.date)
        entries = []
        for n, key in enumerate(sorted(groups, key=lambda k: (k[0], k[1] != "AN", k[1], str(k[2]))), start=1):
            day, journal, _ = key
            entries.append({"number": n, "date": day, "journal": journal, "lines": [
                {"account": a.number, "accountLabel": a.label, "label": l.label, "piece": l.piece, "debit": l.debit,
                 "credit": l.credit, "letter": l.letter, "letterDate": lettered.get((a.number, l.letter), "") if l.letter else ""}
                for a, l in groups[key]
            ]})
        return entries

    def fec(self, db: Session, member: Member, season: Season) -> bytes:
        def d(day: str) -> str:
            return day.replace("-", "")

        def amount(cents: int) -> str:
            return f"{cents // 100},{cents % 100:02d}"

        def clean(text: str) -> str:
            return " ".join(str(text or "").replace("\t", " ").split())

        # ValidDate : la date de validation de l'écriture ; chez nous la
        # clôture de la saison (§8.7), sinon la date de l'écriture.
        closing = self.closing(db, member.org_id, season.id)
        valid = closing.closed_at.strftime("%Y%m%d") if closing is not None else None
        rows = ["\t".join(FEC_COLUMNS)]
        for e in self.fec_entries(db, member, season):
            journal = e["journal"]
            for l in e["lines"]:
                rows.append("\t".join([
                    journal, JOURNALS.get(journal[:2], journal), str(e["number"]), d(e["date"]), l["account"], clean(l["accountLabel"]),
                    "", "", clean(l["piece"]) or str(e["number"]), d(e["date"]), clean(l["label"]) or JOURNALS.get(journal[:2], journal),
                    amount(l["debit"]), amount(l["credit"]), l["letter"], d(l["letterDate"]), valid or d(e["date"]), "", "",
                ]))
        return ("\r\n".join(rows) + "\r\n").encode("iso8859_15", errors="replace")

    def fec_check(self, db: Session, member: Member, season: Season) -> dict:
        """Ce qui empêche le FEC d'être juste (spec §8.6) : rien à corriger
        quand problems est vide ; notes = ce qu'il faut savoir sans être faux."""
        entries = self.fec_entries(db, member, season)
        lines = [(e, l) for e in entries for l in e["lines"]]
        problems, notes = [], []
        unbalanced = [e["number"] for e in entries if sum(l["debit"] - l["credit"] for l in e["lines"])]
        if unbalanced:
            problems.append(f"{len(unbalanced)} écriture(s) déséquilibrée(s) : n° {', '.join(map(str, unbalanced[:10]))}.")
        total = sum(l["debit"] - l["credit"] for _, l in lines)
        if total:
            problems.append(f"Débit et crédit diffèrent de {_eur(abs(total) / 100)}.")
        unclassified = [l for _, l in lines if l["account"] in {n for n, _ in UNCLASSIFIED.values()}]
        if unclassified:
            amount = sum(l["debit"] + l["credit"] for l in unclassified)
            problems.append(f"{len(unclassified)} ligne(s) à classer ({_eur(amount / 100)}) : Comptes › Sans compte.")
        outside = [e["number"] for e in entries if not season.start_date <= e["date"] <= season.end_date]
        if outside:
            problems.append(f"{len(outside)} écriture(s) hors de la saison.")
        bad = sorted({l["account"] for _, l in lines if len(l["account"]) < 3 or l["account"][0] not in "1234567"})
        if bad:
            problems.append(f"Numéros de compte hors plan : {', '.join(bad)}.")
        nameless = sorted({l["account"] for _, l in lines if not l["accountLabel"].strip()})
        if nameless:
            problems.append(f"Comptes sans libellé : {', '.join(nameless)}.")
        open_letters: dict[tuple[str, str], int] = defaultdict(int)
        for _, l in lines:
            if l["letter"]:
                open_letters[(l["account"], l["letter"])] += l["debit"] - l["credit"]
        wrong = sorted(f"{a} {letter}" for (a, letter), rest in open_letters.items() if rest)
        if wrong:
            problems.append(f"Lettrage qui ne s'équilibre pas : {', '.join(wrong[:10])}.")
        if self.accounting.level(db, member.org_id) != FULL:
            notes.append("Niveau Simple : comptabilité de trésorerie, sans fournisseurs ni lettrage.")
        if not any(e["journal"] == "AN" for e in entries):
            notes.append("Pas d'à-nouveaux : aucun solde de départ connu pour la saison.")
        return {"ok": not problems, "entries": len(entries), "lines": len(lines), "problems": problems, "notes": notes}

    # ----- production et rangement -----

    def _build(self, db: Session, member: Member, season: Season, kind: str) -> tuple[bytes, str, str]:
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
        elif kind == "bilan":
            content = self.bilan_pdf(db, member, season, org_name)
        elif kind == "fec":
            content = self.fec(db, member, season)
        else:
            content = self.fees_xlsx(db, member, season, org_name)
        name = f"{title} {season.name}.{extension}"
        media = {"pdf": "application/pdf", "txt": "text/plain; charset=iso-8859-15"}.get(
            extension, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        return content, name, media

    def produce(self, db: Session, member: Member, season: Season, kind: str) -> tuple[bytes, str, str]:
        """(contenu, nom de fichier, type) d'un document ; rangé dans Docs ›
        Financier › AG si l'appli le permet."""
        content, name, media = self._build(db, member, season, kind)
        store_file(self.ports.store, db, member, name, content)
        return content, name, media

    def in_docs(self, db: Session, member: Member, season: Season, kind: str) -> int | None:
        """Produit le document, le range dans Docs › Financier › AG et rend
        l'id du fichier (pour l'ouvrir depuis Docs)."""
        content, name, _ = self._build(db, member, season, kind)
        return store_file(self.ports.store, db, member, name, content)

    @staticmethod
    def kinds(level: str) -> list[dict]:
        """Les documents du niveau (Simple : Synthèse ; Complet : tous)."""
        return [
            {"id": key, "title": title, "format": extension, "level": needed}
            for key, (title, extension, needed) in KINDS.items()
            if level == "complet" or needed == "simple"
        ]


def _third_party(accounts: list, piece: dict | None):
    """Le compte de tiers d'une pièce (401 pour un achat, 467x pour des
    honoraires ou une note de frais, celui qui porte le nom de la personne
    s'il existe), ou None sans pièce ou sans compte de ce genre."""
    if not piece or piece.get("nature") not in THIRD_PARTY_PREFIX:
        return None
    candidates = [a for a in accounts if a.number.startswith(THIRD_PARTY_PREFIX[piece["nature"]])]
    if not candidates:
        return None
    named = [a for a in candidates if _named(a, piece.get("person"))]
    return named[0] if named else min(candidates, key=lambda a: (len(a.number), a.number))


def _named(account, person) -> bool:
    """Le libellé du compte porte un mot du nom de la personne."""
    words = [w.lower() for w in str(person or "").split() if len(w) > 2]
    return any(w in account.label.lower() for w in words)


def _letter(n: int) -> str:
    """Lettre de lettrage : AAA, AAB, … (n à partir de 1)."""
    n -= 1
    return chr(65 + n // 676 % 26) + chr(65 + n // 26 % 26) + chr(65 + n % 26)


def _nature_of(number: str, db: Session, accounting: Accounting, org_id: int) -> str:
    if number.startswith(BANK_BASE):
        return "banque"
    if number == CASH:
        return "caisse"
    if number == CARRY_FORWARD:
        return "report"
    account = next((a for a in accounting.accounts(db, org_id) if a.number == number), None)
    return account.nature if account is not None else THIRD_PARTY


def store_file(store, db: Session, member: Member, name: str, content: bytes) -> int | None:
    """Range un fichier produit dans Docs › Financier › AG ; rend son id."""
    if store is None:
        return None
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / name
        path.write_bytes(content)
        ids = store(db, member, ["AG"], [(name, path)])
    return ids[0] if ids else None


def _c(cents: int) -> str:
    return "" if not cents else _eur(cents / 100)


def _signed(cents: int) -> str:
    return _eur(cents / 100) if cents else ""
