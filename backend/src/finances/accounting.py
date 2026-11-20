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

from .chart import CLASSES, DEFAULT_CHART, Proposal, is_cheque_deposit, label_key, normalize, official_natures, propose
from .models import (
    FULL,
    LEVELS,
    NATURES,
    SIMPLE,
    THIRD_PARTY,
    FinAccount,
    FinCashLine,
    FinChartAccount,
    FinClosing,
    FinOperation,
    FinOperationAccount,
    FinChartSnapshot,
    FinSettings,
)
from .ports import Member

# Mots de la banque qui ne nomment personne (« VIR SEPA MAIRIE » → « MAIRIE »).
BANK_WORDS = {"VIR", "VIREMENT", "SEPA", "INST", "PRLV", "PRELEVEMENT", "CARTE", "CB", "PAIEMENT", "ACHAT", "FACT", "FACTURE", "RECU", "EMIS"}

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
    def __init__(
        self,
        pieces: Callable[[Session, int], dict[int, dict]] | None = None,
        justified: Callable[[Session, int], set[int]] | None = None,
    ) -> None:
        """pieces(db, org_id) : la pièce rattachée à chaque opération
        bancaire ({operation_id: {"id", "title", "kind"}}), fournie par
        l'appli hôte (les dépenses du module notes de frais) ;
        justified(db, org_id) : les opérations justifiées sans facture."""
        self.pieces = pieces
        self.justified = justified

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
                raise AccountingError("On ne revient pas d'Engagement à Trésorerie.")
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
            "snapshots": [self._snapshot(s) for s in self._snapshots(db, member.org_id)],
            "snapshotSuggestion": self.suggest_snapshot_comment(db, member.org_id),
            "natures": [{"id": n, "label": NATURE_LABELS[n]} for n in NATURES],
            "officialNatures": official_natures(),
            "classes": [{"id": c, "label": label} for c, label in CLASSES],
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
            "natureLabel": a.nature_label,
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
        # Nature libre : un nom au choix, le calcul suit `nature` (Seb, 10/11).
        if "natureLabel" in data:
            nature_label = " ".join(str(data.get("natureLabel") or "").split())[:40] or None
        else:
            nature_label = current.nature_label if current else None
        taken = db.scalar(
            select(FinChartAccount.id).where(FinChartAccount.org_id == org_id, FinChartAccount.number == number)
        )
        if taken is not None and (current is None or taken != current.id):
            raise AccountingError(f"Le compte {number} existe déjà.")
        keywords = [str(k).strip() for k in data.get("keywords") or [] if str(k).strip()]
        event = (data.get("event") or "").strip()[:40] or None
        return {"number": number, "label": label, "nature": nature, "nature_label": nature_label, "keywords": keywords, "event": event}

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
        """Supprime un compte jamais utilisé ; sinon le passe inactif. Un
        compte de tiers (401, 467x) sert par les pièces, pas par les lignes :
        il devient inactif, son numéro ne se libère jamais (Seb, 10/11)."""
        _check(member)
        account = self._chart_account(db, member.org_id, account_id)
        if self._used(db, account.id) or account.nature == THIRD_PARTY:
            account.active = False
        else:
            db.delete(account)
        db.commit()

    # ----- copies mémorisées du plan (§8.7) -----

    def _snapshots(self, db: Session, org_id: int) -> list[FinChartSnapshot]:
        """Les copies, la plus récente d'abord."""
        return list(db.scalars(select(FinChartSnapshot).where(FinChartSnapshot.org_id == org_id).order_by(FinChartSnapshot.taken_at.desc(), FinChartSnapshot.id.desc())))

    @staticmethod
    def _snapshot(s: FinChartSnapshot) -> dict:
        return {"id": s.id, "takenAt": s.taken_at.isoformat(), "comment": s.comment, "accounts": len(s.accounts)}

    def _chart_as_saved(self, db: Session, org_id: int) -> list[dict]:
        return [
            {("nature_label" if k == "natureLabel" else k): v for k, v in self._account(a).items() if k != "id"}
            for a in self.accounts(db, org_id)
        ]

    def suggest_snapshot_comment(self, db: Session, org_id: int) -> str:
        """Le commentaire pré-rempli de « Mémoriser » : ce qui a changé depuis
        la copie précédente (comptes ajoutés, retirés, renommés, désactivés),
        calculé, jamais inventé. Première copie : « Plan de départ »."""
        snapshots = self._snapshots(db, org_id)
        if not snapshots:
            return "Plan de départ"
        before = {a["number"]: a for a in snapshots[0].accounts}
        now = {a["number"]: a for a in self._chart_as_saved(db, org_id)}
        parts = []
        added = [f"{n} {now[n]['label']}" for n in sorted(now) if n not in before]
        removed = [f"{n} {before[n]['label']}" for n in sorted(before) if n not in now]
        relabelled = [n for n in sorted(now) if n in before and now[n]["label"] != before[n]["label"]]
        toggled = [n for n in sorted(now) if n in before and now[n]["active"] != before[n]["active"]]
        for items, singular, plural in (
            (added, "compte ajouté", "comptes ajoutés"),
            (removed, "compte retiré", "comptes retirés"),
            (relabelled, "libellé modifié", "libellés modifiés"),
            (toggled, "compte activé ou désactivé", "comptes activés ou désactivés"),
        ):
            if items:
                parts.append(f"{len(items)} {plural if len(items) > 1 else singular} ({', '.join(items[:4])}{'…' if len(items) > 4 else ''})")
        return ", ".join(parts) if parts else "Aucun changement depuis la copie précédente"

    def memorize_chart(self, db: Session, member: Member, comment: str = "") -> dict:
        """« Mémoriser le plan comptable » (§8.7, Seb 10/11) : une copie de
        plus dans le journal, avec son commentaire (sinon la suggestion) ;
        « Repartir à zéro » en remet une."""
        _check(member)
        comment = " ".join(comment.split())[:200] or self.suggest_snapshot_comment(db, member.org_id)
        snapshot = FinChartSnapshot(org_id=member.org_id, comment=comment, accounts=self._chart_as_saved(db, member.org_id))
        db.add(snapshot)
        db.commit()
        return self._snapshot(snapshot)

    def restore_chart(self, db: Session, member: Member, snapshot_id: int | None = None) -> dict | None:
        """Remet le plan comme à une copie (la plus récente sans `snapshot_id`) :
        libellés, natures, mots-clés et actif repris par numéro, comptes
        retirés depuis recréés, comptes ajoutés depuis supprimés (inactifs
        s'ils ont servi). Rend la copie remise, None sans copie."""
        _check(member)
        snapshots = self._snapshots(db, member.org_id)
        if snapshot_id is None:
            snapshot = snapshots[0] if snapshots else None
        else:
            snapshot = next((s for s in snapshots if s.id == snapshot_id), None)
            if snapshot is None:
                raise LookupError("Copie du plan inconnue")
        if snapshot is None:
            return None
        existing = {a.number: a for a in self.accounts(db, member.org_id)}
        for saved in snapshot.accounts:
            account = existing.pop(saved["number"], None)
            if account is None:
                db.add(FinChartAccount(org_id=member.org_id, **saved))
            else:
                for key, value in saved.items():
                    setattr(account, key, value)
        for account in existing.values():
            if self._used(db, account.id):
                account.active = False
            else:
                db.delete(account)
        db.commit()
        return self._snapshot(snapshot)

    def _used(self, db: Session, account_id: int) -> int:
        used = db.scalar(select(func.count()).select_from(FinOperationAccount).where(FinOperationAccount.account_id == account_id))
        return used + db.scalar(select(func.count()).select_from(FinCashLine).where(FinCashLine.account_id == account_id))

    # ----- compte sur chaque ligne -----

    @staticmethod
    def closing_of(db: Session, org_id: int, day: dt.date) -> FinClosing | None:
        """La clôture en vigueur de la saison qui contient ce jour (§8.7) :
        ses lignes sont validées, le cadenas du Grand livre."""
        return db.scalar(
            select(FinClosing).where(
                FinClosing.org_id == org_id, FinClosing.reopened_at.is_(None),
                FinClosing.start_date <= day, FinClosing.end_date >= day,
            )
        )

    def check_open(self, db: Session, org_id: int, day: dt.date) -> None:
        """Refuse un changement daté dans une saison clôturée (§8.7) tant
        qu'elle n'est pas rouverte."""
        if self.closing_of(db, org_id, day) is not None:
            raise AccountingError("Saison clôturée : rouvrez-la (Bilan › Préparer, étape 7) pour changer cette ligne.")

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
        """{clé de libellé: Counter(account_id)} des opérations confirmées par
        le trésorier sur un seul compte (une ventilation ne fait pas une
        habitude, la catégorisation automatique non plus)."""
        history: dict[str, Counter] = {}
        operations = {o.id: o for o in db.scalars(select(FinOperation).join(FinAccount).where(FinAccount.org_id == org_id))}
        for operation_id, lines in self._lines(db, org_id).items():
            if len(lines) != 1 or lines[0].auto:
                continue
            key = label_key(operations[operation_id].label)
            if key:
                history.setdefault(key, Counter())[lines[0].account_id] += 1
        return history

    def _split_habit(self, db: Session, org_id: int) -> list[int]:
        """Les comptes entre lesquels les remises de chèques déjà ventilées ont
        été partagées, du plus fréquent au plus rare : la proposition de
        ventilation de la prochaine remise."""
        operations = {o.id: o for o in db.scalars(select(FinOperation).join(FinAccount).where(FinAccount.org_id == org_id))}
        counter: Counter = Counter()
        for operation_id, lines in self._lines(db, org_id).items():
            op = operations.get(operation_id)
            if op is not None and len(lines) > 1 and is_cheque_deposit(op.label, op.details):
                counter.update(line.account_id for line in lines)
        return [account_id for account_id, _ in counter.most_common()]

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
        justified = self.justified(db, org_id) if self.justified is not None else set()
        for row in rows:
            row["account"] = row["proposal"] = row["piece"] = None
            row["justified"] = row["id"] in justified
            if row.get("transfer"):
                continue
            confirmed = lines.get(row["id"])
            if confirmed:
                first = by_id[confirmed[0].account_id]
                row["account"] = {
                    "id": first.id, "number": first.number, "label": first.label, "split": len(confirmed) > 1,
                    "auto": all(l.auto for l in confirmed),
                }
            else:
                proposal = _from_piece(accounts, pieces.get(row["id"]), row["amount"]) or propose(
                    accounts, row["label"], row.get("details", ""), round(row["amount"] * 100), history
                )
                row["proposal"] = self._proposal(by_id, proposal)
            row["piece"] = pieces.get(row["id"])
            # Ce qui reste à justifier (Seb, 20/11) : les pièces rattachées ne font pas tout le montant.
            piece_cents = round(abs(float(row["piece"].get("amount") or 0)) * 100) if row["piece"] else 0
            row["toJustify"] = max(abs(round(row["amount"] * 100)) - piece_cents, 0) / 100 if row["piece"] else 0
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
        pieces = self.pieces(db, member.org_id) if self.pieces is not None else {}
        if not confirmed and op.transfer_id is None:
            active = self.accounts(db, member.org_id, active_only=True)
            proposal = _from_piece(active, pieces.get(op.id), op.amount) or propose(
                active, op.label, op.details, op.amount, self._history(db, member.org_id)
            )
        cheque = op.transfer_id is None and is_cheque_deposit(op.label, op.details)
        suggestion = []
        if cheque and not confirmed:
            habit = [by_id[i] for i in self._split_habit(db, member.org_id) if i in by_id and by_id[i].active]
            suggestion = [{"id": a.id, "number": a.number, "label": a.label} for a in habit]
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
            # Saison clôturée (§8.7) : la ligne est validée, elle ne change plus.
            "closed": self.closing_of(db, member.org_id, op.date) is not None,
            "level": self.level(db, member.org_id),
            "chequeDeposit": cheque,
            "splitSuggestion": suggestion,
        }

    def set_lines(self, db: Session, member: Member, operation_id: int, lines: list[dict]) -> dict:
        """Le trésorier confirme le compte d'une opération, ou sa ventilation
        sur plusieurs comptes ({"accountId", "amount" en euros}) : la somme
        doit faire le montant de la banque. Liste vide : on retire le compte."""
        _check(member)
        op = self._operation(db, member.org_id, operation_id)
        if op.transfer_id is not None:
            raise AccountingError("Un virement entre vos comptes n'a pas de compte du plan.")
        self.check_open(db, member.org_id, op.date)
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

    # ----- « Proposer des comptes » (§8.2, Seb 20/11) -----

    def _groups(self, db: Session, org_id: int) -> list[dict]:
        """Dans un compte de dépenses ou de recettes, les transactions des
        douze derniers mois qui portent le même nom et reviennent au moins
        trois fois, sans être tout le compte : de quoi faire un sous-compte.
        Règles fixes, pas de modèle ; l'appli propose, la trésorière décide."""
        accounts = {a.id: a for a in self.accounts(db, org_id, active_only=True)}
        taken = {a.number for a in self.accounts(db, org_id)}
        operations = {o.id: o for o in db.scalars(select(FinOperation).join(FinAccount).where(FinAccount.org_id == org_id))}
        if not operations:
            return []
        since = max(o.date for o in operations.values()) - dt.timedelta(days=365)
        by_account: dict[int, dict[str, list[FinOperation]]] = {}
        for operation_id, lines in self._lines(db, org_id).items():
            op = operations[operation_id]
            account = accounts.get(lines[0].account_id)
            if len(lines) != 1 or account is None or account.nature not in ("depense", "recette") or op.date < since:
                continue
            name = " ".join(w for w in label_key(op.label).split() if w not in BANK_WORDS)
            if name and self.closing_of(db, org_id, op.date) is None:
                by_account.setdefault(account.id, {}).setdefault(name, []).append(op)
        groups = []
        for account_id, names in sorted(by_account.items(), key=lambda item: accounts[item[0]].number):
            parent = accounts[account_id]
            total = sum(len(ops) for ops in names.values())
            for name, ops in sorted(names.items(), key=lambda item: -len(item[1])):
                # Déjà un mot-clé d'un compte : la proposition est faite.
                if len(ops) < 3 or len(ops) == total or any(name in (normalize(k) for k in a.keywords or []) for a in accounts.values()):
                    continue
                number = next((parent.number + str(d) for d in range(1, 10) if parent.number + str(d) not in taken), None)
                if number is None or len(number) > 10:
                    continue
                taken.add(number)
                groups.append({"parent": parent, "number": number, "name": name, "operations": ops})
        return groups

    def propose_accounts(self, db: Session, member: Member) -> list[dict]:
        """Les sous-comptes proposés : rien n'est créé avant « Créer les comptes cochés »."""
        _check(member)
        out = []
        for g in self._groups(db, member.org_id):
            amounts = {abs(o.amount) for o in g["operations"]}
            out.append({
                "number": g["number"],
                "label": g["name"].title(),
                "parentId": g["parent"].id,
                "parent": f"{g['parent'].number} {g['parent'].label}",
                "parentNumber": g["parent"].number,
                "key": g["name"],
                "count": len(g["operations"]),
                "sameAmount": amounts.pop() / 100 if len(amounts) == 1 else None,
            })
        return out

    def create_proposed(self, db: Session, member: Member, items: list[dict]) -> dict:
        """Crée les comptes cochés (nom au choix), avec leur mot-clé, et y passe
        leurs transactions. Renvoie de quoi annuler : [{id, parentId}]."""
        _check(member)
        groups = {(g["parent"].id, g["name"]): g for g in self._groups(db, member.org_id)}
        created, moved = [], 0
        for item in items:
            g = groups.get((int(item.get("parentId", 0)), str(item.get("key", ""))))
            if g is None:
                raise AccountingError("Cette proposition n'est plus d'actualité : rouvrez « Proposer des comptes ».")
            data = {"number": g["number"], "label": str(item.get("label") or "").strip() or g["name"].title(), "nature": g["parent"].nature, "keywords": [g["name"]]}
            account = FinChartAccount(org_id=member.org_id, **self._validate(db, member.org_id, data))
            db.add(account)
            db.flush()
            ids = [o.id for o in g["operations"]]
            for line in db.scalars(select(FinOperationAccount).where(FinOperationAccount.operation_id.in_(ids), FinOperationAccount.account_id == g["parent"].id)):
                line.account_id = account.id
                moved += 1
            created.append({"id": account.id, "parentId": g["parent"].id})
        db.commit()
        return {"created": created, "moved": moved}

    def undo_proposed(self, db: Session, member: Member, created: list[dict]) -> None:
        """« Annuler » juste après : les transactions reviennent au compte d'avant, les comptes créés disparaissent."""
        _check(member)
        for item in created:
            account = self._chart_account(db, member.org_id, int(item["id"]))
            parent = self._chart_account(db, member.org_id, int(item["parentId"]))
            for line in db.scalars(select(FinOperationAccount).where(FinOperationAccount.account_id == account.id)):
                line.account_id = parent.id
            db.flush()
            if not self._used(db, account.id):
                db.delete(account)
        db.commit()

    def confirm_many(self, db: Session, member: Member, operation_ids: list[int], account_id: int) -> int:
        """« Valider le compte » (financier.md §8.10, étape 3) : le même compte
        confirmé d'un coup sur plusieurs opérations encore sans compte. Une
        opération déjà classée ou un virement interne est laissé tel quel.
        Renvoie le nombre d'opérations confirmées."""
        _check(member)
        done = 0
        lines = self._lines(db, member.org_id)
        for operation_id in operation_ids:
            op = self._operation(db, member.org_id, operation_id)
            if op.transfer_id is not None or (lines.get(op.id) and not all(l.auto for l in lines[op.id])):
                continue
            self.set_lines(db, member, op.id, [{"accountId": account_id}])
            done += 1
        return done

    def auto_classify(self, db: Session, org_id: int) -> int:
        """Catégorisation automatique (Seb, 20/11, comme les logiciels du
        métier) : à l'arrivée des transactions, une transaction sans compte,
        sans pièce, hors remise de chèques et hors saison clôturée, reçoit le
        compte proposé quand la proposition est sûre (une habitude du
        trésorier, au moins deux fois, ou un mot-clé du compte), marqué
        `auto`. Rend le nombre de transactions catégorisées."""
        accounts = self.accounts(db, org_id, active_only=True)
        if not accounts:
            return 0
        lines = self._lines(db, org_id)
        history = self._history(db, org_id)
        pieces = self.pieces(db, org_id) if self.pieces is not None else {}
        done = 0
        for op in db.scalars(select(FinOperation).join(FinAccount).where(FinAccount.org_id == org_id)):
            if op.transfer_id is not None or op.id in lines or op.id in pieces or not op.amount:
                continue
            if is_cheque_deposit(op.label, op.details or "") or self.closing_of(db, org_id, op.date) is not None:
                continue
            proposal = propose(accounts, op.label, op.details or "", op.amount, history)
            if proposal is None:
                continue
            # Habitude sûre : au moins deux fois ce compte, jamais un autre.
            if proposal.history and (proposal.history < 2 or len(history.get(label_key(op.label), ())) > 1):
                continue
            db.add(FinOperationAccount(operation_id=op.id, account_id=proposal.account_id, amount=op.amount, confirmed_by=None, auto=True))
            done += 1
        db.flush()
        return done

    def counts(self, db: Session, org_id: int, rows: list[dict]) -> dict:
        """Compteurs des puces « À catégoriser » (pas de compte) et « Justificatif
        manquant » (un compte, ni justification sans facture ni pièces qui font
        tout le montant) (§8.4)."""
        real = [r for r in rows if not r.get("transfer")]
        return {
            "withoutAccount": sum(r["account"] is None for r in real),
            "withoutPiece": sum(
                r["account"] is not None and not r.get("justified") and (r["piece"] is None or r.get("toJustify", 0) > 0) for r in real
            ),
        }

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
        self.check_open(db, member.org_id, day)
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
        self.check_open(db, member.org_id, line.date)
        db.delete(line)
        db.commit()
        return self.cash(db, member)


def _from_piece(accounts: list, piece: dict | None, amount) -> Proposal | None:
    """Le compte de la catégorie de la pièce rattachée (une dépense classée
    « 6063 Autres fournitures » dans sa note), pour une sortie d'argent ;
    pour une entrée, le compte de la vente rattachée (§8.12)."""
    number = (piece or {}).get("account")
    if not number or (amount > 0) != (piece.get("nature") == "vente"):
        return None
    account = next((a for a in accounts if a.number == number), None)
    if account is None:
        return None
    return Proposal(account.id, f"la pièce « {piece['title']} » est classée dans ce compte")
