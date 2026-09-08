"""Routes REST des professeurs — reçoit les requêtes HTTP, délègue tout à
Profs (voir profs.py). L'assignation à un cours passe par les routes déjà
existantes du module cours (/cours/{id}/professeurs/{compte_id}), pas
dupliquées ici.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .profs import Profs
from .schemas import ProfCreation, ProfModification, ProfSortie


class ProfsReceiver:
    def __init__(self, client: Profs, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/profs", response_model=list[ProfSortie])(self.lister)
        self.app.get("/profs/{prof_id}", response_model=ProfSortie)(self.obtenir)
        self.app.post("/profs", response_model=ProfSortie, status_code=201)(self.creer)
        self.app.put("/profs/{prof_id}", response_model=ProfSortie)(self.modifier)
        self.app.delete("/profs/{prof_id}", status_code=204)(self.supprimer)

    def _avec_cours_ids(self, db: Session, compte) -> dict:
        return {
            "id": compte.id,
            "ecole_id": compte.ecole_id,
            "nom": compte.nom,
            "prenom": compte.prenom,
            "email": compte.email,
            "telephone": compte.telephone,
            "cours_ids": [c.id for c in self.client.cours.cours_du_professeur(db, compte.id)],
        }

    def lister(self, ecole_id: int, db: Session = Depends(get_db)):
        return [self._avec_cours_ids(db, p) for p in self.client.list(db, ecole_id)]

    def obtenir(self, prof_id: int, db: Session = Depends(get_db)):
        prof = self.client.get(db, prof_id)
        if prof is None:
            raise HTTPException(status_code=404, detail="Professeur introuvable")
        return self._avec_cours_ids(db, prof)

    def creer(self, ecole_id: int, donnees: ProfCreation, db: Session = Depends(get_db)):
        prof = self.client.create(db, ecole_id, **donnees.model_dump())
        return self._avec_cours_ids(db, prof)

    def modifier(self, prof_id: int, donnees: ProfModification, db: Session = Depends(get_db)):
        prof = self.client.update(db, prof_id, **donnees.model_dump(exclude_unset=True))
        if prof is None:
            raise HTTPException(status_code=404, detail="Professeur introuvable")
        return self._avec_cours_ids(db, prof)

    def supprimer(self, prof_id: int, db: Session = Depends(get_db)):
        if not self.client.delete(db, prof_id):
            raise HTTPException(status_code=404, detail="Professeur introuvable")
