"""Session et RBAC centralisés (voir spec/SPEC.md §2.2 et §2.4).

**Qui appelle ?** (`compte_appelant`) Depuis le 2026-10-01, plus rien n'est
cru sur parole. Chaque requête porte :
- un **jeton de session signé** (`Authorization: Bearer ...`, voir
  securite/jetons.py), remis à la connexion, qui désigne une adresse email
  (table `acces_emails`) ;
- le **profil actif** dans `X-Compte-Id` (voir frontend/src/api/identite.js).

Le serveur vérifie le jeton, que le mot de passe n'a pas changé depuis, que
le profil appartient bien à cet email, et que son rang ne dépasse pas celui
de la session (un profil de rang supérieur de la même famille redemande le
mot de passe, voir auth/). Un `X-Compte-Id` seul ne donne plus aucun droit.

**Toutes les routes exigent une session** (`session_requise`, branché sur
l'appli entière dans app/main.py), sauf la courte liste `ROUTES_PUBLIQUES`.

**Qui a le droit de faire quoi ?** `require_admin` / `require_owner` /
`require_superuser` : la seule implémentation, les routes ne testent jamais
un rôle elles-mêmes. Chaque route protégée sait QUELLE école elle touche
(via ses paramètres : `ecole_id`, ou l'école d'un élève, d'un cours...) et
la passe ici : un admin d'une école n'a aucun droit sur une autre (§2.1).

**Le Superuser (§2.5)** n'est reconnu qu'avec un jeton de portée
"superuser" (12 heures).
"""

from __future__ import annotations

from acces import AccesEmail, normaliser_email
from acces.acces import Acces
from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from db import get_db
from saisons import Saison, saison_courante_id
from saisons.portee import TOUTES_SAISONS, saison_demandee
from securite import jetons

from . import roles
from .models import Compte

ENTETE_COMPTE = "X-Compte-Id"
# Jeton prolongé (30 jours glissants, §2.2) : remis dans cet en-tête de
# réponse, que l'appli enregistre à la place de l'ancien.
ENTETE_JETON_RENOUVELE = "X-Jeton-Renouvele"

# Seules routes utilisables SANS session (méthode, chemin déclaré) :
# connexion, liens d'invitation et de réinitialisation, parcours public
# d'inscription d'un élève (frontend-inscription/), et ce dont il a besoin
# (liste des écoles : nom et code postal seulement ; cours proposés).
ROUTES_PUBLIQUES = {
    ("GET", "/health"),
    ("POST", "/auth/login"),
    ("POST", "/auth/mot-de-passe-oublie"),
    ("GET", "/auth/liens/{jeton}"),
    ("POST", "/auth/liens/{jeton}/mot-de-passe"),
    # Appelée par Brevo (remise des mails) : protégée par une clé dans l'adresse.
    ("POST", "/mails/brevo/{cle}"),
    ("GET", "/ecoles"),
    ("GET", "/cours"),
    ("GET", "/push/cle-publique"),
    # Ne révèle qu'un numéro de fiche ; sert à la reprise de session quand
    # la fiche mémorisée date d'une saison terminée (§2.6).
    ("GET", "/comptes/{compte_id}/fiche-courante"),
    ("POST", "/inscriptions"),
    # Brouillon d'une fiche papier lue par un admin : ouvert par son jeton
    # (tiré au hasard), depuis le formulaire d'inscription. La LECTURE
    # d'une fiche (POST /inscriptions/fiches) exige, elle, un admin.
    ("GET", "/inscriptions/fiches/{jeton}"),
    ("GET", "/inscriptions/fiches/{jeton}/pages/{numero}"),
    ("DELETE", "/inscriptions/fiches/{jeton}"),
    ("POST", "/inscriptions/fiches/{jeton}/eleve"),
    ("POST", "/inscriptions/{token}/photo"),
    ("GET", "/inscriptions/{token}"),
    ("POST", "/inscriptions/{token}/paiement/helloasso"),
    ("GET", "/inscriptions/{token}/dossier.pdf"),
    ("GET", "/inscriptions/{token}/facture.pdf"),
    ("POST", "/inscriptions/{token}/paiement/helloasso/verifier"),
    ("POST", "/inscriptions/{token}/paiement/choix"),
    ("POST", "/inscriptions/paiement/helloasso/notification"),
}

_SESSION_EXPIREE = "Session expirée : reconnectez-vous"


def _refus_session() -> HTTPException:
    return HTTPException(status_code=401, detail={"code": "session_expiree", "message": _SESSION_EXPIREE})


def session_de_la_requete(request: Request, db: Session) -> tuple[jetons.Jeton, AccesEmail]:
    """Le jeton et l'adresse email connectée, ou 401. Le jeton est lu dans
    `Authorization`, ou dans le paramètre `jeton` de l'URL pour le flux
    temps réel (EventSource ne sait pas envoyer d'en-tête)."""
    texte = request.headers.get("authorization", "")
    if texte.lower().startswith("bearer "):
        texte = texte[len("bearer "):].strip()
    else:
        texte = request.query_params.get("jeton", "")
    jeton = jetons.lire(texte)
    acces_email = db.get(AccesEmail, jeton.acces_email_id) if jeton is not None else None
    # Mot de passe changé depuis l'émission du jeton : session terminée.
    if acces_email is None or Acces().empreinte(acces_email) != jeton.empreinte:
        raise _refus_session()
    return jeton, acces_email


def _identifier(request: Request, response: Response, db: Session) -> Compte:
    jeton, acces_email = session_de_la_requete(request, db)
    compte_id = request.headers.get(ENTETE_COMPTE) or request.query_params.get("compte")
    if compte_id is None or not str(compte_id).isdigit():
        raise HTTPException(status_code=401, detail="Profil actif manquant")
    # Toutes saisons : l'appelant est cherché même s'il n'est pas de la
    # saison affichée (un admin qui consulte une ancienne saison), ou plus
    # de la saison courante (voir _verifier_saison).
    compte = db.get(Compte, int(compte_id), execution_options={TOUTES_SAISONS: True})
    if compte is None or normaliser_email(compte.email) != acces_email.email:
        raise HTTPException(status_code=401, detail="Ce profil n'appartient pas à votre compte")
    if roles.is_superuser(compte):
        if jeton.portee != jetons.SUPERUSER:
            raise _refus_session()
    else:
        if roles.rang(compte) > jeton.rang:
            raise HTTPException(
                status_code=403,
                detail={"code": "mot_de_passe_requis", "message": "Mot de passe requis pour ce profil"},
            )
        _verifier_saison(db, compte)
    if jetons.a_renouveler(jeton):
        response.headers[ENTETE_JETON_RENOUVELE] = jetons.emettre(
            acces_email.id, portee=jeton.portee, rang=jeton.rang, empreinte=jeton.empreinte
        )
    return compte


def compte_appelant(request: Request, response: Response, db: Session = Depends(get_db)) -> Compte:
    """Le compte qui fait la requête (profil actif d'une session valide),
    sinon 401. Calculé une seule fois par requête."""
    if not hasattr(request.state, "appelant"):
        request.state.appelant = _identifier(request, response, db)
    return request.state.appelant


def session_requise(request: Request, response: Response, db: Session = Depends(get_db)) -> None:
    """Branché sur TOUTES les routes (app/main.py) : pas de session valide,
    pas de réponse — sauf pour `ROUTES_PUBLIQUES`."""
    route = request.scope.get("route")
    if (request.method, getattr(route, "path", None)) in ROUTES_PUBLIQUES:
        return
    compte_appelant(request, response, db)


def meme_personne(appelant: Compte | None, compte_id: int, db: Session) -> None:
    """La route vise la fiche `compte_id` : ce doit être le profil actif, ou
    une autre fiche du même email (un autre profil de la famille). `appelant`
    vaut None seulement dans les tests où la session est neutralisée."""
    if appelant is None or appelant.id == compte_id or roles.is_superuser(appelant):
        return
    cible = db.get(Compte, compte_id, execution_options={TOUTES_SAISONS: True})
    if cible is None or normaliser_email(cible.email) != normaliser_email(appelant.email):
        raise HTTPException(status_code=403, detail="Ce profil n'appartient pas à votre compte")


def _verifier_saison(db: Session, compte: Compte) -> None:
    """Saisons (spec §2.6) :
    - une fiche d'une ancienne saison ne donne plus accès à rien. Si la
      personne a été reprise dans la saison courante, 409 avec l'id de sa
      nouvelle fiche, pour que l'appli bascule dessus sans reconnexion ;
      sinon 401 ;
    - seule la saison courante se consulte, sauf pour un admin de l'école
      (en-tête X-Saison-Id, voir saisons/portee.py)."""
    courante = saison_courante_id(db, compte.ecole_id)
    if compte.saison_id != courante:
        from .comptes import Comptes

        nouvelle = Comptes().fiche_courante(db, compte)
        if nouvelle is not None:
            raise HTTPException(
                status_code=409,
                detail={"code": "nouvelle_saison", "compte_id": nouvelle.id},
            )
        raise HTTPException(
            status_code=401,
            detail={"code": "hors_saison", "message": "Vous n'êtes pas inscrit(e) pour la saison en cours."},
        )
    demandee = saison_demandee()
    if demandee is None or demandee == courante:
        return
    saison = db.get(Saison, demandee)
    if saison is None or saison.ecole_id != compte.ecole_id:
        raise HTTPException(status_code=403, detail="Saison inconnue")
    if not roles.is_admin(compte):
        raise HTTPException(status_code=403, detail="Seuls les administrateurs consultent les anciennes saisons")


def require_admin(appelant: Compte, ecole_id: int | None) -> None:
    """L'appelant doit être admin de `ecole_id` (admin "pur" ou
    professeur-admin). `ecole_id=None` : la ressource visée n'existe pas —
    on vérifie seulement qu'il est admin, la route répondra 404 ensuite
    (inutile de révéler par un 403 qu'un id existe ou non).

    Le Superuser passe toujours, dans n'importe quelle école (§2.5)."""
    if roles.is_superuser(appelant):
        return
    if not roles.is_admin(appelant):
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
