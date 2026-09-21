from pydantic import AliasChoices, BaseModel, Field


class Connexion(BaseModel):
    ecole_id: int
    identifiant: str  # "Prénom Nom" ou email (voir spec §2.2)
    code: str


class CompteConnecte(BaseModel):
    id: int
    # Vides pour le Superuser seulement (compte hors école, §2.5).
    ecole_id: int | None
    famille_id: int | None
    # Rôles cumulables (§6.3bis) : `role` est le rôle PRINCIPAL (le plus
    # élevé, pour l'affichage et le rang), `roles` la liste complète.
    # Lus sur le Compte via ses propriétés role_principal/noms_roles.
    role: str = Field(validation_alias=AliasChoices("role_principal", "role"))
    roles: list[str] = Field(default_factory=list, validation_alias=AliasChoices("noms_roles", "roles"))
    nom: str
    prenom: str
    email: str | None
    telephone: str | None = None
    # Jamais la VALEUR du code de récupération : il suffit, via "Code
    # oublié ?", à se connecter en admin (§2.2). Jusqu'au 2026-09-21 il
    # était renvoyé ici, y compris par des routes lues par tout le monde
    # (GET /comptes?role=admin, messagerie). Juste s'il est défini ; on le
    # MODIFIE toujours via CompteModification.
    code_recuperation_defini: bool = False
    # Jeton signé de 12 h, remis UNIQUEMENT à la connexion du Superuser
    # (§2.5) : le navigateur le renvoie à chaque requête. Absent pour
    # les comptes d'école.
    jeton: str | None = None

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
