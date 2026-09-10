"""Routes REST minimales pour l'écran Profil (voir spec/SPEC.md §5.6) : lire
un compte et lister les profils de sa famille. Les écrans Élèves/Profs ont
leurs propres routes dans leurs modules respectifs, pas ici.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .comptes import Comptes
from .schemas import CompteModification, CompteSortie


class ComptesReceiver:
    def __init__(self, client: Comptes, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/comptes", response_model=list[CompteSortie])(self.lister)
        self.app.get("/comptes/{compte_id}", response_model=CompteSortie)(self.obtenir)
        self.app.put("/comptes/{compte_id}", response_model=CompteSortie)(self.modifier)
        self.app.get("/comptes/{compte_id}/famille", response_model=list[CompteSortie])(
            self.famille
        )

    def lister(self, ecole_id: int, role: str, db: Session = Depends(get_db)):
        """Utilisé par Admin > Conversations pour proposer les vrais
        comptes admin de l'école (voir AdminGroupes.jsx) — pas encore
        d'écran de gestion multi-admin dédié (spec/SPEC.md §8), donc pas
        de route plus générale pour l'instant."""
        return self.client.list_par_role(db, ecole_id, role)

    def obtenir(self, compte_id: int, db: Session = Depends(get_db)):
        compte = self.client.get(db, compte_id)
        if compte is None:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        return compte

    def modifier(self, compte_id: int, donnees: CompteModification, db: Session = Depends(get_db)):
        """Profil admin (voir ProfilScreen.jsx) : crayon à côté de
        l'email/du code de récupération."""
        compte = self.client.update(db, compte_id, **donnees.model_dump(exclude_unset=True))
        if compte is None:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        return compte

    def famille(self, compte_id: int, db: Session = Depends(get_db)):
        return self.client.membres_de_la_famille(db, compte_id)
