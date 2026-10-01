import datetime as dt

from pydantic import AliasChoices, BaseModel, Field


class Connexion(BaseModel):
    identifiant: str  # "Prénom Nom" ou email (voir spec §2.2)
    mot_de_passe: str
    # Renseigné seulement après « Choisissez votre école » (plusieurs
    # écoles possibles pour cet identifiant et ce mot de passe).
    compte_id: int | None = None


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

    model_config = {"from_attributes": True}


class ChoixEcole(BaseModel):
    """Une ligne de « Choisissez votre école » (§2.2)."""

    compte_id: int
    # Vides pour l'accès Superuser (au-dessus des écoles, §2.5).
    ecole_id: int | None
    ecole_nom: str | None
    prenom: str
    nom: str
    role: str


class SessionOuverte(BaseModel):
    """Réponse d'une connexion : soit `compte` et son `jeton` de session
    (à renvoyer dans `Authorization: Bearer ...`), soit `choix` quand
    plusieurs écoles sont possibles."""

    compte: CompteConnecte | None = None
    jeton: str | None = None
    choix: list[ChoixEcole] = []


class Bascule(BaseModel):
    vers_compte_id: int
    # Seulement pour une montée en privilège (§2.2).
    mot_de_passe: str | None = None


class LienSortie(BaseModel):
    """Ce qu'affiche « Créer mon mot de passe » / « Nouveau mot de passe »."""

    type: str  # "invitation" | "reinitialisation"
    email: str
    # La personne à qui l'on s'adresse (« Prénom Nom »), comme dans le mail.
    destinataire: str | None
    prenoms: list[str]
    ecole_nom: str | None


class NouveauMotDePasse(BaseModel):
    mot_de_passe: str


class MotDePasseOublie(BaseModel):
    identifiant: str


class ChangementMotDePasse(BaseModel):
    ancien: str
    nouveau: str


class Invitation(BaseModel):
    # Fiches à inviter (les fiches sans email sont ignorées ; un seul mail
    # par adresse).
    compte_ids: list[int]


class InvitationSortie(BaseModel):
    # Nombre d'adresses invitées. `en_cours` : les mails partent en tâche
    # de fond (plusieurs adresses), le statut se met à jour au fil de l'eau.
    emails: int
    en_cours: bool = False
    # Les adresses concernées, pour le message affiché à l'admin.
    adresses: list[str] = []


class StatutAcces(BaseModel):
    # pas_email | pas_invite | invite | consultee | finalise | installee |
    # echec_envoi (avec `detail` : la raison)
    statut: str
    date: dt.datetime | None
    detail: str | None = None
