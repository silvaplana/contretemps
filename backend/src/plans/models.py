"""Tables `season_plans` (une formule : ce qu'un membre choisit pour la
saison) et `season_plan_installments` (ses échéances, dont la somme fait le
tarif). Montants en centimes, comme le Financier."""

from datetime import date, datetime, timezone

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String
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


class SeasonPlanInstallment(Base):
    __tablename__ = "season_plan_installments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("season_plans.id", ondelete="CASCADE"), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Vide : « À l'inscription ».
    due_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
