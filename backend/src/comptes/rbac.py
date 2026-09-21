"""RBAC centralisé : `require_admin` / `require_owner` (voir spec/SPEC.md §2.4).

**La seule implémentation de "qui a le droit de faire quoi"** : les routes
ne testent jamais un rôle elles-mêmes, elles appellent ces fonctions.

Qui appelle ? Le navigateur envoie l'id du profil actif dans l'en-tête
`X-Compte-Id` (voir frontend/src/api/identite.js), lu par `compte_appelant`.
⚠️ Limite assumée (§2.4, §8) : ce backend n'a toujours ni session ni jeton,
le serveur croit cet en-tête sur parole. Ces vérifications empêchent un
profil non-admin d'utiliser une route Admin par erreur ou en contournant
l'interface ; elles n'arrêtent pas quelqu'un qui forge l'en-tête.

**Exception : le Superuser (§2.5)**, qui a tous les droits sur toutes les
écoles, n'est reconnu QUE par un jeton signé par le serveur (en-tête
`Authorization: Bearer ...`, voir securite/jetons.py). Un `X-Compte-Id`
qui désigne le Superuser sans jeton valide est refusé : impossible de
prendre ses droits en connaissant juste son numéro de compte.

**Élève promu administrateur (§2.4)** : ses droits d'admin ne sont actifs
qu'avec un jeton de portée "admin", remis quand il se connecte avec le code
ADMIN de l'école. Avec son seul `X-Compte-Id` (connexion par le code
élève), `require_admin` le refuse comme n'importe quel élève.

Chaque route protégée sait QUELLE école elle touche (via ses paramètres :
`ecole_id`, ou l'école d'un élève, d'un cours...) et la passe ici : un
admin d'une école n'a aucun droit sur une autre (§2.1, écoles étanches).
"""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from db import get_db
from securite import jetons

from . import roles
from .models import Compte

ENTETE_COMPTE = "X-Compte-Id"


def compte_appelant(
    x_compte_id: int | None = Header(default=None),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Compte:
    """Le compte qui fait la requête. Jeton Superuser (`Authorization`) s'il
    y en a un, sinon l'en-tête `X-Compte-Id`. 401 si rien de valable."""
    if authorization and authorization.lower().startswith("bearer "):
        jeton = jetons.depuis_entete(authorization)
        compte = db.get(Compte, jeton.compte_id) if jeton is not None else None
        valide = compte is not None and (
            roles.is_superuser(compte)
            if jeton.portee == jetons.SUPERUSER
            else roles.admin_sous_condition(compte)
        )
        if not valide:
            raise HTTPException(status_code=401, detail="Session expirée : reconnectez-vous")
        # Attribut posé pour la durée de CETTE requête seulement (l'objet
        # vient de la session de base de la requête) : voir
        # droits_admin_actifs.
        compte._admin_par_jeton = jeton.portee == jetons.ADMIN
        return compte
    if x_compte_id is None:
        raise HTTPException(status_code=401, detail="Identité de l'appelant manquante")
    compte = db.get(Compte, x_compte_id)
    if compte is None:
        raise HTTPException(status_code=401, detail="Compte appelant inconnu")
    if roles.is_superuser(compte):
        raise HTTPException(status_code=401, detail="Jeton requis pour ce compte")
    return compte


def droits_admin_actifs(appelant: Compte) -> bool:
    """Un admin ordinaire (ou professeur-admin) les a toujours ; un élève
    promu admin seulement avec son jeton "admin" (voir compte_appelant)."""
    return not roles.admin_sous_condition(appelant) or getattr(appelant, "_admin_par_jeton", False)


def require_admin(appelant: Compte, ecole_id: int | None) -> None:
    """L'appelant doit être admin de `ecole_id` (admin "pur" ou
    professeur-admin). `ecole_id=None` : la ressource visée n'existe pas —
    on vérifie seulement qu'il est admin, la route répondra 404 ensuite
    (inutile de révéler par un 403 qu'un id existe ou non).

    Le Superuser passe toujours, dans n'importe quelle école (§2.5)."""
    if roles.is_superuser(appelant):
        return
    if not roles.is_admin(appelant) or not droits_admin_actifs(appelant):
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    if ecole_id is not None and appelant.ecole_id != ecole_id:
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs de cette école")


def require_owner(appelant: Compte, ecole_id: int | None) -> None:
    """Comme `require_admin`, et l'appelant doit en plus être Owner de
    l'école : gestion de la liste des administrateurs (§2.4). Le
    Superuser passe toujours (§2.5)."""
    require_admin(appelant, ecole_id)
    if not roles.is_superuser(appelant) and not roles.is_owner(appelant):
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs principaux de l'école")


def require_superuser(appelant: Compte) -> None:
    """Réservé au propriétaire de l'application (§2.5) : ce qui touche
    TOUTES les écoles (créer une école, relancer les messages de toutes
    les écoles)."""
    if appelant is None or not roles.is_superuser(appelant):
        raise HTTPException(status_code=403, detail="Réservé au propriétaire de l'application")
