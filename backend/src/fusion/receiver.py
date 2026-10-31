"""Route « Fusionner avec… » d'une fiche (spec/core.md §4)."""

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from comptes import Compte, rbac, roles
from comptes.schemas import CompteSortie
from db import get_db

from .fusion import Fusion, RefusFusion


class FusionDemande(BaseModel):
    autre_id: int
    # Les mails à garder ; absent : ceux des deux fiches.
    emails: list[str] | None = None


class FusionReceiver:
    def __init__(self, client: Fusion, app: FastAPI) -> None:
        self.client = client
        app.post("/comptes/{compte_id}/fusion", response_model=CompteSortie)(self.fusionner)

    def fusionner(
        self,
        compte_id: int,
        demande: FusionDemande,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        """Garde la fiche `compte_id`, y verse `autre_id`. Un admin de
        l'école ; un Administrateur principal dès qu'une des deux fiches
        est admin, car la fiche gardée en reçoit les emails et les droits."""
        garde = self.client.comptes.get(db, compte_id)
        absorbe = self.client.comptes.get(db, demande.autre_id)
        rbac.require_admin(appelant, garde.ecole_id if garde else None)
        try:
            self.client.verifier(garde, absorbe)
        except RefusFusion as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
        if roles.is_admin(garde) or roles.is_admin(absorbe):
            rbac.require_owner(appelant, garde.ecole_id)
        try:
            return self.client.fusionner(db, garde, absorbe, demande.emails)
        except RefusFusion as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from erreur
