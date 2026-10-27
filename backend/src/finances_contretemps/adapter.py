"""Branchement du module `finances` sur Contretemps : organisation = école,
trésorier = rôle `tresorier`, Super User = école choisie (en-tête
X-Ecole-Id, comme pour les notes de frais), saisons = celles de l'école."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from comptes import Compte, rbac, roles
from db import get_db
from documents_contretemps.adapter import nom_affiche, personne_id
from finances.ports import Member, Season
from inscriptions.models import Inscription
from notes_frais_contretemps.adapter import _ecole_choisie
from saisons.models import Saison
from saisons.portee import toutes_saisons


# Le droit « Accès au Financier » (spec/core.md §5.3), déclaré dans module.py.
FINANCES_ACCESS = roles.DROIT_FINANCIER

def membre_appelant(
    request: Request, db: Session = Depends(get_db), compte: Compte = Depends(rbac.compte_appelant)
) -> Member:
    if compte is None:
        raise HTTPException(status_code=401, detail="Session requise")
    ecole_id = _ecole_choisie(db, request) if roles.is_superuser(compte) else compte.ecole_id
    if ecole_id is None:
        raise HTTPException(status_code=403, detail="Choisissez d'abord une école")
    return Member(
        person_id=personne_id(db, compte),
        org_id=ecole_id,
        name=nom_affiche(compte),
        is_treasurer=roles.has_right(compte, FINANCES_ACCESS),
        is_superuser=roles.is_superuser(compte),
    )


def saisons_de_l_ecole(db: Session, ecole_id: int) -> list[Season]:
    """De la plus ancienne à la plus récente ; la courante est la dernière
    créée (voir saisons/saisons.py)."""
    with toutes_saisons(db):
        saisons = list(db.scalars(select(Saison).where(Saison.ecole_id == ecole_id).order_by(Saison.id)))
    # Inscrits par saison : les fiches d'inscription de l'école.
    inscrits = dict(
        db.execute(
            select(Inscription.saison_id, func.count()).where(Inscription.ecole_id == ecole_id).group_by(Inscription.saison_id)
        ).all()
    )
    return [
        Season(
            id=s.id,
            name=s.nom,
            start_date=s.date_debut.isoformat(),
            end_date=s.date_fin.isoformat(),
            current=i == len(saisons) - 1,
            members=inscrits.get(s.id, 0),
        )
        for i, s in enumerate(saisons)
    ]
