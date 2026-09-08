"""Routes REST des écoles — reçoit les requêtes HTTP, délègue tout à
Ecoles (voir ecoles.py), ne fait aucun calcul métier ici.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .ecoles import Ecoles
from .schemas import EcoleCreation, EcoleModification, EcoleSortie


class EcolesReceiver:
    """Comme les autres receivers (voir main.py) : enregistre ses routes
    sur une app FastAPI existante, partagée avec les autres modules."""

    def __init__(self, client: Ecoles, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/ecoles", response_model=list[EcoleSortie])(self.lister)
        self.app.get("/ecoles/{ecole_id}", response_model=EcoleSortie)(self.obtenir)
        self.app.post("/ecoles", response_model=EcoleSortie, status_code=201)(self.creer)
        self.app.put("/ecoles/{ecole_id}", response_model=EcoleSortie)(self.modifier)

    def lister(self, db: Session = Depends(get_db)):
        return self.client.list(db)

    def obtenir(self, ecole_id: int, db: Session = Depends(get_db)):
        ecole = self.client.get(db, ecole_id)
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        return ecole

    def creer(self, donnees: EcoleCreation, db: Session = Depends(get_db)):
        """Voir spec §2.3 : crée l'école. La création du premier compte
        admin associé est faite par le module comptes (appelée depuis le
        même endpoint côté frontend, pas ici — ecoles ne connaît pas
        comptes)."""
        existante = self.client.find_by_nom_code_postal(db, donnees.nom, donnees.code_postal)
        if existante is not None:
            raise HTTPException(
                status_code=409,
                detail="Une école avec ce nom et ce code postal existe déjà",
            )
        return self.client.create(db, **donnees.model_dump())

    def modifier(self, ecole_id: int, donnees: EcoleModification, db: Session = Depends(get_db)):
        ecole = self.client.update(db, ecole_id, **donnees.model_dump(exclude_unset=True))
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        return ecole
