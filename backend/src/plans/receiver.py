"""Routes des tarifs de la saison (spec/core.md §9, Admin > École > Tarifs),
réservées aux admins de l'école. On lit la saison affichée ; on ne modifie
que la saison courante."""

from __future__ import annotations

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException
from saisons import Saison, saison_courante_id
from saisons.portee import SaisonEnLectureSeule, saison_demandee
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db

from . import plans as p
from .models import SeasonPlan
from .schemas import PlanIn, PlanOut, PlansOut, Previous


def _installments(data: PlanIn) -> list:
    return [(i.due_on, i.amount) for i in data.installments]


class PlansReceiver:
    def __init__(self, app: FastAPI) -> None:
        admin = [Depends(self._admin_ecole)]
        app.get("/ecoles/{ecole_id}/tarifs", response_model=PlansOut, dependencies=admin)(self.lister)
        app.post("/ecoles/{ecole_id}/tarifs/formules", response_model=PlanOut, status_code=201, dependencies=admin)(
            self.creer
        )
        app.post("/ecoles/{ecole_id}/tarifs/reprendre", response_model=list[PlanOut], dependencies=admin)(
            self.reprendre
        )
        app.put("/tarifs/formules/{plan_id}", response_model=PlanOut)(self.modifier)
        app.post("/tarifs/formules/{plan_id}/dupliquer", response_model=PlanOut, status_code=201)(self.dupliquer)
        app.delete("/tarifs/formules/{plan_id}", status_code=204)(self.retirer)

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    @staticmethod
    def _formule(db: Session, plan_id: int, appelant: Compte | None) -> SeasonPlan:
        """Une formule de la saison courante de l'école de l'admin."""
        plan = db.get(SeasonPlan, plan_id)
        rbac.require_admin(appelant, plan.org_id if plan else None)
        if plan is None:
            raise HTTPException(status_code=404, detail="Formule introuvable")
        if plan.season_id != saison_courante_id(db, plan.org_id):
            raise SaisonEnLectureSeule()
        return plan

    @staticmethod
    def _courante(db: Session, ecole_id: int) -> int:
        """Les écritures : toujours la saison courante, jamais une ancienne."""
        courante = saison_courante_id(db, ecole_id)
        if saison_demandee() not in (None, courante):
            raise SaisonEnLectureSeule()
        return courante

    def lister(self, ecole_id: int, db: Session = Depends(get_db)):
        courante = saison_courante_id(db, ecole_id)
        saison = saison_demandee() or courante
        liste = p.plans(db, ecole_id, saison)
        previous = None
        avant = db.scalar(
            select(Saison).where(Saison.ecole_id == ecole_id, Saison.id < saison).order_by(Saison.id.desc()).limit(1)
        )
        if not liste and avant is not None and (n := len(p.plans(db, ecole_id, avant.id))):
            previous = Previous(name=avant.nom, plans=n)
        return PlansOut(
            season=db.get(Saison, saison).nom, read_only=saison != courante, plans=liste, previous=previous
        )

    def creer(self, ecole_id: int, data: PlanIn, db: Session = Depends(get_db)):
        try:
            plan = p.create(
                db, ecole_id, self._courante(db, ecole_id), data.name, data.price, data.active,
                _installments(data), data.position,
            )
        except p.PlanError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        db.commit()
        return plan

    def reprendre(self, ecole_id: int, db: Session = Depends(get_db)):
        """« Reprendre ceux de <saison précédente> » : seulement si la saison
        n'a encore aucune formule."""
        courante = self._courante(db, ecole_id)
        avant = db.scalar(
            select(Saison.id).where(Saison.ecole_id == ecole_id, Saison.id < courante).order_by(Saison.id.desc()).limit(1)
        )
        if avant is None or p.plans(db, ecole_id, courante):
            raise HTTPException(status_code=409, detail="Rien à reprendre")
        copies = p.copy_season(db, ecole_id, avant, courante)
        db.commit()
        return copies

    def modifier(self, plan_id: int, data: PlanIn, db: Session = Depends(get_db),
                 appelant: Compte = Depends(rbac.compte_appelant)):
        plan = self._formule(db, plan_id, appelant)
        try:
            p.update(plan, data.name, data.price, data.active, _installments(data))
        except p.PlanError as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from None
        db.commit()
        return plan

    def dupliquer(self, plan_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        copie = p.duplicate(db, self._formule(db, plan_id, appelant))
        db.commit()
        return copie

    def retirer(self, plan_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        db.delete(self._formule(db, plan_id, appelant))
        db.commit()
