"""Routes REST de la présence — reçoit les requêtes HTTP, délègue tout à
Presence (voir presence.py), ne fait aucun calcul métier ici à part
attacher le statut calculé d'un professeur pour la sortie JSON.
"""

import datetime as dt

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .presence import Presence, statut_prof
from .schemas import (
    HeuresSortie,
    PresenceEleveModification,
    PresenceEleveSortie,
    PresenceProfModification,
    PresenceProfSortie,
    SeanceCreation,
    SeanceSortie,
)


class PresenceReceiver:
    def __init__(self, client: Presence, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/cours/{cours_id}/seances", response_model=list[SeanceSortie])(
            self.lister_seances
        )
        self.app.post(
            "/cours/{cours_id}/seances", response_model=SeanceSortie, status_code=201
        )(self.creer_seance)
        self.app.get("/seances/{seance_id}", response_model=SeanceSortie)(self.obtenir_seance)
        self.app.delete("/seances/{seance_id}", status_code=204)(self.supprimer_seance)

        self.app.get(
            "/seances/{seance_id}/eleves", response_model=list[PresenceEleveSortie]
        )(self.presences_eleves)
        self.app.put(
            "/seances/{seance_id}/eleves/{eleve_id}", response_model=PresenceEleveSortie
        )(self.modifier_presence_eleve)

        self.app.get(
            "/seances/{seance_id}/profs", response_model=list[PresenceProfSortie]
        )(self.presences_profs)
        self.app.put(
            "/seances/{seance_id}/profs/{professeur_id}", response_model=PresenceProfSortie
        )(self.modifier_presence_prof)

        self.app.get("/profs/{professeur_id}/heures", response_model=HeuresSortie)(
            self.heures_professeur
        )

    def lister_seances(self, cours_id: int, db: Session = Depends(get_db)):
        return self.client.lister_seances(db, cours_id)

    def creer_seance(
        self, cours_id: int, donnees: SeanceCreation, db: Session = Depends(get_db)
    ):
        return self.client.creer_seance(db, cours_id, donnees.date)

    def obtenir_seance(self, seance_id: int, db: Session = Depends(get_db)):
        seance = self.client.get_seance(db, seance_id)
        if seance is None:
            raise HTTPException(status_code=404, detail="Séance introuvable")
        return seance

    def supprimer_seance(self, seance_id: int, db: Session = Depends(get_db)):
        if not self.client.supprimer_seance(db, seance_id):
            raise HTTPException(status_code=404, detail="Séance introuvable")

    def presences_eleves(self, seance_id: int, db: Session = Depends(get_db)):
        return self.client.presences_eleves(db, seance_id)

    def modifier_presence_eleve(
        self,
        seance_id: int,
        eleve_id: int,
        donnees: PresenceEleveModification,
        db: Session = Depends(get_db),
    ):
        return self.client.set_presence_eleve(db, seance_id, eleve_id, donnees.statut)

    def _avec_statut(self, db: Session, presence) -> dict:
        seance = self.client.get_seance(db, presence.seance_id)
        cours = self.client.cours.get(db, seance.cours_id) if seance else None
        heure_debut_theorique = cours.heure_debut if cours else None
        return {
            "id": presence.id,
            "seance_id": presence.seance_id,
            "professeur_id": presence.professeur_id,
            "heure_debut_reelle": presence.heure_debut_reelle,
            "heure_fin_reelle": presence.heure_fin_reelle,
            "depassement_minutes": presence.depassement_minutes,
            "statut": statut_prof(presence, heure_debut_theorique),
        }

    def presences_profs(self, seance_id: int, db: Session = Depends(get_db)):
        return [self._avec_statut(db, p) for p in self.client.presences_profs(db, seance_id)]

    def modifier_presence_prof(
        self,
        seance_id: int,
        professeur_id: int,
        donnees: PresenceProfModification,
        db: Session = Depends(get_db),
    ):
        presence = self.client.set_presence_prof(
            db, seance_id, professeur_id, **donnees.model_dump()
        )
        return self._avec_statut(db, presence)

    def heures_professeur(
        self,
        professeur_id: int,
        depuis: str | None = None,
        jusqua: str | None = None,
        db: Session = Depends(get_db),
    ):
        return self.client.heures_professeur(
            db,
            professeur_id,
            depuis=dt.date.fromisoformat(depuis) if depuis else None,
            jusqua=dt.date.fromisoformat(jusqua) if jusqua else None,
        )
