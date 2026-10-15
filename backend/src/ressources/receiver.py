"""Route du panneau « Usage ressources et IA de la saison » (Admin > École)."""

from comptes import Compte, rbac
from fastapi import Depends, FastAPI
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db

from .ressources import Ressources


class RubriqueMemoire(BaseModel):
    cle: str
    libelle: str
    octets: int


class PosteIA(BaseModel):
    categorie: str
    libelle: str
    nombre: int
    cout_usd: float


class UsageRessources(BaseModel):
    saison: str | None
    memoire: list[RubriqueMemoire]
    memoire_total_octets: int
    ia: list[PosteIA]
    ia_total_usd: float
    ia_total_toutes_saisons_usd: float


class RessourcesReceiver:
    def __init__(self, client: Ressources, app: FastAPI) -> None:
        self.client = client
        app.get(
            "/ecoles/{ecole_id}/ressources",
            response_model=UsageRessources,
            dependencies=[Depends(self._admin_ecole)],
        )(self.usage)

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def usage(self, ecole_id: int, db: Session = Depends(get_db)):
        return self.client.usage(db, ecole_id)
