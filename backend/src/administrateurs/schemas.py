from typing import Literal

from pydantic import BaseModel, field_validator, model_validator

# Fonctions au bureau (spec/core.md §6.4), dans l'ordre d'affichage : des
# titres, aucun droit (l'onglet Financier reste la coche Trésorier).
BUREAU_FUNCTIONS = ("president", "vice_president", "secretary", "treasurer")
BureauFunction = Literal["president", "vice_president", "secretary", "treasurer"]


def ordered_functions(functions) -> list[str]:
    """Sans doublon, dans l'ordre de BUREAU_FUNCTIONS."""
    return [f for f in BUREAU_FUNCTIONS if f in set(functions)]


class AdministrateurSortie(BaseModel):
    """Une ligne du tableau des administrateurs (§2.4) : jamais la valeur du
    code de récupération, seulement s'il est défini."""

    id: int
    nom: str
    prenom: str
    email: str | None
    emails: list[str] = []
    est_owner: bool
    # Trésorier (module notes de frais §6) : coché dans ce tableau seulement.
    est_tresorier: bool = False
    bureau_functions: list[str] = []
    # Professeur-admin ou élève-admin : son nom/prénom/email se modifient
    # depuis Admin > Profs ou Admin > Élèves, pas depuis ce tableau (voir
    # administrateurs.py).
    est_prof: bool
    est_eleve: bool


class AdministrateurCreation(BaseModel):
    """Deux façons de créer un admin (§2.4) : un nouveau compte (nom,
    prénom, email) OU un professeur ou élève existant (`compte_id`). Il
    reçoit ensuite son accès par une invitation (spec §2.2)."""

    compte_id: int | None = None
    nom: str | None = None
    prenom: str | None = None
    email: str | None = None
    owner: bool = False

    @model_validator(mode="after")
    def _une_seule_facon(self):
        if self.compte_id is None:
            if not (self.nom or "").strip() or not (self.prenom or "").strip():
                raise ValueError("Nom et prénom obligatoires pour un nouvel administrateur")
        elif self.nom or self.prenom or self.email:
            raise ValueError(
                "Un compte promu admin garde son nom, son prénom et son email : ne pas les fournir"
            )
        return self


class AdministrateurModification(BaseModel):
    """Seulement les champs fournis sont modifiés. `owner` : donner (True)
    ou retirer (False) ce statut, absent pour ne pas y toucher."""

    nom: str | None = None
    prenom: str | None = None
    email: str | None = None
    owner: bool | None = None
    # Donner (True) ou retirer (False) le rôle trésorier ; absent : inchangé.
    tresorier: bool | None = None
    # Remplace les fonctions au bureau ; absent : inchangées.
    bureau_functions: list[BureauFunction] | None = None

    @field_validator("bureau_functions")
    @classmethod
    def _ordre(cls, v):
        return None if v is None else ordered_functions(v)
