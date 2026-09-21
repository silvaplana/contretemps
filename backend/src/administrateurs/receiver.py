"""Routes REST du tableau des administrateurs (Admin > École, spec §2.4).

Droits (comptes/rbac.py) : tout admin de l'école voit la liste ; seuls ses
Owners créent, modifient et suppriment un administrateur — et jamais sur
leur propre ligne (pas d'auto-rétrogradation ni d'auto-suppression par
accident).
"""

from __future__ import annotations

from comptes import Compte, RegleRoles, rbac, roles
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .administrateurs import Administrateurs
from .schemas import AdministrateurCreation, AdministrateurModification, AdministrateurSortie


def _sortie(compte: Compte) -> dict:
    return {
        "id": compte.id,
        "nom": compte.nom,
        "prenom": compte.prenom,
        "email": compte.email,
        "est_owner": roles.is_owner(compte),
        "est_prof": roles.is_prof(compte),
        "code_recuperation_defini": compte.code_recuperation_defini,
    }


class AdministrateursReceiver:
    def __init__(self, client: Administrateurs, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get(
            "/ecoles/{ecole_id}/administrateurs",
            response_model=list[AdministrateurSortie],
            dependencies=[Depends(self._admin_ecole)],
        )(self.lister)
        self.app.post(
            "/ecoles/{ecole_id}/administrateurs",
            response_model=AdministrateurSortie,
            status_code=201,
            dependencies=[Depends(self._owner_ecole)],
        )(self.creer)
        self.app.put("/administrateurs/{compte_id}", response_model=AdministrateurSortie)(
            self.modifier
        )
        self.app.delete("/administrateurs/{compte_id}", status_code=204)(self.supprimer)

    # --- RBAC (spec §2.4) ---

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _owner_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_owner(appelant, ecole_id)

    def _cible_pour_owner(self, db: Session, compte_id: int, appelant: Compte) -> Compte:
        """L'administrateur visé, après les vérifications : l'appelant est
        Owner de SON école, et ce n'est pas lui-même."""
        cible = self.client.get(db, compte_id)
        rbac.require_owner(appelant, cible.ecole_id if cible else None)
        if cible is None:
            raise HTTPException(status_code=404, detail="Administrateur introuvable")
        # `appelant` peut être None quand les tests neutralisent le RBAC.
        if appelant is not None and appelant.id == cible.id:
            raise HTTPException(
                status_code=403, detail="Un Owner ne peut pas modifier ou supprimer sa propre ligne"
            )
        return cible

    # --- Routes ---

    def lister(self, ecole_id: int, db: Session = Depends(get_db)):
        return [_sortie(c) for c in self.client.lister(db, ecole_id)]

    def creer(self, ecole_id: int, donnees: AdministrateurCreation, db: Session = Depends(get_db)):
        try:
            if donnees.professeur_id is not None:
                compte = self.client.promouvoir(
                    db,
                    ecole_id,
                    donnees.professeur_id,
                    code_recuperation=donnees.code_recuperation,
                    owner=donnees.owner,
                )
            else:
                compte = self.client.creer(
                    db,
                    ecole_id,
                    nom=donnees.nom.strip(),
                    prenom=donnees.prenom.strip(),
                    email=(donnees.email or "").strip() or None,
                    code_recuperation=donnees.code_recuperation,
                    owner=donnees.owner,
                )
        except LookupError as erreur:
            raise HTTPException(status_code=404, detail=str(erreur)) from erreur
        except RegleRoles as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return _sortie(compte)

    def modifier(
        self,
        compte_id: int,
        donnees: AdministrateurModification,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        cible = self._cible_pour_owner(db, compte_id, appelant)
        champs = donnees.model_dump(exclude_unset=True)
        owner = champs.pop("owner", None)
        try:
            cible = self.client.modifier(db, cible, champs=champs, owner=owner)
        except RegleRoles as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return _sortie(cible)

    def supprimer(
        self,
        compte_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        cible = self._cible_pour_owner(db, compte_id, appelant)
        try:
            self.client.supprimer(db, cible)
        except RegleRoles as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
