from pydantic import AliasChoices, BaseModel, Field


class CompteModification(BaseModel):
    # Pour l'instant : uniquement email/telephone
    # (Profil admin, voir ProfilScreen.jsx — crayon à côté de chaque
    # champ). nom/prenom pas exposés ici : pas demandé, et eleves/profs
    # ont déjà leurs propres routes de modification pour ces champs
    # (voir §6.4/§6.5).
    email: str | None = None
    # Plusieurs emails (§2.1) : la liste remplace `email` si elle est donnée.
    emails: list[str] | None = None
    telephone: str | None = None
    # Email du payeur (spec/core.md §4.4) ; vide = le premier email.
    payer_email: str | None = None


class CompteSortie(BaseModel):
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
    # Toutes les adresses séparées par une virgule (affichage) ; la liste
    # dans `emails` (plusieurs emails par fiche, §2.1).
    email: str | None
    emails: list[str] = Field(default_factory=list)
    telephone: str | None
    payer_email: str | None = None

    model_config = {"from_attributes": True}
