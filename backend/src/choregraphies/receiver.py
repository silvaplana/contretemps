"""Routes REST des chorégraphies — reçoit les requêtes HTTP, délègue tout
à Choregraphies (voir choregraphies.py), ne fait aucun calcul métier ici.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .choregraphies import Choregraphies
from .schemas import (
    ChoregraphieCreation,
    ChoregraphieModification,
    ChoregraphieSortie,
    EleveParticipant,
)


class ChoregraphiesReceiver:
    def __init__(self, client: Choregraphies, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get(
            "/cours/{cours_id}/choregraphies", response_model=list[ChoregraphieSortie]
        )(self.lister)
        self.app.post(
            "/cours/{cours_id}/choregraphies",
            response_model=ChoregraphieSortie,
            status_code=201,
        )(self.creer)
        self.app.get("/choregraphies/{choregraphie_id}", response_model=ChoregraphieSortie)(
            self.obtenir
        )
        self.app.put("/choregraphies/{choregraphie_id}", response_model=ChoregraphieSortie)(
            self.modifier
        )
        self.app.delete("/choregraphies/{choregraphie_id}", status_code=204)(self.supprimer)

        self.app.get(
            "/choregraphies/{choregraphie_id}/eleves", response_model=list[EleveParticipant]
        )(self.eleves_participants)
        self.app.post("/choregraphies/{choregraphie_id}/eleves/{eleve_id}", status_code=204)(
            self.ajouter_eleve
        )
        self.app.delete("/choregraphies/{choregraphie_id}/eleves/{eleve_id}", status_code=204)(
            self.retirer_eleve
        )

    def lister(self, cours_id: int, db: Session = Depends(get_db)):
        return self.client.list(db, cours_id)

    def creer(
        self, cours_id: int, donnees: ChoregraphieCreation, db: Session = Depends(get_db)
    ):
        return self.client.create(db, cours_id, **donnees.model_dump())

    def obtenir(self, choregraphie_id: int, db: Session = Depends(get_db)):
        choregraphie = self.client.get(db, choregraphie_id)
        if choregraphie is None:
            raise HTTPException(status_code=404, detail="Chorégraphie introuvable")
        return choregraphie

    def modifier(
        self,
        choregraphie_id: int,
        donnees: ChoregraphieModification,
        db: Session = Depends(get_db),
    ):
        choregraphie = self.client.update(
            db, choregraphie_id, **donnees.model_dump(exclude_unset=True)
        )
        if choregraphie is None:
            raise HTTPException(status_code=404, detail="Chorégraphie introuvable")
        return choregraphie

    def supprimer(self, choregraphie_id: int, db: Session = Depends(get_db)):
        if not self.client.delete(db, choregraphie_id):
            raise HTTPException(status_code=404, detail="Chorégraphie introuvable")

    def eleves_participants(self, choregraphie_id: int, db: Session = Depends(get_db)):
        return self.client.eleves_participants(db, choregraphie_id)

    def ajouter_eleve(
        self, choregraphie_id: int, eleve_id: int, db: Session = Depends(get_db)
    ):
        if not self.client.ajouter_eleve(db, choregraphie_id, eleve_id):
            raise HTTPException(
                status_code=409,
                detail="Chorégraphie introuvable, ou élève non inscrit au cours lié",
            )

    def retirer_eleve(
        self, choregraphie_id: int, eleve_id: int, db: Session = Depends(get_db)
    ):
        self.client.retirer_eleve(db, choregraphie_id, eleve_id)
