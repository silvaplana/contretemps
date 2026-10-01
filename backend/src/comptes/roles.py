"""Rôles cumulables d'un compte (voir spec/SPEC.md §2.1 et §6.3bis).

Un compte peut avoir plusieurs rôles (ex. professeur ET admin), stockés
dans `roles_compte` (voir models.py:RoleCompte). **Le reste du code ne lit
jamais ces lignes directement** : il passe par les fonctions ci-dessous.
Si un jour la façon de stocker les rôles change, seul ce fichier change.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .models import Compte

ELEVE = "eleve"
PROFESSEUR = "professeur"
ADMIN = "admin"
OWNER = "owner"
# Propriétaire de l'application, au-dessus des écoles (§2.5) : compte sans
# école, jamais cumulé, jamais attribué depuis l'appli.
SUPERUSER = "superuser"

ROLES = (ELEVE, PROFESSEUR, ADMIN, OWNER, SUPERUSER)

# Rang, du plus faible au plus fort (voir §2.2) : sert à savoir si passer
# d'un profil familial à l'autre est une montée en privilège, et à choisir
# le rôle principal affiché. Owner compte comme Admin : ce n'est qu'un
# droit en plus sur la gestion des admins (§2.4), pas un rang au-dessus.
# Même règle que le frontend (frontend/src/data/roles.js).
RANG = {ELEVE: 0, PROFESSEUR: 1, ADMIN: 2, OWNER: 2, SUPERUSER: 3}


def noms_roles(compte: Compte) -> list[str]:
    """Rôles du compte, du plus fort au plus faible — ordre stable pour
    l'API et les tests."""
    return sorted((r.role for r in compte.roles), key=lambda nom: (-RANG[nom], nom))


def a_le_role(compte: Compte, role: str) -> bool:
    return any(r.role == role for r in compte.roles)


def is_eleve(compte: Compte) -> bool:
    return a_le_role(compte, ELEVE)


def is_prof(compte: Compte) -> bool:
    return a_le_role(compte, PROFESSEUR)


def is_admin(compte: Compte) -> bool:
    return a_le_role(compte, ADMIN)


def is_owner(compte: Compte) -> bool:
    return a_le_role(compte, OWNER)


def is_superuser(compte: Compte) -> bool:
    return a_le_role(compte, SUPERUSER)


def role_principal(noms: Iterable[str]) -> str:
    """Le rôle le plus élevé, Owner ramené à Admin : c'est celui qu'on
    affiche comme libellé ("Admin", "Professeur"...) et qui sert de rang
    pour la bascule de profil familial (§2.2)."""
    noms = [ADMIN if nom == OWNER else nom for nom in noms]
    return max(noms, key=lambda nom: RANG[nom])


def rang(compte: Compte) -> int:
    return RANG[role_principal(r.role for r in compte.roles)]
