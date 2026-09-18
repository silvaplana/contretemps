"""Routes REST des cours — reçoit les requêtes HTTP, délègue tout à
CoursService (voir cours.py), ne fait aucun calcul métier ici.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from comptes import Comptes
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .cours import CoursService
from .schemas import CompteResume, CoursCreation, CoursModification, CoursSortie

if TYPE_CHECKING:
    # Import UNIQUEMENT pour les annotations de type (voir `from __future__
    # import annotations` ci-dessus, qui les rend paresseuses) — jamais
    # exécuté à l'exécution. `messagerie` importe déjà `cours` (voir
    # conversations.py : résolution des membres "cours") ; importer
    # `Evenements` pour de vrai ici créerait un cycle d'import, fragile
    # selon l'ordre d'import réel (main.py, tests...).
    from messagerie import Evenements


class CoursReceiver:
    """Comme les autres receivers (voir main.py) : enregistre ses routes
    sur une app FastAPI existante, partagée avec les autres modules."""

    def __init__(
        self, client: CoursService, app: FastAPI, evenements: Evenements, comptes: Comptes
    ) -> None:
        self.client = client
        self.app = app
        self.evenements = evenements
        self.comptes = comptes
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
        cours = self.client.create(db, ecole_id, **donnees.model_dump())
        self._publier_cours_maj(db, ecole_id)
        return cours

    def modifier(self, cours_id: int, donnees: CoursModification, db: Session = Depends(get_db)):
        cours = self.client.update(db, cours_id, **donnees.model_dump(exclude_unset=True))
        if cours is None:
            raise HTTPException(status_code=404, detail="Cours introuvable")
        self._publier_cours_maj(db, cours.ecole_id)
        return cours

    def supprimer(self, cours_id: int, db: Session = Depends(get_db)):
        # Capturé AVANT suppression : après coup, plus moyen de retrouver
        # son ecole_id pour savoir qui prévenir.
        cours = self.client.get(db, cours_id)
        if cours is None or not self.client.delete(db, cours_id):
            raise HTTPException(status_code=404, detail="Cours introuvable")
        self._publier_cours_maj(db, cours.ecole_id)

    def professeurs(self, cours_id: int, db: Session = Depends(get_db)):
        return self.client.professeurs_du_cours(db, cours_id)

    def ajouter_professeur(self, cours_id: int, compte_id: int, db: Session = Depends(get_db)):
        self.client.ajouter_professeur(db, cours_id, compte_id)
        self._publier_cours_maj_pour(db, cours_id)

    def retirer_professeur(self, cours_id: int, compte_id: int, db: Session = Depends(get_db)):
        self.client.retirer_professeur(db, cours_id, compte_id)
        self._publier_cours_maj_pour(db, cours_id)

    def eleves(self, cours_id: int, db: Session = Depends(get_db)):
        return self.client.eleves_du_cours(db, cours_id)

    def inscrire_eleve(self, cours_id: int, compte_id: int, db: Session = Depends(get_db)):
        self.client.inscrire_eleve(db, cours_id, compte_id)
        self._publier_cours_maj_pour(db, cours_id)

    def desinscrire_eleve(self, cours_id: int, compte_id: int, db: Session = Depends(get_db)):
        self.client.desinscrire_eleve(db, cours_id, compte_id)
        self._publier_cours_maj_pour(db, cours_id)

    def cours_de_leleve(self, eleve_id: int, db: Session = Depends(get_db)):
        return self.client.cours_de_leleve(db, eleve_id)

    def _publier_cours_maj_pour(self, db: Session, cours_id: int) -> None:
        cours = self.client.get(db, cours_id)
        if cours is not None:
            self._publier_cours_maj(db, cours.ecole_id)

    def _publier_cours_maj(self, db: Session, ecole_id: int) -> None:
        """Prévient TOUS les comptes de l'école (SSE, voir Comptes.
        list_ecole) qu'un cours a été créé/modifié/supprimé, ou que ses
        élèves/professeurs ont changé — demande utilisateur du
        2026-09-19 : le sélecteur de cours (voir Header.jsx côté client)
        doit se tenir à jour en direct, comme les conversations. Le
        client recalcule ses propres listes visibles (admin/prof/élève
        n'ont pas les mêmes, voir App.jsx: coursDuProfil) à la réception
        — pas de filtrage par pertinence ici, plus simple et plus sûr
        qu'une logique dupliquée côté serveur."""
        for compte in self.comptes.list_ecole(db, ecole_id):
            self.evenements.publier(compte.id, {"type": "cours_maj"})
