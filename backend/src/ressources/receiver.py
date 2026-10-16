"""Route du panneau « Usage ressources et IA de la saison » (Admin > École)."""

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from assistant.receiver import super_user_ou_sa_fiche
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
    # Assistant (Seb, 16 octobre) : plafond par mois civil et dépense du mois.
    assistant_plafond_mensuel_usd: float
    assistant_cout_du_mois_usd: float
    # La personne peut-elle changer le plafond ? (Super User, ou sa fiche d'école)
    assistant_plafond_modifiable: bool = False


class PlafondAssistant(BaseModel):
    plafond_usd: float = Field(ge=0, le=10000)


class RessourcesReceiver:
    def __init__(self, client: Ressources, app: FastAPI) -> None:
        self.client = client
        app.get(
            "/ecoles/{ecole_id}/ressources",
            response_model=UsageRessources,
            dependencies=[Depends(self._admin_ecole)],
        )(self.usage)
        # Réglé par le Super User seul (Seb, 16 octobre).
        app.put(
            "/ecoles/{ecole_id}/assistant-plafond",
            response_model=PlafondAssistant,
            dependencies=[Depends(self._superuser)],
        )(self.definir_plafond)

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _superuser(self, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        # Le Super User, y compris connecté avec sa fiche d'école (même email).
        if appelant is None or not super_user_ou_sa_fiche(db, appelant):
            rbac.require_superuser(appelant)

    def definir_plafond(self, ecole_id: int, donnees: PlafondAssistant, db: Session = Depends(get_db)):
        try:
            return {"plafond_usd": self.client.definir_plafond_assistant(db, ecole_id, donnees.plafond_usd)}
        except LookupError:
            raise HTTPException(status_code=404, detail="École introuvable")

    def usage(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        resultat = self.client.usage(db, ecole_id)
        resultat["assistant_plafond_modifiable"] = appelant is not None and super_user_ou_sa_fiche(db, appelant)
        return resultat
