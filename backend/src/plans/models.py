"""Tables `season_plans` (une formule : ce qu'un membre choisit pour la
saison), `season_plan_installments` (ses échéances, dont la somme fait le
tarif), `season_adjustments` (options et codes promo) et
`season_adjustment_plans` (les formules d'une option, aucune = toutes).
Montants en centimes, comme le Financier."""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SeasonPlan(Base):
    __tablename__ = "season_plans"
    __table_args__ = (Index("ix_season_plans_org_season", "org_id", "season_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    # « Proposée cette saison ».
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    installments: Mapped[list["SeasonPlanInstallment"]] = relationship(
        order_by="SeasonPlanInstallment.position", cascade="all, delete-orphan"
    )
    # Ses liens vers les options : effacés avec elle (SQLite sans clés étrangères actives).
    adjustments: Mapped[list["SeasonAdjustment"]] = relationship(
        secondary="season_adjustment_plans", back_populates="plans"
    )


class SeasonPlanInstallment(Base):
    __tablename__ = "season_plan_installments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("season_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Vide : « À l'inscription ».
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)


season_adjustment_plans = Table(
    "season_adjustment_plans",
    Base.metadata,
    Column("adjustment_id", ForeignKey("season_adjustments.id", ondelete="CASCADE"), primary_key=True),
    Column("plan_id", ForeignKey("season_plans.id", ondelete="CASCADE"), primary_key=True, index=True),
)


class SeasonAdjustment(Base):
    """Une option ou un code promo (spec/core.md §9.2) : un montant en plus ou
    en moins, en € ou en %, obtenu en cochant ou avec un code."""

    __tablename__ = "season_adjustments"
    __table_args__ = (Index("ix_season_adjustments_org_season", "org_id", "season_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("ecoles.id"), nullable=False)
    season_id: Mapped[int] = mapped_column(ForeignKey("saisons.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Négatif = en moins. En centimes (« eur ») ou en centièmes de % (« pct »).
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    unit: Mapped[str] = mapped_column(String(3), nullable=False, default="eur")
    # Comment l'obtenir : « check » (la personne coche), « code » ou « rule ».
    mode: Mapped[str] = mapped_column(String(10), nullable=False, default="check")
    code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Code montré dans le formulaire (la personne le coche) ou secret (elle le tape).
    shown: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    until: Mapped[date | None] = mapped_column(Date, nullable=True)
    # À cocher : quantité limitée.
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Règle (étape 7c) : écrite en français, redite par l'assistant
    # (« Compris : … ») et son calcul (rules.py), qui donne le montant.
    rule: Mapped[str | None] = mapped_column(Text, nullable=True)
    understood: Mapped[str | None] = mapped_column(Text, nullable=True)
    calculation: Mapped[str | None] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)

    plans: Mapped[list[SeasonPlan]] = relationship(
        secondary=season_adjustment_plans, order_by=SeasonPlan.position, back_populates="adjustments"
    )

    @property
    def plan_ids(self) -> list[int]:
        return [plan.id for plan in self.plans]
