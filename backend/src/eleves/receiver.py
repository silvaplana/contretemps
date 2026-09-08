"""Routes REST des élèves — reçoit les requêtes HTTP, délègue tout à
Eleves (voir eleves.py) + Comptes (champs communs), ne fait aucun calcul
métier ici à part fusionner Compte+ProfilEleve pour la sortie JSON.
"""

from comptes import Comptes, Compte
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .eleves import Eleves, calculer_age
from .models import ProfilEleve
from .schemas import (
    ContactCreation,
    ContactModification,
    ContactSortie,
    EleveCreation,
    EleveModification,
    EleveSortie,
)


def _fusionner(compte: Compte, profil: ProfilEleve) -> dict:
    return {
        "id": compte.id,
        "ecole_id": compte.ecole_id,
        "nom": compte.nom,
        "prenom": compte.prenom,
        "email": compte.email,
        "telephone": compte.telephone,
        "date_naissance": profil.date_naissance,
        "age": calculer_age(profil.date_naissance),
        "adresse": profil.adresse,
        "allergies": profil.allergies,
        "traitement_medical": profil.traitement_medical,
        "informations_importantes": profil.informations_importantes,
        "statut_paiement": profil.statut_paiement,
        "montant_total_annee": profil.montant_total_annee,
        "montant_paye": profil.montant_paye,
        "commentaire_admin": profil.commentaire_admin,
        "contacts": [],
    }


class ElevesReceiver:
    """Comme les autres receivers (voir main.py) : enregistre ses routes
    sur une app FastAPI existante, partagée avec les autres modules."""

    def __init__(self, client: Eleves, comptes: Comptes, app: FastAPI) -> None:
        self.client = client
        self.comptes = comptes
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/eleves", response_model=list[EleveSortie])(self.lister)
        self.app.get("/eleves/{eleve_id}", response_model=EleveSortie)(self.obtenir)
        self.app.post("/eleves", response_model=EleveSortie, status_code=201)(self.creer)
        self.app.put("/eleves/{eleve_id}", response_model=EleveSortie)(self.modifier)

        self.app.get("/eleves/{eleve_id}/contacts", response_model=list[ContactSortie])(
            self.lister_contacts
        )
        self.app.post(
            "/eleves/{eleve_id}/contacts", response_model=ContactSortie, status_code=201
        )(self.ajouter_contact)
        self.app.put("/contacts/{contact_id}", response_model=ContactSortie)(
            self.modifier_contact
        )
        self.app.delete("/contacts/{contact_id}", status_code=204)(self.supprimer_contact)

    def _obtenir_ou_404(self, db: Session, eleve_id: int) -> tuple[Compte, ProfilEleve]:
        compte = self.client.get_compte(db, eleve_id)
        profil = self.client.get_profil(db, eleve_id) if compte else None
        if compte is None or profil is None:
            raise HTTPException(status_code=404, detail="Élève introuvable")
        return compte, profil

    def lister(self, ecole_id: int, db: Session = Depends(get_db)):
        sortie = []
        for compte in self.client.list(db, ecole_id):
            profil = self.client.get_profil(db, compte.id)
            if profil is None:
                continue
            corps = _fusionner(compte, profil)
            corps["contacts"] = self.client.contacts_de_leleve(db, compte.id)
            sortie.append(corps)
        return sortie

    def obtenir(self, eleve_id: int, db: Session = Depends(get_db)):
        compte, profil = self._obtenir_ou_404(db, eleve_id)
        corps = _fusionner(compte, profil)
        corps["contacts"] = self.client.contacts_de_leleve(db, eleve_id)
        return corps

    def creer(self, ecole_id: int, donnees: EleveCreation, db: Session = Depends(get_db)):
        compte, profil = self.client.create(db, ecole_id, **donnees.model_dump())
        corps = _fusionner(compte, profil)
        corps["contacts"] = []
        return corps

    def modifier(self, eleve_id: int, donnees: EleveModification, db: Session = Depends(get_db)):
        champs = donnees.model_dump(exclude_unset=True)
        champs_compte = {
            cle: champs.pop(cle) for cle in ("nom", "prenom", "email", "telephone") if cle in champs
        }
        if champs_compte:
            self.comptes.update(db, eleve_id, **champs_compte)
        if champs:
            self.client.update_profil(db, eleve_id, **champs)
        compte, profil = self._obtenir_ou_404(db, eleve_id)
        corps = _fusionner(compte, profil)
        corps["contacts"] = self.client.contacts_de_leleve(db, eleve_id)
        return corps

    def lister_contacts(self, eleve_id: int, db: Session = Depends(get_db)):
        return self.client.contacts_de_leleve(db, eleve_id)

    def ajouter_contact(
        self, eleve_id: int, donnees: ContactCreation, db: Session = Depends(get_db)
    ):
        return self.client.ajouter_contact(db, eleve_id, **donnees.model_dump())

    def modifier_contact(
        self, contact_id: int, donnees: ContactModification, db: Session = Depends(get_db)
    ):
        contact = self.client.modifier_contact(
            db, contact_id, **donnees.model_dump(exclude_unset=True)
        )
        if contact is None:
            raise HTTPException(status_code=404, detail="Contact introuvable")
        return contact

    def supprimer_contact(self, contact_id: int, db: Session = Depends(get_db)):
        if not self.client.supprimer_contact(db, contact_id):
            raise HTTPException(status_code=404, detail="Contact introuvable")
