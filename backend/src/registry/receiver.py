"""Routes des modules d'une organisation (spec/core.md §9 bis.3) : la liste
est lue par chaque membre (onglets à montrer) ; l'Administrateur principal et
le Super User allument ou éteignent un module (Admin > École >
Personnalisation de l'application > Fonctionnalités), et y rangent les
onglets de la barre du bas pour toute l'école (Seb, 18/11/2026)."""

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException
from ecoles.models import Ecole
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from . import activation, rights_of


class ModuleState(BaseModel):
    enabled: bool


class TabOrder(BaseModel):
    # Clés des onglets dans l'ordre ; [] revient à l'ordre des modules.
    tab_order: list[str] = Field(max_length=40)


class ModulesReceiver:
    def __init__(self, modules: list, app: FastAPI) -> None:
        self.modules = modules
        app.get("/ecoles/{ecole_id}/modules")(self.list)
        app.put("/ecoles/{ecole_id}/modules/{key}")(self.update)
        app.get("/ecoles/{ecole_id}/droits")(self.rights)
        app.get("/ecoles/{ecole_id}/tab-order")(self.tab_order)
        app.put("/ecoles/{ecole_id}/tab-order")(self.set_tab_order)

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

    def rights(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """Les 🔒 droits des modules allumés (spec/core.md §5.3), à cocher
        dans Admin > École > Administrateurs."""
        rbac.require_membre(appelant, ecole_id)
        off = activation.disabled(db, ecole_id)
        return [
            {"key": r.key, "label": r.label}
            for m in self.modules if m.key not in off for r in rights_of(m, db, ecole_id)
        ]

    def tab_order(self, ecole_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        """L'ordre de la barre du bas de l'école, lu par chaque membre."""
        rbac.require_membre(appelant, ecole_id)
        ecole = db.get(Ecole, ecole_id)
        return {"tab_order": (ecole.tab_order if ecole else None) or []}

    def set_tab_order(
        self,
        ecole_id: int,
        donnees: TabOrder,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        rbac.require_owner(appelant, ecole_id)
        ecole = db.get(Ecole, ecole_id)
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        ecole.tab_order = [k[:40] for k in donnees.tab_order] or None
        db.commit()
        return {"tab_order": ecole.tab_order or []}
