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


class DemandeRecuperation(BaseModel):
    ecole_id: int
    identifiant: str  # "Prénom Nom" ou email (voir spec §2.2)


class ReponseRecuperationSortie(BaseModel):
    role: str  # 'admin' | 'professeur' | 'eleve'
    # Renseignés seulement si role != 'admin' (voir "Code oublié ?" §2.2/§2.3) :
    # contact du (premier) admin de l'école, à qui demander son code.
    admin_nom: str | None = None
    admin_prenom: str | None = None
    admin_email: str | None = None
    ecole_nom: str | None = None


class ConfirmationRecuperation(BaseModel):
    ecole_id: int
    identifiant: str
    reponse: str  # réponse à la question de récupération (admin seulement)
