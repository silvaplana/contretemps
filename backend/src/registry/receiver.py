"""Routes des modules d'une organisation (spec/core.md §9 bis.3) : la liste
est lue par chaque membre (onglets à montrer) ; l'Administrateur principal et
le Super User allument ou éteignent un module (Admin > École >
Personnalisation de l'application > Fonctionnalités)."""

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db

from . import activation


class ModuleState(BaseModel):
    enabled: bool


class ModulesReceiver:
    def __init__(self, modules: list, app: FastAPI) -> None:
        self.modules = modules
        app.get("/ecoles/{ecole_id}/modules")(self.list)
        app.put("/ecoles/{ecole_id}/modules/{key}")(self.update)

    def list(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        rbac.require_membre(appelant, ecole_id)
        return activation.listing(db, ecole_id, self.modules)

    def update(
        self,
        ecole_id: int,
        key: str,
        state: ModuleState,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        rbac.require_owner(appelant, ecole_id)
        try:
            activation.set_enabled(db, ecole_id, self.modules, key, state.enabled)
        except LookupError:
            raise HTTPException(status_code=404, detail="Module introuvable") from None
        except ValueError as erreur:
            raise HTTPException(status_code=409, detail=str(erreur)) from None
        return activation.listing(db, ecole_id, self.modules)
