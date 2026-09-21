from pydantic import AliasChoices, BaseModel, Field


class CompteModification(BaseModel):
    # Pour l'instant : uniquement email/telephone/code_recuperation
    # (Profil admin, voir ProfilScreen.jsx — crayon à côté de chaque
    # champ). nom/prenom pas exposés ici : pas demandé, et eleves/profs
    # ont déjà leurs propres routes de modification pour ces champs
    # (voir §6.4/§6.5).
    email: str | None = None
    telephone: str | None = None
    code_recuperation: str | None = None


class CompteSortie(BaseModel):
    id: int
    ecole_id: int
    famille_id: int
    # Rôles cumulables (§6.3bis) : `role` est le rôle PRINCIPAL (le plus
    # élevé, pour l'affichage et le rang), `roles` la liste complète.
    # Lus sur le Compte via ses propriétés role_principal/noms_roles.
    role: str = Field(validation_alias=AliasChoices("role_principal", "role"))
    roles: list[str] = Field(default_factory=list, validation_alias=AliasChoices("noms_roles", "roles"))
    nom: str
    prenom: str
    email: str | None
    telephone: str | None
    # Jamais la VALEUR du code de récupération : il suffit, via "Code
    # oublié ?", à se connecter en admin (§2.2). Jusqu'au 2026-09-21 il
    # était renvoyé ici, y compris par des routes lues par tout le monde
    # (GET /comptes?role=admin, messagerie). Juste s'il est défini ; on le
    # MODIFIE toujours via CompteModification.
    code_recuperation_defini: bool = False

    model_config = {"from_attributes": True}
