"""Branchement du module `session_clips` sur Contretemps : organisation =
école, personne = premier compte de la chaîne des saisons (comme pour
documents), coach = admin ou professeur, Super User = école choisie
(en-tête X-Ecole-Id, comme pour les notes de frais)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from comptes import Compte, rbac, roles
from db import get_db
from documents_contretemps.adapter import _saison_courante, nom_affiche, personne_id
from notes_frais_contretemps.adapter import _ecole_choisie
from saisons.portee import toutes_saisons
from session_clips.ports import Member, Person


def nom_court(compte: Compte) -> str:
    """« Seb R. », comme sur la maquette validée."""
    return f"{compte.prenom} {compte.nom[:1]}.".strip() if compte.nom else compte.prenom


def membre_appelant(
    request: Request, db: Session = Depends(get_db), compte: Compte = Depends(rbac.compte_appelant)
) -> Member:
    if compte is None:
        raise HTTPException(status_code=401, detail="Session requise")
    ecole_id = _ecole_choisie(db, request) if roles.is_superuser(compte) else compte.ecole_id
    if ecole_id is None:
        raise HTTPException(status_code=403, detail="Choisissez d'abord une école")
    coach = roles.is_superuser(compte) or roles.is_admin(compte) or roles.is_owner(compte) or roles.is_prof(compte)
    return Member(person_id=personne_id(db, compte), org_id=ecole_id, name=nom_affiche(compte), is_coach=coach)


class AnnuaireSparring:
    """Port `Directory` : les membres de l'école."""

    def people(self, db: Session, org_id: int) -> list[Person]:
        saison = _saison_courante(db, org_id)
        with toutes_saisons(db):
            comptes = db.scalars(
                select(Compte).where(Compte.ecole_id == org_id, Compte.saison_id == saison).order_by(Compte.prenom, Compte.nom)
            )
            vus: dict[int, Person] = {}
            for compte in comptes:
                pid = personne_id(db, compte)
                vus.setdefault(pid, Person(pid, nom_court(compte)))
        return list(vus.values())

    def names(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, str]:
        if not person_ids:
            return {}
        with toutes_saisons(db):
            return {c.id: nom_court(c) for c in db.scalars(select(Compte).where(Compte.id.in_(person_ids)))}
