"""Routes REST des cours — reçoit les requêtes HTTP, délègue tout à
CoursService (voir cours.py), ne fait aucun calcul métier ici.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .cours import CoursService
from .schemas import CompteResume, CoursCreation, CoursModification, CoursSortie


class CoursReceiver:
    """Comme les autres receivers (voir main.py) : enregistre ses routes
    sur une app FastAPI existante, partagée avec les autres modules."""

    def __init__(self, client: CoursService, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/cours", response_model=list[CoursSortie])(self.lister)
        self.app.get("/cours/{cours_id}", response_model=CoursSortie)(self.obtenir)
        self.app.post("/cours", response_model=CoursSortie, status_code=201)(self.creer)
        self.app.put("/cours/{cours_id}", response_model=CoursSortie)(self.modifier)
        self.app.delete("/cours/{cours_id}", status_code=204)(self.supprimer)

        self.app.get(
            "/cours/{cours_id}/professeurs", response_model=list[CompteResume]
        )(self.professeurs)
        self.app.post("/cours/{cours_id}/professeurs/{compte_id}", status_code=204)(
            self.ajouter_professeur
        )
        self.app.delete("/cours/{cours_id}/professeurs/{compte_id}", status_code=204)(
            self.retirer_professeur
        )

        self.app.get("/cours/{cours_id}/eleves", response_model=list[CompteResume])(
            self.eleves
        )
        self.app.post("/cours/{cours_id}/eleves/{compte_id}", status_code=204)(
            self.inscrire_eleve
        )
        self.app.delete("/cours/{cours_id}/eleves/{compte_id}", status_code=204)(
            self.desinscrire_eleve
        )

        # Sens inverse de /cours/{id}/eleves — utile à Admin > Élèves (une
        # ligne par élève, colonne "cours suivis"), pas seulement à
        # Admin > Cours (voir CoursService.cours_de_leleve).
        self.app.get("/eleves/{eleve_id}/cours", response_model=list[CoursSortie])(
            self.cours_de_leleve
        )

    def lister(self, ecole_id: int, db: Session = Depends(get_db)):
        return self.client.list(db, ecole_id)

    def obtenir(self, cours_id: int, db: Session = Depends(get_db)):
        cours = self.client.get(db, cours_id)
        if cours is None:
            raise HTTPException(status_code=404, detail="Cours introuvable")
        return cours

    def creer(self, ecole_id: int, donnees: CoursCreation, db: Session = Depends(get_db)):
        return self.client.create(db, ecole_id, **donnees.model_dump())

    def modifier(self, cours_id: int, donnees: CoursModification, db: Session = Depends(get_db)):
        cours = self.client.update(db, cours_id, **donnees.model_dump(exclude_unset=True))
        if cours is None:
            raise HTTPException(status_code=404, detail="Cours introuvable")
        return cours

    def supprimer(self, cours_id: int, db: Session = Depends(get_db)):
        if not self.client.delete(db, cours_id):
            raise HTTPException(status_code=404, detail="Cours introuvable")

    def professeurs(self, cours_id: int, db: Session = Depends(get_db)):
        return self.client.professeurs_du_cours(db, cours_id)

    def ajouter_professeur(self, cours_id: int, compte_id: int, db: Session = Depends(get_db)):
        self.client.ajouter_professeur(db, cours_id, compte_id)

    def retirer_professeur(self, cours_id: int, compte_id: int, db: Session = Depends(get_db)):
        self.client.retirer_professeur(db, cours_id, compte_id)

    def eleves(self, cours_id: int, db: Session = Depends(get_db)):
        return self.client.eleves_du_cours(db, cours_id)

    def inscrire_eleve(self, cours_id: int, compte_id: int, db: Session = Depends(get_db)):
        self.client.inscrire_eleve(db, cours_id, compte_id)

    def desinscrire_eleve(self, cours_id: int, compte_id: int, db: Session = Depends(get_db)):
        self.client.desinscrire_eleve(db, cours_id, compte_id)

    def cours_de_leleve(self, eleve_id: int, db: Session = Depends(get_db)):
        return self.client.cours_de_leleve(db, eleve_id)
