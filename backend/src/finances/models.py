"""Tables du sous-module Comptes du module finances (spec/modules/
financier.md §3) : comptes bancaires, relevés importés, opérations.

Comme les autres modules : aucune clé étrangère vers l'appli hôte, `org_id`
est un simple entier fourni par le port (voir ports.py). Pas de `saison_id`,
un historique bancaire traverse les saisons.

Montants en centimes entiers (un relevé doit tomber juste au centime).
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Origine d'une opération : un relevé importé, ou (plus tard) la connexion
# bancaire, dont les opérations sont provisoires jusqu'au relevé.
SOURCE_STATEMENT = "releve"
SOURCE_BANK = "banque"


class FinAccount(Base):
    __tablename__ = "fin_accounts"
    __table_args__ = (UniqueConstraint("org_id", "number", name="uq_fin_accounts_org_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(34), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # "checking" (compte courant) ou "savings" (livret).
    kind: Mapped[str] = mapped_column(String(20), nullable=False)


class FinStatement(Base):
    __tablename__ = "fin_statements"
    __table_args__ = (UniqueConstraint("account_id", "start_date", "end_date", name="uq_fin_statements_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("fin_accounts.id"), nullable=False, index=True)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    start_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class FinOperation(Base):
    __tablename__ = "fin_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("fin_accounts.id"), nullable=False, index=True)
    statement_id: Mapped[int | None] = mapped_column(ForeignKey("fin_statements.id", ondelete="CASCADE"), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default=SOURCE_STATEMENT)
    # Rang dans le relevé : l'ordre de la banque pour un même jour.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Opération jumelle d'un virement entre deux comptes de l'organisation.
    transfer_id: Mapped[int | None] = mapped_column(ForeignKey("fin_operations.id", ondelete="SET NULL"), nullable=True)


# États d'un bilan (un seul officiel par saison).
DRAFT = "brouillon"
VALIDATED = "valide"
OFFICIAL = "officiel"
STATES = {DRAFT: "Brouillon", VALIDATED: "Validé", OFFICIAL: "Officiel"}


class FinReport(Base):
    """Bilan financier d'une saison (sous-module Bilan, spec §4) : un calcul
    enregistré, avec son nom, son état, les consignes et le modèle du
    dernier calcul, son coût cumulé et son résultat (JSON : tableau +
    analyse). `season_id` est l'id d'une saison fournie par le port
    `seasons` (pas de clé étrangère : le module ne connaît pas la table)."""

    __tablename__ = "fin_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=DRAFT)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(40), nullable=False)
    # Coût cumulé des appels à l'IA, en dollars (affiché en euros, comme
    # l'assistant).
    ai_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "idle", "running" (calcul en cours depuis run_started_at) ou "error".
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="idle")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
