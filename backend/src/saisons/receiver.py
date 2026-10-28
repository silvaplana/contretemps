"""Routes des saisons (Admin > École, voir spec/SPEC.md §2.6 et §5.1.1) :
lister, créer (avec duplication), éditer la saison courante ou une ancienne
saison ouverte. Réservées aux admins de l'école ; ouvrir une ancienne saison
aux modifications est réservé à l'administrateur principal et au Super
User."""

from __future__ import annotations

from comptes import Compte, rbac, roles
from ecoles.models import Ecole
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .gestion import Duplication, ErreurSaison, GestionSaisons
from .schemas import (
    SaisonContenu,
    SaisonCreation,
    SaisonCreee,
    SaisonModification,
    SaisonOuverture,
    SaisonSortie,
    SaisonSupprimee,
)


def _sortie(saison, courante_id: int) -> SaisonSortie:
    sortie = SaisonSortie.model_validate(saison)
    sortie.courante = saison.id == courante_id
    return sortie


class SaisonsReceiver:
    def __init__(self, client: GestionSaisons, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        admin = [Depends(self._admin_ecole)]
        self.app.get("/ecoles/{ecole_id}/saisons", response_model=list[SaisonSortie], dependencies=admin)(
            self.lister
        )
        self.app.post(
            "/ecoles/{ecole_id}/saisons", response_model=SaisonCreee, status_code=201, dependencies=admin
        )(self.creer)
        self.app.put("/ecoles/{ecole_id}/saisons/courante", response_model=SaisonSortie, dependencies=admin)(
            self.modifier_courante
        )
        self.app.put("/ecoles/{ecole_id}/saisons/{saison_id}", response_model=SaisonSortie, dependencies=admin)(
            self.modifier
        )
        self.app.put(
            "/ecoles/{ecole_id}/saisons/{saison_id}/ouverture",
            response_model=SaisonSortie,
            dependencies=[Depends(self._owner_ecole)],
        )(self.ouvrir)
        self.app.get(
            "/ecoles/{ecole_id}/saisons/courante/contenu", response_model=SaisonContenu, dependencies=admin
        )(self.contenu)
        self.app.delete(
            "/ecoles/{ecole_id}/saisons/{saison_id}", response_model=SaisonSupprimee, dependencies=admin
        )(self.supprimer)

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _owner_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)
        if appelant is not None and not (roles.is_owner(appelant) or roles.is_superuser(appelant)):
            raise HTTPException(status_code=403, detail="Réservé à l'administrateur principal")

    def lister(self, ecole_id: int, db: Session = Depends(get_db)):
        saisons = self.client.lister(db, ecole_id)
        courante_id = saisons[0].id if saisons else None
        return [_sortie(s, courante_id) for s in saisons]

    def creer(
        self,
        ecole_id: int,
        donnees: SaisonCreation,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        try:
            saison, fiches = self.client.creer(
                db,
                ecole_id,
                donnees.nom,
                donnees.date_debut,
                donnees.date_fin,
                Duplication(
                    profs=donnees.dupliquer_profs,
                    cours=donnees.dupliquer_cours,
                    eleves=donnees.dupliquer_eleves,
                    documents=donnees.dupliquer_documents,
                    structure_eleves=donnees.structure_eleves,
                    champs_masques=set(donnees.champs_masques),
                ),
                auteur_id=appelant.id if appelant is not None else None,
            )
        except ErreurSaison as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return SaisonCreee(
            saison=_sortie(saison, self.client.lister(db, ecole_id)[0].id),
            compte_id=fiches.get(appelant.id) if appelant is not None else None,
        )

    def contenu(self, ecole_id: int, db: Session = Depends(get_db)):
        return self.client.contenu(db, ecole_id)

    def modifier_courante(self, ecole_id: int, donnees: SaisonModification, db: Session = Depends(get_db)):
        try:
            saison = self.client.modifier_courante(db, ecole_id, donnees.nom, donnees.date_debut, donnees.date_fin)
        except ErreurSaison as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return _sortie(saison, saison.id)

    def modifier(self, ecole_id: int, saison_id: int, donnees: SaisonModification, db: Session = Depends(get_db)):
        try:
            saison = self.client.modifier(db, ecole_id, saison_id, donnees.nom, donnees.date_debut, donnees.date_fin)
        except ErreurSaison as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return _sortie(saison, self.client.lister(db, ecole_id)[0].id)

    def ouvrir(self, ecole_id: int, saison_id: int, donnees: SaisonOuverture, db: Session = Depends(get_db)):
        try:
            saison = self.client.ouvrir(db, ecole_id, saison_id, donnees.ouverte)
        except ErreurSaison as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return _sortie(saison, self.client.lister(db, ecole_id)[0].id)

    def supprimer(
        self,
        ecole_id: int,
        saison_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        ecole = db.get(Ecole, ecole_id)
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        try:
            fiche = self.client.supprimer(db, ecole, saison_id, appelant.id if appelant is not None else None)
        except ErreurSaison as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return SaisonSupprimee(compte_id=fiche)
