"""Comptabilité du module finances (spec/modules/financier.md §8) : plan
comptable de l'organisation, réglage Simple / Complet, compte sur chaque
ligne de banque (ventilation confirmée par le trésorier), caisse.

Tout est calculé depuis les lignes de banque et de caisse ; l'appli ne
propose un compte qu'à l'écran (voir chart.py), rien n'est écrit sans
confirmation. Les montants sont en centimes.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter
from collections.abc import Callable
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .chart import DEFAULT_CHART, Proposal, label_key, propose
from .models import (
    FULL,
    LEVELS,
    NATURES,
    SIMPLE,
    FinAccount,
    FinCashLine,
    FinChartAccount,
    FinOperation,
    FinOperationAccount,
    FinSettings,
)
from .ports import Member

# Libellés des natures à l'écran (jamais « type », spec §8.2).
NATURE_LABELS = {"depense": "Dépenses", "recette": "Recettes", "tiers": "Tiers", "attente": "Attente"}


class AccountingError(ValueError):
    """Donnée refusée (message affichable tel quel)."""


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _check(member: Member) -> None:
    if not member.keeps_accounts:
        raise PermissionError("Réservé aux trésoriers")


class Accounting:
    def __init__(self, pieces: Callable[[Session, int], dict[int, dict]] | None = None) -> None:
        """pieces(db, org_id) : la pièce rattachée à chaque opération
        bancaire ({operation_id: {"id", "title", "kind"}}), fournie par
        l'appli hôte (les dépenses du module notes de frais)."""
        self.pieces = pieces

    # ----- réglage -----

    def level(self, db: Session, org_id: int) -> str:
        settings = db.get(FinSettings, org_id)
        return settings.level if settings is not None else SIMPLE

    def set_level(self, db: Session, member: Member, level: str) -> str:
        _check(member)
        if level not in LEVELS:
            raise AccountingError("Niveau inconnu (simple ou complet).")
        settings = db.get(FinSettings, member.org_id)
        if settings is None:
            db.add(FinSettings(org_id=member.org_id, level=level))
        else:
            if settings.level == FULL and level == SIMPLE:
                raise AccountingError("On ne revient pas de Complet à Simple.")
            settings.level = level
        db.commit()
        return level

    # ----- plan comptable -----

    def ensure_chart(self, db: Session, org_id: int) -> None:
        """Une organisation sans plan reçoit la liste par défaut."""
        if db.scalar(select(func.count()).select_from(FinChartAccount).where(FinChartAccount.org_id == org_id)):
            return
        db.add_all(
            FinChartAccount(
                org_id=org_id, number=a.number, label=a.label, nature=a.nature, event=a.event, keywords=list(a.keywords)
            )
            for a in DEFAULT_CHART
        )
        db.commit()

    def accounts(self, db: Session, org_id: int, active_only: bool = False) -> list[FinChartAccount]:
        self.ensure_chart(db, org_id)
        query = select(FinChartAccount).where(FinChartAccount.org_id == org_id)
        if active_only:
            query = query.where(FinChartAccount.active.is_(True))
        return sorted(db.scalars(query), key=lambda a: (NATURES.index(a.nature), a.number))

    def chart(self, db: Session, member: Member) -> dict:
        """Le plan comptable à l'écran : niveau, comptes avec le nombre de
        lignes confirmées sur chacun."""
        _check(member)
        counts = dict(
            db.execute(
                select(FinOperationAccount.account_id, func.count())
                .join(FinChartAccount)
                .where(FinChartAccount.org_id == member.org_id)
                .group_by(FinOperationAccount.account_id)
            ).all()
        )
        cash_counts = dict(
            db.execute(
                select(FinCashLine.account_id, func.count())
                .where(FinCashLine.org_id == member.org_id, FinCashLine.account_id.is_not(None))
                .group_by(FinCashLine.account_id)
            ).all()
        )
        return {
            "level": self.level(db, member.org_id),
            "natures": [{"id": n, "label": NATURE_LABELS[n]} for n in NATURES],
            "accounts": [
                {**self._account(a), "used": counts.get(a.id, 0) + cash_counts.get(a.id, 0)}
                for a in self.accounts(db, member.org_id)
            ],
        }

    @staticmethod
    def _account(a: FinChartAccount) -> dict:
        return {
            "id": a.id,
            "number": a.number,
            "label": a.label,
            "nature": a.nature,
            "event": a.event,
            "keywords": list(a.keywords or []),
            "active": a.active,
        }

    def _validate(self, db: Session, org_id: int, data: dict, current: FinChartAccount | None = None) -> dict:
        number = str(data.get("number", "")).strip()
        label = str(data.get("label", "")).strip()[:80]
        nature = data.get("nature", current.nature if current else None)
        if not number.isdigit() or not 3 <= len(number) <= 10:
            raise AccountingError("Le numéro de compte est fait de 3 à 10 chiffres.")
        if not label:
            raise AccountingError("Donnez un libellé au compte.")
        if nature not in NATURES:
            raise AccountingError("Nature inconnue.")
        taken = db.scalar(
            select(FinChartAccount.id).where(FinChartAccount.org_id == org_id, FinChartAccount.number == number)
        )
        if taken is not None and (current is None or taken != current.id):
            raise AccountingError(f"Le compte {number} existe déjà.")
        keywords = [str(k).strip() for k in data.get("keywords") or [] if str(k).strip()]
        event = (data.get("event") or "").strip()[:40] or None
        return {"number": number, "label": label, "nature": nature, "keywords": keywords, "event": event}

    def create_account(self, db: Session, member: Member, data: dict) -> dict:
        _check(member)
        self.ensure_chart(db, member.org_id)
        account = FinChartAccount(org_id=member.org_id, **self._validate(db, member.org_id, data))
        db.add(account)
        db.commit()
        return self._account(account)

    def _chart_account(self, db: Session, org_id: int, account_id: int) -> FinChartAccount:
        account = db.get(FinChartAccount, account_id)
        if account is None or account.org_id != org_id:
            raise LookupError("Compte inconnu")
        return account

    def update_account(self, db: Session, member: Member, account_id: int, data: dict) -> dict:
        _check(member)
        account = self._chart_account(db, member.org_id, account_id)
        for key, value in self._validate(db, member.org_id, data, account).items():
            setattr(account, key, value)
        if "active" in data:
            account.active = bool(data["active"])
        db.commit()
        return self._account(account)

    def delete_account(self, db: Session, member: Member, account_id: int) -> None:
        """Supprime un compte jamais utilisé ; sinon le passe inactif."""
        _check(member)
        account = self._chart_account(db, member.org_id, account_id)
        used = db.scalar(select(func.count()).select_from(FinOperationAccount).where(FinOperationAccount.account_id == account.id))
        used += db.scalar(select(func.count()).select_from(FinCashLine).where(FinCashLine.account_id == account.id))
        if used:
            account.active = False
        else:
            db.delete(account)
        db.commit()

    # ----- compte sur chaque ligne -----

    def _operation(self, db: Session, org_id: int, operation_id: int) -> FinOperation:
        row = db.execute(
            select(FinOperation).join(FinAccount).where(FinOperation.id == operation_id, FinAccount.org_id == org_id)
        ).scalar()
        if row is None:
            raise LookupError("Opération inconnue")
        return row

    def _lines(self, db: Session, org_id: int) -> dict[int, list[FinOperationAccount]]:
        """Les ventilations confirmées de l'organisation, par opération."""
        rows = db.execute(
            select(FinOperationAccount)
            .join(FinOperation, FinOperationAccount.operation_id == FinOperation.id)
            .join(FinAccount)
            .where(FinAccount.org_id == org_id)
            .order_by(FinOperationAccount.id)
        ).scalars()
        by_operation: dict[int, list[FinOperationAccount]] = {}
        for line in rows:
            by_operation.setdefault(line.operation_id, []).append(line)
        return by_operation

    def _history(self, db: Session, org_id: int) -> dict[str, Counter]:
        """{clé de libellé: Counter(account_id)} des opérations confirmées
        sur un seul compte (une ventilation ne fait pas une habitude)."""
        history: dict[str, Counter] = {}
        operations = {o.id: o for o in db.scalars(select(FinOperation).join(FinAccount).where(FinAccount.org_id == org_id))}
        for operation_id, lines in self._lines(db, org_id).items():
            if len(lines) != 1:
                continue
            key = label_key(operations[operation_id].label)
            if key:
                history.setdefault(key, Counter())[lines[0].account_id] += 1
        return history

    def annotate(self, db: Session, org_id: int, rows: list[dict]) -> list[dict]:
        """Ajoute à chaque ligne de l'historique (Finances.get_ledger) son
        compte confirmé (`account` : {"id", "number", "label", "split"}),
        sinon la proposition (`proposal`), et sa pièce (`piece`). Un virement
        interne n'a ni compte ni pièce."""
        accounts = self.accounts(db, org_id, active_only=True)
        by_id = {a.id: a for a in self.accounts(db, org_id)}
        lines = self._lines(db, org_id)
        history = self._history(db, org_id)
        pieces = self.pieces(db, org_id) if self.pieces is not None else {}
        for row in rows:
            row["account"] = row["proposal"] = row["piece"] = None
            if row.get("transfer"):
                continue
            confirmed = lines.get(row["id"])
            if confirmed:
                first = by_id[confirmed[0].account_id]
                row["account"] = {"id": first.id, "number": first.number, "label": first.label, "split": len(confirmed) > 1}
            else:
                proposal = propose(accounts, row["label"], row.get("details", ""), round(row["amount"] * 100), history)
                row["proposal"] = self._proposal(by_id, proposal)
            row["piece"] = pieces.get(row["id"])
        return rows

    @staticmethod
    def _proposal(by_id: dict[int, FinChartAccount], proposal: Proposal | None) -> dict | None:
        if proposal is None:
            return None
        account = by_id[proposal.account_id]
        return {"id": account.id, "number": account.number, "label": account.label, "reason": proposal.reason}

    def operation(self, db: Session, member: Member, operation_id: int) -> dict:
        """La fiche d'une opération (spec §8.4) : l'opération, sa ventilation
        confirmée ou la proposition, sa pièce, le niveau."""
        _check(member)
        op = self._operation(db, member.org_id, operation_id)
        account = db.get(FinAccount, op.account_id)
        by_id = {a.id: a for a in self.accounts(db, member.org_id)}
        confirmed = self._lines(db, member.org_id).get(op.id, [])
        proposal = None
        if not confirmed and op.transfer_id is None:
            proposal = propose(
                self.accounts(db, member.org_id, active_only=True), op.label, op.details, op.amount, self._history(db, member.org_id)
            )
        pieces = self.pieces(db, member.org_id) if self.pieces is not None else {}
        return {
            "id": op.id,
            "date": op.date.isoformat(),
            "label": op.label,
            "details": op.details,
            "amount": op.amount / 100,
            "bankAccount": {"id": account.id, "name": account.name},
            "transfer": op.transfer_id is not None,
            "lines": [
                {
                    "accountId": line.account_id,
                    "number": by_id[line.account_id].number,
                    "label": by_id[line.account_id].label,
                    "amount": line.amount / 100,
                    "confirmedAt": line.confirmed_at.isoformat(),
                }
                for line in confirmed
            ],
            "proposal": self._proposal(by_id, proposal),
            "piece": pieces.get(op.id),
            "level": self.level(db, member.org_id),
        }

    def set_lines(self, db: Session, member: Member, operation_id: int, lines: list[dict]) -> dict:
        """Le trésorier confirme le compte d'une opération, ou sa ventilation
        sur plusieurs comptes ({"accountId", "amount" en euros}) : la somme
        doit faire le montant de la banque. Liste vide : on retire le compte."""
        _check(member)
        op = self._operation(db, member.org_id, operation_id)
        if op.transfer_id is not None:
            raise AccountingError("Un virement entre vos comptes n'a pas de compte du plan.")
        by_id = {a.id: a for a in self.accounts(db, member.org_id, active_only=True)}
        cleaned = []
        for line in lines:
            account_id = int(line.get("accountId", 0))
            if account_id not in by_id:
                raise AccountingError("Compte inconnu ou inactif.")
            amount = round(float(line.get("amount", op.amount / 100)) * 100) if len(lines) > 1 else op.amount
            if amount == 0:
                raise AccountingError("Une ligne de ventilation ne peut pas être à zéro.")
            cleaned.append((account_id, amount))
        if cleaned and sum(a for _, a in cleaned) != op.amount:
            raise AccountingError("La ventilation ne fait pas le montant de la banque.")
        for old in db.scalars(select(FinOperationAccount).where(FinOperationAccount.operation_id == op.id)):
            db.delete(old)
        db.add_all(
            FinOperationAccount(operation_id=op.id, account_id=account_id, amount=amount, confirmed_by=member.person_id)
            for account_id, amount in cleaned
        )
        db.commit()
        return self.operation(db, member, op.id)

    def counts(self, db: Session, org_id: int, rows: list[dict]) -> dict:
        """Compteurs des puces « Sans compte » et « Sans pièce » (§8.4)."""
        real = [r for r in rows if not r.get("transfer")]
        return {"withoutAccount": sum(r["account"] is None for r in real), "withoutPiece": sum(r["piece"] is None for r in real)}

    # ----- caisse -----

    def cash(self, db: Session, member: Member) -> dict:
        """La caisse : solde et lignes, la plus récente en premier."""
        _check(member)
        by_id = {a.id: a for a in self.accounts(db, member.org_id)}
        lines = list(
            db.scalars(
                select(FinCashLine)
                .where(FinCashLine.org_id == member.org_id)
                .order_by(FinCashLine.date.desc(), FinCashLine.id.desc())
            )
        )
        balance = sum(line.amount for line in lines)
        return {
            "balance": balance / 100,
            "asOf": lines[0].date.isoformat() if lines else None,
            "lines": [
                {
                    "id": line.id,
                    "date": line.date.isoformat(),
                    "label": line.label,
                    "amount": line.amount / 100,
                    "account": (
                        {"id": line.account_id, "number": by_id[line.account_id].number, "label": by_id[line.account_id].label}
                        if line.account_id in by_id
                        else None
                    ),
                    "transferOperationId": line.transfer_operation_id,
                    "docNodeId": line.doc_node_id,
                }
                for line in lines
            ],
        }

    def add_cash_line(self, db: Session, member: Member, data: dict) -> dict:
        _check(member)
        try:
            day = dt.date.fromisoformat(str(data.get("date", "")))
        except ValueError as exc:
            raise AccountingError("Date invalide.") from exc
        label = str(data.get("label", "")).strip()[:120]
        if not label:
            raise AccountingError("Donnez un libellé à la ligne.")
        amount = round(float(data.get("amount", 0)) * 100)
        if amount == 0:
            raise AccountingError("Le montant ne peut pas être à zéro.")
        account_id = data.get("accountId")
        transfer_id = data.get("transferOperationId")
        if transfer_id is not None:
            # Retrait au distributeur : virement interne banque → caisse,
            # même montant, pas de compte du plan.
            op = self._operation(db, member.org_id, int(transfer_id))
            if op.amount != -amount:
                raise AccountingError("Le retrait de la banque n'a pas ce montant.")
            account_id = None
        elif account_id is not None:
            account = self._chart_account(db, member.org_id, int(account_id))
            if not account.active:
                raise AccountingError("Compte inactif.")
            account_id = account.id
        line = FinCashLine(
            org_id=member.org_id,
            date=day,
            label=label,
            amount=amount,
            account_id=account_id,
            transfer_operation_id=int(transfer_id) if transfer_id is not None else None,
            doc_node_id=data.get("docNodeId"),
            created_by=member.person_id,
        )
        db.add(line)
        db.commit()
        return self.cash(db, member)

    def delete_cash_line(self, db: Session, member: Member, line_id: int) -> dict:
        _check(member)
        line = db.get(FinCashLine, line_id)
        if line is None or line.org_id != member.org_id:
            raise LookupError("Ligne inconnue")
        db.delete(line)
        db.commit()
        return self.cash(db, member)
