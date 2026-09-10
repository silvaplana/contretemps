from pydantic import BaseModel


class CompteModification(BaseModel):
    # Pour l'instant : uniquement email/code_recuperation (Profil admin,
    # voir ProfilScreen.jsx — crayon à côté de chaque champ). nom/prenom
    # pas exposés ici : pas demandé, et eleves/profs ont déjà leurs
    # propres routes de modification pour ces champs (voir §6.4/§6.5).
    email: str | None = None
    code_recuperation: str | None = None


class CompteSortie(BaseModel):
    id: int
    ecole_id: int
    famille_id: int
    role: str
    nom: str
    prenom: str
    email: str | None
    telephone: str | None
    code_recuperation: str | None = None

    model_config = {"from_attributes": True}
