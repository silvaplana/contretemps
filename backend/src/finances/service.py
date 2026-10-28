"""Comptes de l'organisation (sous-module Comptes, spec/modules/financier.md
§3) : historique bancaire construit à partir des relevés PDF de la banque,
repris de Sambo Admin (bankstatements/).

Les relevés sont déposés depuis Financier › Comptes (PDF un par un ou
archive) : chaque opération est stockée dans la base (tables fin_*, voir
models.py), une seule table pour tous les comptes. Un relevé déjà importé
(même compte, même période) est ignoré : on peut redéposer toute une archive
sans créer de doublon. Chaque organisation ne voit que ses comptes.

Virements entre les comptes de l'organisation (ex. livret → compte
courant) : visibles sur les deux relevés. Les deux opérations sont reliées
(transfer_id) pour n'afficher qu'une ligne dans la vue « tous les comptes »,
où elles ne changent pas le total.

Les opérations provisoires (source « banque ») viennent de la connexion
bancaire (bank.py) ; le relevé qui les couvre les efface en arrivant.
"""

from __future__ import annotations

import io
import tarfile
import tempfile
import zipfile
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import py7zr
from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories import CATEGORY_NAMES, categorize
from .models import SOURCE_BANK, FinAccount, FinBankConnection, FinOperation, FinStatement
from .parser import ParsedStatement, StatementParseError, parse_statement
from .ports import Member

# Écart maximal (jours) entre les deux opérations d'un virement interne.
TRANSFER_MAX_DAYS = 3


class AccountNotFoundError(LookupError):
    """Levée quand le compte demandé n'existe pas dans l'organisation."""


def _account_name(product: str) -> tuple[str, str]:
    """(libellé affiché, nature) d'un compte d'après l'intitulé du relevé."""
    upper = product.upper()
    if "LIVRET BLEU" in upper:
        return "Livret Bleu", "savings"
    if "LIVRET" in upper:
        return product.title(), "savings"
    return "Compte courant", "checking"


def _check(member: Member) -> None:
    if not member.keeps_accounts:
        raise PermissionError("Réservé aux trésoriers")


class Finances:
    """Import des relevés et lecture de l'historique (voir le docstring du
    module)."""

    # ----- import -----

    def import_files(self, db: Session, member: Member, files: list[tuple[str, bytes]]) -> dict:
        """Importe des relevés PDF (ou des archives de PDF). Retourne le
        compte rendu : {"imported": [...], "skipped": [...], "errors": [...]},
        une entrée {"file", "detail"} par relevé."""
        _check(member)
        report: dict[str, list[dict]] = {"imported": [], "skipped": [], "errors": []}
        for name, data in self._expand(files):
            try:
                statement = parse_statement(data)
            except StatementParseError as exc:
                report["errors"].append({"file": name, "detail": str(exc)})
                continue
            period = f"{statement.start_date} → {statement.end_date}"
            if self._store(db, member.org_id, name, statement):
                report["imported"].append({"file": name, "detail": f"{period}, {len(statement.operations)} opérations"})
            else:
                report["skipped"].append({"file": name, "detail": f"{period} déjà importé"})
        if report["imported"]:
            self._link_transfers(db, member.org_id)
        db.commit()
        return report

    @staticmethod
    def _expand(files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
        """Remplace chaque archive (zip, 7z, tar/tar.gz...) par les PDF
        qu'elle contient, dans l'ordre alphabétique."""
        expanded = []
        for name, data in files:
            members: list[tuple[str, bytes]] = []
            if zipfile.is_zipfile(io.BytesIO(data)):
                with zipfile.ZipFile(io.BytesIO(data)) as archive:
                    members = [(m, archive.read(m)) for m in archive.namelist() if not m.endswith("/")]
            elif py7zr.is_7zfile(io.BytesIO(data)):
                with tempfile.TemporaryDirectory() as tmp, py7zr.SevenZipFile(io.BytesIO(data)) as archive:
                    archive.extractall(tmp)
                    members = [(str(f.relative_to(tmp)), f.read_bytes()) for f in Path(tmp).rglob("*") if f.is_file()]
            else:
                try:
                    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
                        members = [(m.name, archive.extractfile(m).read()) for m in archive.getmembers() if m.isfile()]
                except tarfile.TarError:
                    expanded.append((name, data))
                    continue
            expanded.extend(
                (member.rsplit("/", 1)[-1], content)
                for member, content in sorted(members)
                if member.lower().endswith(".pdf") and "__MACOSX/" not in member
            )
        return expanded

    def _store(self, db: Session, org_id: int, file_name: str, statement: ParsedStatement) -> bool:
        """Enregistre le relevé et ses opérations. False s'il était déjà là."""
        account = db.scalar(select(FinAccount).where(FinAccount.org_id == org_id, FinAccount.number == statement.account_number))
        # Compte créé par la connexion bancaire : son numéro est l'IBAN, qui
        # contient le numéro lu sur le relevé.
        account = account or next(
            (
                a
                for a in db.scalars(select(FinAccount).where(FinAccount.org_id == org_id, FinAccount.bank_uid.is_not(None)))
                if statement.account_number in a.number
            ),
            None,
        )
        if account is None:
            name, kind = _account_name(statement.account_product)
            account = FinAccount(org_id=org_id, number=statement.account_number, name=name, kind=kind)
            db.add(account)
            db.flush()
        start, end = date.fromisoformat(statement.start_date), date.fromisoformat(statement.end_date)
        already = db.scalar(
            select(FinStatement.id).where(
                FinStatement.account_id == account.id, FinStatement.start_date == start, FinStatement.end_date == end
            )
        )
        if already is not None:
            return False
        stored = FinStatement(
            account_id=account.id,
            start_date=start,
            start_balance=statement.start_balance,
            end_date=end,
            end_balance=statement.end_balance,
            file_name=file_name,
        )
        db.add(stored)
        db.flush()
        db.add_all(
            FinOperation(
                account_id=account.id,
                statement_id=stored.id,
                position=i,
                date=date.fromisoformat(op.date),
                value_date=date.fromisoformat(op.value_date),
                label=op.label,
                details=op.details,
                amount=op.amount,
            )
            for i, op in enumerate(statement.operations)
        )
        # Le relevé fait foi : les opérations lues à la banque qu'il couvre
        # s'effacent (voir bank.py).
        from .bank import delete_provisional

        delete_provisional(
            db,
            list(
                db.scalars(
                    select(FinOperation).where(
                        FinOperation.account_id == account.id, FinOperation.source == SOURCE_BANK, FinOperation.date <= end
                    )
                )
            ),
        )
        db.flush()
        return True

    def rename_account(self, db: Session, member: Member, account_id: int, name: str) -> dict:
        """Le trésorier nomme un compte (« Honoraires profs », « Livret A »)."""
        _check(member)
        account = db.get(FinAccount, account_id)
        if account is None or account.org_id != member.org_id:
            raise AccountNotFoundError(account_id)
        name = name.strip()[:80]
        if not name:
            raise ValueError("Donnez un nom au compte.")
        account.name = name
        db.commit()
        return {"id": account.id, "name": account.name}

    @staticmethod
    def _link_transfers(db: Session, org_id: int) -> None:
        """Relie les virements entre comptes de l'organisation pas encore
        reliés : un virement (« VIR... ») dans un compte et l'opération de
        montant opposé dans un autre compte, à TRANSFER_MAX_DAYS jours près."""
        rows = list(
            db.scalars(
                select(FinOperation)
                .join(FinAccount)
                .where(FinAccount.org_id == org_id, FinOperation.transfer_id.is_(None), FinOperation.label.like("VIR%"))
                .order_by(FinOperation.date, FinOperation.id)
            )
        )
        linked: set[int] = set()
        for debit in (r for r in rows if r.amount < 0):
            for credit in rows:
                if (
                    credit.id not in linked
                    and credit.account_id != debit.account_id
                    and credit.amount == -debit.amount
                    and abs((credit.date - debit.date).days) <= TRANSFER_MAX_DAYS
                ):
                    linked.update((debit.id, credit.id))
                    debit.transfer_id, credit.transfer_id = credit.id, debit.id
                    break
        db.flush()

    # ----- lecture -----

    def get_ledger(self, db: Session, member: Member, account_id: int | None = None) -> dict:
        """Historique, la plus récente opération en premier.

        account_id absent : tous les comptes ensemble. Chaque ligne porte le
        solde de chaque compte après l'opération et leur total (None tant
        qu'un compte n'a pas encore de relevé). Un virement interne n'occupe
        qu'une ligne (transfer: {"from", "to"}, montant positif).
        Avec account_id : les opérations de ce compte seul et son solde.

        Retour : {"accounts": [{"id", "name", "kind", "number", "iban",
        "bank", "balance", "asOf", "coverage": [{"from", "to",
        "statements"}]}], "allAccounts",
        "total", "categories", "rows": [...], "issues": [...]} (montants en
        euros, dates ISO ; chaque ligne porte sa "category", voir
        categories.py).
        """
        _check(member)
        org_id = member.org_id
        accounts = list(db.scalars(select(FinAccount).where(FinAccount.org_id == org_id).order_by(FinAccount.kind, FinAccount.id)))
        if account_id is not None and account_id not in {a.id for a in accounts}:
            raise AccountNotFoundError(account_id)
        statements = list(
            db.scalars(
                select(FinStatement)
                .join(FinAccount)
                .where(FinAccount.org_id == org_id)
                .order_by(FinStatement.account_id, FinStatement.start_date)
            )
        )
        # Ordre de lecture : date, puis relevé le plus ancien (une opération
        # provisoire, sans relevé, après), compte, rang dans le relevé.
        starts = {s.id: s.start_date for s in statements}
        operations = sorted(
            db.scalars(
                select(FinOperation).join(FinAccount).where(FinAccount.org_id == org_id)
            ),
            key=lambda o: (o.date, starts.get(o.statement_id, date.max), o.account_id, o.position),
        )

        first: dict[int, FinStatement] = {}
        last: dict[int, FinStatement] = {}
        # Périodes couvertes sans trou, par compte : relevés qui s'enchaînent
        # (solde de début = solde de fin du précédent).
        coverage: dict[int, list[dict]] = {}
        issues = []
        names = {a.id: a.name for a in accounts}
        for s in statements:
            previous = last.get(s.account_id)
            periods = coverage.setdefault(s.account_id, [])
            if previous is not None and s.start_balance == previous.end_balance:
                periods[-1]["to"] = s.end_date.isoformat()
                periods[-1]["statements"] += 1
            else:
                periods.append({"from": s.start_date.isoformat(), "to": s.end_date.isoformat(), "statements": 1})
            if previous is None:
                first[s.account_id] = s
            elif s.start_balance != previous.end_balance:
                issues.append(
                    f"{names[s.account_id]} : il manque un relevé entre le {_fr(previous.end_date)} "
                    f"({previous.end_balance / 100:.2f} €) et le {_fr(s.start_date)} "
                    f"({s.start_balance / 100:.2f} €)"
                )
            last[s.account_id] = s
        # Compte connu seulement par la connexion bancaire : le solde lu à la
        # banque sert de point de départ (solde au début = solde lu - les
        # opérations lues).
        for a in accounts:
            if a.id not in first and a.bank_balance is not None:
                ops = [op for op in operations if op.account_id == a.id]
                # Connu sur toute la période lue : il entre dans le total dès le début.
                first[a.id] = SimpleNamespace(start_date=date.min, start_balance=a.bank_balance - sum(op.amount for op in ops))

        visible = [a.id for a in accounts if account_id in (None, a.id)]
        balances: dict[int, int | None] = {a: None for a in visible}
        by_id = {op.id: op for op in operations}
        rows = []
        for op in operations:
            if op.account_id not in balances:
                continue
            twin = by_id.get(op.transfer_id) if account_id is None and op.transfer_id is not None else None
            if twin is not None and op.amount > 0:
                continue  # ligne déjà produite par le débit du virement
            # Un compte entre dans le total à la date de début de son 1er relevé.
            for aid, balance in balances.items():
                if balance is None and aid in first and first[aid].start_date <= op.date:
                    balances[aid] = first[aid].start_balance
            for affected in (op, twin) if twin is not None else (op,):
                aid = affected.account_id
                # Jumelle d'un virement datée quelques jours après : son compte
                # peut ne pas être encore entré dans le total à cette date.
                if balances[aid] is None and aid in first:
                    balances[aid] = first[aid].start_balance
                balances[aid] += affected.amount
            known = all(b is not None for b in balances.values())
            transfer = {"from": names[op.account_id], "to": names[twin.account_id]} if twin is not None else None
            rows.append(
                {
                    "id": op.id,
                    "date": op.date.isoformat(),
                    "valueDate": op.value_date.isoformat(),
                    "accountId": op.account_id,
                    "label": op.label,
                    "details": op.details,
                    # Recette / dépense déduite du libellé (voir categories.py) ;
                    # un virement entre les comptes de l'organisation est à part.
                    "category": categorize(op.label, op.details, op.transfer_id is not None),
                    "amount": (abs(op.amount) if twin is not None else op.amount) / 100,
                    "transfer": transfer,
                    # Lue par la connexion bancaire, pas encore dans un relevé.
                    "provisional": op.source == SOURCE_BANK,
                    "balances": {str(a): (b / 100 if b is not None else None) for a, b in balances.items()},
                    "total": sum(balances.values()) / 100 if known else None,
                }
            )
        # Comptes sans aucune opération importée : solde du relevé.
        for aid in visible:
            if balances[aid] is None and aid in first:
                balances[aid] = first[aid].start_balance
        rows.reverse()

        def as_of(account: FinAccount) -> str | None:
            # Date jusqu'à laquelle le solde est connu : fin du dernier
            # relevé, ou dernière opération lue à la banque.
            dates = [last[account.id].end_date] if account.id in last else []
            dates += [op.date for op in operations if op.account_id == account.id and op.source == SOURCE_BANK]
            dates += [account.bank_balance_date] if account.bank_balance_date and account.id not in last else []
            return max(dates).isoformat() if dates else None

        # Fiche du compte (« Voir le compte ») : IBAN et banque, s'il est relié.
        connection = db.scalar(select(FinBankConnection).where(FinBankConnection.org_id == org_id))
        ibans = {b["uid"]: b.get("iban") for b in (connection.accounts or [])} if connection is not None else {}
        return {
            "accounts": [
                {
                    "id": a.id,
                    "name": a.name,
                    "kind": a.kind,
                    "number": a.number,
                    "iban": ibans.get(a.bank_uid) if a.bank_uid else None,
                    "bank": connection.bank if a.bank_uid and connection is not None else None,
                    "balance": balances[a.id] / 100 if balances.get(a.id) is not None else None,
                    "asOf": as_of(a),
                    "coverage": coverage.get(a.id, []),
                }
                for a in accounts
                if a.id in visible
            ],
            # Tous les comptes (pour choisir la vue), même avec account_id.
            # number : pour distinguer deux comptes de même nature au moment de
            # les nommer (deux comptes courants, Seb 28 octobre).
            "allAccounts": [{"id": a.id, "name": a.name, "kind": a.kind, "number": a.number} for a in accounts],
            "total": sum(b for b in balances.values() if b is not None) / 100,
            # Toutes les catégories possibles, dans l'ordre d'affichage.
            "categories": CATEGORY_NAMES,
            "rows": rows,
            "issues": issues,
        }


def _fr(day: date) -> str:
    return day.strftime("%d/%m/%Y")
