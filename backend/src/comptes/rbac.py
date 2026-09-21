"""RBAC centralisé : `require_admin` / `require_owner` (voir spec/SPEC.md §2.4).

**La seule implémentation de "qui a le droit de faire quoi"** : les routes
ne testent jamais un rôle elles-mêmes, elles appellent ces fonctions.

Qui appelle ? Le navigateur envoie l'id du profil actif dans l'en-tête
`X-Compte-Id` (voir frontend/src/api/identite.js), lu par `compte_appelant`.
⚠️ Limite assumée (§2.4, §8) : ce backend n'a toujours ni session ni jeton,
le serveur croit cet en-tête sur parole. Ces vérifications empêchent un
profil non-admin d'utiliser une route Admin par erreur ou en contournant
l'interface ; elles n'arrêtent pas quelqu'un qui forge l'en-tête. Le vrai
jeton signé arrive avec le Superuser (§2.5).

Chaque route protégée sait QUELLE école elle touche (via ses paramètres :
`ecole_id`, ou l'école d'un élève, d'un cours...) et la passe ici : un
admin d'une école n'a aucun droit sur une autre (§2.1, écoles étanches).
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from . import roles
from .models import Compte

ENTETE_COMPTE = "X-Compte-Id"


def compte_appelant(
    x_compte_id: int | None = Header(default=None), db: Session = Depends(get_db)
) -> Compte:
    """Le compte qui fait la requête (en-tête `X-Compte-Id`). 401 s'il
    manque ou ne correspond à aucun compte."""
    if x_compte_id is None:
        raise HTTPException(status_code=401, detail="Identité de l'appelant manquante")
    compte = db.get(Compte, x_compte_id)
    if compte is None:
        raise HTTPException(status_code=401, detail="Compte appelant inconnu")
    return compte


def require_admin(appelant: Compte, ecole_id: int | None) -> None:
    """L'appelant doit être admin de `ecole_id` (admin "pur" ou
    professeur-admin). `ecole_id=None` : la ressource visée n'existe pas —
    on vérifie seulement qu'il est admin, la route répondra 404 ensuite
    (inutile de révéler par un 403 qu'un id existe ou non)."""
    if not roles.is_admin(appelant):
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    if ecole_id is not None and appelant.ecole_id != ecole_id:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs de cette école")


def require_owner(appelant: Compte, ecole_id: int | None) -> None:
    """Comme `require_admin`, et l'appelant doit en plus être Owner de
    l'école : gestion de la liste des administrateurs (§2.4)."""
    require_admin(appelant, ecole_id)
    if not roles.is_owner(appelant):
        raise HTTPException(status_code=403, detail="Réservé aux Owners de l'école")
