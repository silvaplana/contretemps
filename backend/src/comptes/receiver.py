"""Routes REST minimales pour l'écran Profil (voir spec/SPEC.md §5.6) : lire
un compte et lister les profils de sa famille. Les écrans Élèves/Profs ont
leurs propres routes dans leurs modules respectifs, pas ici.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .comptes import Comptes
from .schemas import CompteSortie


class ComptesReceiver:
    def __init__(self, client: Comptes, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/comptes/{compte_id}", response_model=CompteSortie)(self.obtenir)
        self.app.get("/comptes/{compte_id}/famille", response_model=list[CompteSortie])(
            self.famille
        )

    def obtenir(self, compte_id: int, db: Session = Depends(get_db)):
        compte = self.client.get(db, compte_id)
        if compte is None:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        return compte

    def famille(self, compte_id: int, db: Session = Depends(get_db)):
        return self.client.membres_de_la_famille(db, compte_id)
