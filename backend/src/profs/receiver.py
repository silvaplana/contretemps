"""Routes REST des professeurs — reçoit les requêtes HTTP, délègue tout à
Profs (voir profs.py). L'assignation à un cours passe par les routes déjà
existantes du module cours (/cours/{id}/professeurs/{compte_id}), pas
dupliquées ici.
"""

from comptes import Compte, rbac
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
        self.app.post(
            "/profs",
            response_model=ProfSortie,
            status_code=201,
            dependencies=[Depends(self._admin_ecole)],
        )(self.creer)
        self.app.put(
            "/profs/{prof_id}", response_model=ProfSortie, dependencies=[Depends(self._admin_du_prof)]
        )(self.modifier)
        self.app.delete(
            "/profs/{prof_id}", status_code=204, dependencies=[Depends(self._admin_du_prof)]
        )(self.supprimer)

    # --- RBAC (spec §2.4) : l'école que touche chaque route protégée, la
    # règle elle-même étant dans comptes/rbac.py. ---

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _admin_du_prof(
        self,
        prof_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ) -> None:
        prof = self.client.comptes.get(db, prof_id)
        rbac.require_admin(appelant, prof.ecole_id if prof else None)

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
