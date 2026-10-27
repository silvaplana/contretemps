"""Les tarifs d'une saison (spec/core.md §9) : les formules (§9.1) et les
options et codes promo (§9.2) ; lister, créer, modifier, dupliquer, retirer,
et les recopier d'une saison à l'autre."""

from __future__ import annotations

import datetime as dt

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import SeasonAdjustment, SeasonPlan, SeasonPlanInstallment


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


def adjustments(db: Session, org_id: int, season_id: int) -> list[SeasonAdjustment]:
    return list(
        db.scalars(
            select(SeasonAdjustment)
            .where(SeasonAdjustment.org_id == org_id, SeasonAdjustment.season_id == season_id)
            .order_by(SeasonAdjustment.position, SeasonAdjustment.id)
        )
    )


def set_adjustment(db: Session, adjustment: SeasonAdjustment, **values) -> None:
    """Vérifie et range les réglages d'une option ou d'un code promo.
    `plan_ids` : ses formules (vide = toutes)."""
    name = (values.get("name") or "").strip()
    if not name:
        raise PlanError("Le nom est obligatoire")
    mode, unit, amount = values["mode"], values["unit"], values["amount"]
    if mode not in ("check", "code") or unit not in ("eur", "pct"):
        raise PlanError("Réglage inconnu")
    if amount == 0:
        raise PlanError("Le montant est obligatoire")
    if unit == "pct" and abs(amount) > 10000:
        raise PlanError("Un pourcentage ne dépasse pas 100 %")
    code = (values.get("code") or "").strip().upper() or None
    if mode == "code":
        if not code:
            raise PlanError("Le code est obligatoire")
        doublon = db.scalar(
            select(SeasonAdjustment.id).where(
                SeasonAdjustment.org_id == adjustment.org_id, SeasonAdjustment.season_id == adjustment.season_id,
                SeasonAdjustment.code == code, SeasonAdjustment.id != adjustment.id,
            )
        )
        if doublon is not None:
            raise PlanError(f"Le code {code} existe déjà")
    plan_ids = values.get("plan_ids") or []
    chosen = [
        plan for plan in plans(db, adjustment.org_id, adjustment.season_id) if plan.id in plan_ids
    ]
    if len(chosen) != len(set(plan_ids)):
        raise PlanError("Formule inconnue")
    adjustment.name, adjustment.amount, adjustment.unit, adjustment.mode = name, amount, unit, mode
    adjustment.code = code if mode == "code" else None
    adjustment.shown = bool(values.get("shown")) if mode == "code" else False
    adjustment.max_uses = values.get("max_uses") if mode == "code" else None
    adjustment.until = values.get("until") if mode == "code" else None
    adjustment.quantity = values.get("quantity") if mode == "check" else None
    adjustment.active = values.get("active", True)
    adjustment.plans = chosen


def create_adjustment(db: Session, org_id: int, season_id: int, position: int | None = None, **values) -> SeasonAdjustment:
    """Nouvelle option ou nouveau code promo, à la fin (ou à `position`), sans commit."""
    if position is None:
        last = db.scalar(
            select(func.max(SeasonAdjustment.position)).where(
                SeasonAdjustment.org_id == org_id, SeasonAdjustment.season_id == season_id
            )
        )
        position = (last or 0) + 1
    adjustment = SeasonAdjustment(org_id=org_id, season_id=season_id, position=position)
    set_adjustment(db, adjustment, **values)
    db.add(adjustment)
    db.flush()
    return adjustment


def _next_year(day: dt.date | None) -> dt.date | None:
    if day is None:
        return None
    try:
        return day.replace(year=day.year + 1)
    except ValueError:  # 29 février
        return day.replace(year=day.year + 1, day=28)


def copy_season(
    db: Session, org_id: int, old_season_id: int, new_season_id: int
) -> tuple[list[SeasonPlan], list[SeasonAdjustment]]:
    """Les tarifs d'une saison recopiés dans une autre, dates (échéances,
    date limite d'un code) décalées d'un an (sans commit)."""
    same: dict[int, SeasonPlan] = {}
    for old in plans(db, org_id, old_season_id):
        new = create(
            db, org_id, new_season_id, old.name, old.price, old.active,
            [(_next_year(i.due_on), i.amount) for i in old.installments], position=old.position,
        )
        same[old.id] = new
    copied_adjustments = []
    for old in adjustments(db, org_id, old_season_id):
        new = SeasonAdjustment(org_id=org_id, season_id=new_season_id, position=old.position)
        for key in ("name", "amount", "unit", "mode", "code", "shown", "max_uses", "quantity", "active"):
            setattr(new, key, getattr(old, key))
        new.until = _next_year(old.until)
        new.plans = [same[plan.id] for plan in old.plans]
        db.add(new)
        copied_adjustments.append(new)
    db.flush()
    return list(same.values()), copied_adjustments
