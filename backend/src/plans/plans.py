"""Les formules d'une saison (spec/core.md §9.1) : lister, créer, modifier,
dupliquer, retirer, et les recopier d'une saison à l'autre."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import SeasonPlan, SeasonPlanInstallment


class PlanError(ValueError):
    """Message lisible, renvoyé tel quel à l'écran."""


def plans(db: Session, org_id: int, season_id: int) -> list[SeasonPlan]:
    return list(
        db.scalars(
            select(SeasonPlan)
            .where(SeasonPlan.org_id == org_id, SeasonPlan.season_id == season_id)
            .order_by(SeasonPlan.position, SeasonPlan.id)
        )
    )


def _set(plan: SeasonPlan, name: str, price: int, active: bool, installments: list[tuple[dt.date | None, int]]) -> None:
    name = (name or "").strip()
    if not name:
        raise PlanError("Le nom de la formule est obligatoire")
    if price < 0 or any(amount < 0 for _, amount in installments):
        raise PlanError("Un montant ne peut pas être négatif")
    if not installments:
        installments = [(None, price)]
    if sum(amount for _, amount in installments) != price:
        raise PlanError("Les échéances doivent faire le tarif")
    plan.name, plan.price, plan.active = name, price, active
    plan.installments = [
        SeasonPlanInstallment(position=i, due_on=due_on, amount=amount) for i, (due_on, amount) in enumerate(installments)
    ]


def create(db: Session, org_id: int, season_id: int, name: str, price: int, active: bool = True,
           installments: list[tuple[dt.date | None, int]] = (), position: int | None = None) -> SeasonPlan:
    """Nouvelle formule, à la fin de la liste (ou à `position`), sans commit."""
    if position is None:
        last = db.scalar(
            select(func.max(SeasonPlan.position)).where(SeasonPlan.org_id == org_id, SeasonPlan.season_id == season_id)
        )
        position = (last or 0) + 1
    plan = SeasonPlan(org_id=org_id, season_id=season_id, position=position)
    _set(plan, name, price, active, list(installments))
    db.add(plan)
    db.flush()
    return plan


def update(plan: SeasonPlan, name: str, price: int, active: bool, installments: list[tuple[dt.date | None, int]]) -> None:
    _set(plan, name, price, active, list(installments))


def duplicate(db: Session, plan: SeasonPlan) -> SeasonPlan:
    """« Dupliquer » : la copie se place juste après."""
    for other in plans(db, plan.org_id, plan.season_id):
        if other.position > plan.position:
            other.position += 1
    return create(
        db, plan.org_id, plan.season_id, f"{plan.name} (copie)", plan.price, plan.active,
        [(i.due_on, i.amount) for i in plan.installments], position=plan.position + 1,
    )


def copy_season(db: Session, org_id: int, old_season_id: int, new_season_id: int) -> list[SeasonPlan]:
    """Les formules d'une saison recopiées dans une autre, échéances datées
    décalées d'un an (sans commit)."""

    def next_year(day: dt.date | None) -> dt.date | None:
        if day is None:
            return None
        try:
            return day.replace(year=day.year + 1)
        except ValueError:  # 29 février
            return day.replace(year=day.year + 1, day=28)

    return [
        create(
            db, org_id, new_season_id, old.name, old.price, old.active,
            [(next_year(i.due_on), i.amount) for i in old.installments], position=old.position,
        )
        for old in plans(db, org_id, old_season_id)
    ]
