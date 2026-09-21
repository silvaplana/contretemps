from pydantic import BaseModel, Field, model_validator


class AdministrateurSortie(BaseModel):
    """Une ligne du tableau des administrateurs (§2.4) : jamais la valeur du
    code de récupération, seulement s'il est défini."""

    id: int
    nom: str
    prenom: str
    email: str | None
    est_owner: bool
    # Professeur-admin : son nom/prénom/email se modifient depuis Admin >
    # Profs, pas depuis ce tableau (voir administrateurs.py).
    est_prof: bool
    code_recuperation_defini: bool


class AdministrateurCreation(BaseModel):
    """Deux façons de créer un admin (§2.4) : un nouveau compte (nom,
    prénom, email) OU un professeur existant (`professeur_id`). Le code de
    récupération est demandé dans les deux cas."""

    professeur_id: int | None = None
    nom: str | None = None
    prenom: str | None = None
    email: str | None = None
    code_recuperation: str = Field(min_length=1)
    owner: bool = False

    @model_validator(mode="after")
    def _une_seule_facon(self):
        if self.professeur_id is None:
            if not (self.nom or "").strip() or not (self.prenom or "").strip():
                raise ValueError("Nom et prénom obligatoires pour un nouvel administrateur")
        elif self.nom or self.prenom or self.email:
            raise ValueError(
                "Un professeur promu admin garde son nom, son prénom et son email : ne pas les fournir"
            )
        return self


class AdministrateurModification(BaseModel):
    """Seulement les champs fournis sont modifiés. `owner` : donner (True)
    ou retirer (False) ce statut, absent pour ne pas y toucher."""

    nom: str | None = None
    prenom: str | None = None
    email: str | None = None
    code_recuperation: str | None = None
    owner: bool | None = None
