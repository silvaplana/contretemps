from pydantic import BaseModel


class Connexion(BaseModel):
    ecole_id: int
    identifiant: str  # "Prénom Nom" ou email (voir spec §2.2)
    code: str


class CompteConnecte(BaseModel):
    id: int
    ecole_id: int
    famille_id: int
    role: str
    nom: str
    prenom: str
    email: str | None

    model_config = {"from_attributes": True}


class DemandeBascule(BaseModel):
    depuis_compte_id: int
    vers_compte_id: int


class ReponseBascule(BaseModel):
    code_requis: bool


class ConfirmationBascule(BaseModel):
    vers_compte_id: int
    code: str
