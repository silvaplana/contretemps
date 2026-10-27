"""Rôles cumulables d'un compte (voir spec/SPEC.md §2.1 et §6.3bis).

Un compte peut avoir plusieurs rôles (ex. professeur ET admin), stockés
dans `roles_compte` (voir models.py:RoleCompte). **Le reste du code ne lit
jamais ces lignes directement** : il passe par les fonctions ci-dessous.
Si un jour la façon de stocker les rôles change, seul ce fichier change.

Professeur n'est plus une ligne de `roles_compte` depuis le 27/10/2026 :
c'est le groupe « Profs » de la saison (groups/teachers.py, spec/core.md
§5.1). Ce fichier le présente toujours comme un rôle, avec le même rang.
Trésorier non plus : c'est le groupe 🔒 du droit « Accès au Financier »
(groups/rights.py, §5.3). Le contrôle d'un droit passe par `has_right`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

from groups import rights
from groups.models import Group
from groups.teachers import TEACHERS

if TYPE_CHECKING:
    from .models import Compte

ELEVE = "eleve"
PROFESSEUR = "professeur"
ADMIN = "admin"
OWNER = "owner"
# Trésorier (module notes de frais, spec/modules/notes-de-frais.md §6) :
# toujours un admin, comme Owner ; un droit en plus, pas un rang.
TRESORIER = "tresorier"
# Propriétaire de l'application, au-dessus des écoles (§2.5) : compte sans
# école, jamais cumulé, jamais attribué depuis l'appli.
SUPERUSER = "superuser"

ROLES = (ELEVE, PROFESSEUR, ADMIN, OWNER, TRESORIER, SUPERUSER)

# Rang, du plus faible au plus fort (voir §2.2) : sert à savoir si passer
# d'un profil familial à l'autre est une montée en privilège, et à choisir
# le rôle principal affiché. Owner compte comme Admin : ce n'est qu'un
# droit en plus sur la gestion des admins (§2.4), pas un rang au-dessus.
# Même règle que le frontend (frontend/src/data/roles.js).
RANG = {ELEVE: 0, PROFESSEUR: 1, ADMIN: 2, OWNER: 2, TRESORIER: 2, SUPERUSER: 3}

# Le droit déclaré par le module Financier (finances_contretemps/module.py).
DROIT_FINANCIER = "finances.access"
# Rôles qui sont des groupes : rôle → clé du groupe.
ROLES_EN_GROUPE = {PROFESSEUR: TEACHERS, TRESORIER: rights.group_key(DROIT_FINANCIER)}


def _dans_le_groupe(compte: Compte, cle: str) -> bool:
    return any(g.key == cle for g in compte.groups)


def noms_roles(compte: Compte) -> list[str]:
    """Rôles du compte, du plus fort au plus faible — ordre stable pour
    l'API et les tests."""
    noms = [r.role for r in compte.roles]
    noms += [role for role, cle in ROLES_EN_GROUPE.items() if _dans_le_groupe(compte, cle)]
    return sorted(noms, key=lambda nom: (-RANG[nom], nom))


def a_le_role(compte: Compte, role: str) -> bool:
    if role in ROLES_EN_GROUPE:
        return _dans_le_groupe(compte, ROLES_EN_GROUPE[role])
    return any(r.role == role for r in compte.roles)


def filtre_role(role: str):
    """Condition SQL « le compte a ce rôle », pour `select(Compte).where(...)`."""
    from .models import Compte

    if role in ROLES_EN_GROUPE:
        return Compte.groups.any(Group.key == ROLES_EN_GROUPE[role])
    return Compte.roles.any(role=role)


def has_right(compte: Compte, droit: str) -> bool:
    """La seule vérification d'un droit de module (spec/core.md §5.3) : le
    Super User passe toujours ; sinon il faut être dans le groupe 🔒 du droit,
    de sa saison."""
    return is_superuser(compte) or _dans_le_groupe(compte, rights.group_key(droit))


def is_eleve(compte: Compte) -> bool:
    return a_le_role(compte, ELEVE)


def is_prof(compte: Compte) -> bool:
    return a_le_role(compte, PROFESSEUR)


def is_admin(compte: Compte) -> bool:
    return a_le_role(compte, ADMIN)


def is_owner(compte: Compte) -> bool:
    return a_le_role(compte, OWNER)


def is_tresorier(compte: Compte) -> bool:
    return a_le_role(compte, TRESORIER)


def is_superuser(compte: Compte) -> bool:
    return a_le_role(compte, SUPERUSER)


def role_principal(noms: Iterable[str]) -> str:
    """Le rôle le plus élevé, Owner ramené à Admin : c'est celui qu'on
    affiche comme libellé ("Admin", "Professeur"...) et qui sert de rang
    pour la bascule de profil familial (§2.2). Trésorier aussi : un droit
    en plus d'admin, comme Owner."""
    noms = [ADMIN if nom in (OWNER, TRESORIER) else nom for nom in noms]
    return max(noms, key=lambda nom: RANG[nom])


def rang(compte: Compte) -> int:
    return RANG[role_principal(noms_roles(compte))]
