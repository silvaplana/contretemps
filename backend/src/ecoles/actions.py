"""Action de l'école ouverte à l'assistant (spec/modules/assistant-ia.md §3) :
modifier ses coordonnées, comme Admin > École. Réservé aux administrateurs.
"""

from __future__ import annotations

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import rbac
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .ecoles import Ecoles, normaliser_iban, normaliser_siret


class SchoolDetails(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150, description="Nom de l'école.")
    address: str | None = Field(default=None, description="Adresse.")
    postcode: str | None = Field(default=None, description="Code postal.")
    city: str | None = Field(default=None, description="Ville.")
    siret: str | None = Field(default=None, description="SIRET, 14 chiffres.")
    iban: str | None = Field(default=None, description="IBAN.")
    contact_email: str | None = Field(default=None, description="Email de contact.")
    treasurer_email: str | None = Field(default=None, description="Email du trésorier.")


# Champ de l'action -> (colonne de l'école, nom à l'écran).
CHAMPS = {
    "name": ("nom", "nom"), "address": ("adresse", "adresse"), "postcode": ("code_postal", "code postal"),
    "city": ("ville", "ville"), "siret": ("siret", "SIRET"), "iban": ("iban", "IBAN"),
    "contact_email": ("email_contact", "email de contact"), "treasurer_email": ("email_tresorier", "email du trésorier"),
}


def actions(client: Ecoles) -> list[Action]:
    def prepare(db: Session, compte, org_id: int, p: SchoolDetails) -> Ligne:
        rbac.require_admin(compte, org_id)
        donnees = p.model_dump(exclude_none=True)
        if not donnees:
            raise Refus("rien à changer")
        try:  # refusé tout de suite plutôt qu'au clic
            if "siret" in donnees:
                normaliser_siret(donnees["siret"])
            if "iban" in donnees:
                normaliser_iban(donnees["iban"])
        except ValueError as erreur:
            raise Refus(str(erreur)) from erreur
        champs = {CHAMPS[k][0]: v for k, v in donnees.items()}
        libelle = ", ".join(f"{CHAMPS[k][1]} : {v}" for k, v in donnees.items())
        return Ligne(f"Coordonnées de l'école : {libelle}", lambda db: client.update(db, org_id, **champs))

    return [
        Action("update_school", "École", "Modifie les coordonnées de l'école (Admin > École) : nom, adresse, SIRET, "
               "IBAN, emails. Ne donne que les champs qui changent.", SchoolDetails, prepare),
    ]
