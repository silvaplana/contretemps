"""Routes REST du tableau des administrateurs (Admin > École, spec §2.4).

Droits (comptes/rbac.py) : tout admin de l'école voit la liste ; seuls ses
Owners créent, modifient et suppriment un administrateur — et jamais sur
leur propre ligne (pas d'auto-rétrogradation ni d'auto-suppression par
accident).
"""

from __future__ import annotations

from comptes import Compte, RegleRoles, rbac, roles
from fastapi import Depends, FastAPI, HTTPException
from groups import board, custom
from saisons import saison_courante_id
from saisons.portee import saison_demandee
from sqlalchemy.orm import Session

from db import get_db

from .administrateurs import Administrateurs
from .schemas import (
    AdministrateurCreation,
    AdministrateurModification,
    AdministrateurSortie,
    GroupeCreation,
    GroupeSortie,
)

# Ce que tout admin de l'école change, sur toutes les lignes, la sienne
# comprise (spec/core.md §5.1) : les groupes qui ne donnent aucun droit.
CHAMPS_GROUPES = {"bureau_functions", "prof", "groups"}


def _sortie(db: Session, compte: Compte) -> dict:
    return {
        "id": compte.id,
        "nom": compte.nom,
        "prenom": compte.prenom,
        "email": compte.email,
        "emails": compte.emails,
        "est_owner": roles.is_owner(compte),
        "est_tresorier": roles.is_tresorier(compte),
        "bureau_functions": board.functions_of(db, compte),
        "groups": custom.ids_of(db, compte),
        "est_prof": roles.is_prof(compte),
        "est_eleve": roles.is_eleve(compte),
    }


def _saison(db: Session, ecole_id: int) -> int | None:
    return saison_demandee() or saison_courante_id(db, ecole_id)


def _est_superuser(appelant: Compte | None) -> bool:
    # `appelant` peut être None quand les tests neutralisent le RBAC.
    return appelant is not None and roles.is_superuser(appelant)


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
        self.app.get(
            "/ecoles/{ecole_id}/groupes",
            response_model=list[GroupeSortie],
            dependencies=[Depends(self._admin_ecole)],
        )(self.groupes)
        self.app.post(
            "/ecoles/{ecole_id}/groupes",
            response_model=GroupeSortie,
            status_code=201,
            dependencies=[Depends(self._admin_ecole)],
        )(self.creer_groupe)
        self.app.put("/administrateurs/{compte_id}", response_model=AdministrateurSortie)(
            self.modifier
        )
        self.app.delete("/administrateurs/{compte_id}", status_code=204)(self.supprimer)

    # --- RBAC (spec §2.4) ---

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _owner_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_owner(appelant, ecole_id)

    def _cible_pour_owner(
        self, db: Session, compte_id: int, appelant: Compte, *, soi_meme_permis: bool = False
    ) -> Compte:
        """L'administrateur visé, après les vérifications : l'appelant est
        Owner de SON école, et ce n'est pas lui-même (sauf `soi_meme_permis` :
        cocher ou décocher sa propre case Trésorier, ou ses fonctions au
        bureau, souvent le cas d'un bureau d'une seule personne)."""
        cible = self.client.get(db, compte_id)
        rbac.require_owner(appelant, cible.ecole_id if cible else None)
        if cible is None:
            raise HTTPException(status_code=404, detail="Administrateur introuvable")
        # `appelant` peut être None quand les tests neutralisent le RBAC.
        if appelant is not None and appelant.id == cible.id and not soi_meme_permis:
            raise HTTPException(
                status_code=403, detail="Un administrateur principal ne peut pas modifier ou supprimer sa propre ligne"
            )
        return cible

    # --- Routes ---

    def groupes(self, ecole_id: int, db: Session = Depends(get_db)):
        """Les groupes faits à la main de la saison affichée."""
        return custom.groups(db, ecole_id, _saison(db, ecole_id))

    def creer_groupe(self, ecole_id: int, donnees: GroupeCreation, db: Session = Depends(get_db)):
        try:
            groupe = custom.create(db, ecole_id, _saison(db, ecole_id), donnees.name)
        except custom.GroupError as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        db.commit()
        return groupe

    def lister(self, ecole_id: int, db: Session = Depends(get_db)):
        return [_sortie(db, c) for c in self.client.lister(db, ecole_id)]

    def creer(self, ecole_id: int, donnees: AdministrateurCreation, db: Session = Depends(get_db)):
        try:
            if donnees.compte_id is not None:
                compte = self.client.promouvoir(
                    db,
                    ecole_id,
                    donnees.compte_id,
                    owner=donnees.owner,
                )
            else:
                compte = self.client.creer(
                    db,
                    ecole_id,
                    nom=donnees.nom.strip(),
                    prenom=donnees.prenom.strip(),
                    email=(donnees.email or "").strip() or None,
                    owner=donnees.owner,
                )
        except LookupError as erreur:
            raise HTTPException(status_code=404, detail=str(erreur)) from erreur
        except RegleRoles as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return _sortie(db, compte)

    def modifier(
        self,
        compte_id: int,
        donnees: AdministrateurModification,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        champs = donnees.model_dump(exclude_unset=True)
        if champs and set(champs) <= CHAMPS_GROUPES:
            cible = self.client.get(db, compte_id)
            rbac.require_admin(appelant, cible.ecole_id if cible else None)
            if cible is None:
                raise HTTPException(status_code=404, detail="Administrateur introuvable")
        else:
            # Sur sa propre ligne : la case Accès au Financier et les groupes.
            soi_meme_permis = bool(champs) and set(champs) <= CHAMPS_GROUPES | {"tresorier"}
            cible = self._cible_pour_owner(db, compte_id, appelant, soi_meme_permis=soi_meme_permis)
        owner = champs.pop("owner", None)
        tresorier = champs.pop("tresorier", None)
        bureau = champs.pop("bureau_functions", None)
        prof = champs.pop("prof", None)
        groupes = champs.pop("groups", None)
        try:
            cible = self.client.modifier(
                db, cible, champs=champs, owner=owner, tresorier=tresorier, bureau_functions=bureau,
                prof=prof, groups=groupes, par_superuser=_est_superuser(appelant),
            )
        except RegleRoles as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        return _sortie(db, cible)

    def supprimer(
        self,
        compte_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        cible = self._cible_pour_owner(db, compte_id, appelant)
        try:
            self.client.supprimer(db, cible, par_superuser=_est_superuser(appelant))
        except RegleRoles as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
