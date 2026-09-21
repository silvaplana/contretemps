"""Routes REST de connexion et de bascule de profil famille (voir spec
§2.2). Pas de session pour les comptes d'école — juste l'identité du compte
trouvé (limite assumée, voir spec §8). Seul le Superuser reçoit un jeton
signé (§2.5, voir securite/jetons.py).
"""

from comptes import Compte, roles
from fastapi import Depends, FastAPI, HTTPException
from securite import jetons
from sqlalchemy.orm import Session

from db import get_db

from .auth import Auth
from .schemas import (
    CompteConnecte,
    Connexion,
    DemandeBascule,
    ConfirmationBascule,
    ConfirmationRecuperation,
    DemandeRecuperation,
    ReponseBascule,
    ReponseRecuperationSortie,
)


def _sortie(compte: Compte, *, admin_actif: bool, jeton: str | None = None) -> CompteConnecte:
    """Réponse de connexion avec les rôles EFFECTIFS de cette connexion : un
    élève promu admin n'a ses rôles admin/owner que s'ils sont actifs
    (§2.4), et alors avec le jeton "admin" qui les active côté serveur."""
    sortie = CompteConnecte.model_validate(compte)
    sortie.roles = roles.roles_effectifs(compte, admin_actif)
    sortie.role = roles.role_principal(sortie.roles)
    sortie.jeton = jeton
    return sortie


class AuthReceiver:
    def __init__(self, client: Auth, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.post("/auth/login", response_model=CompteConnecte)(self.login)
        self.app.post("/auth/bascule/verifier", response_model=ReponseBascule)(
            self.verifier_bascule
        )
        self.app.post("/auth/bascule/confirmer", response_model=CompteConnecte)(
            self.confirmer_bascule
        )
        self.app.post(
            "/auth/recuperation/verifier", response_model=ReponseRecuperationSortie
        )(self.verifier_recuperation)
        self.app.post("/auth/recuperation/repondre", response_model=CompteConnecte)(
            self.repondre_recuperation
        )

    def _connexion(self, db: Session, compte: Compte, code: str):
        """Élève promu admin : droits d'admin actifs seulement avec le code
        ADMIN de l'école (jeton "admin") — avec le code élève, il n'est
        qu'un élève (décision utilisateur du 2026-09-21)."""
        if not roles.admin_sous_condition(compte):
            return compte
        if self.client.code_admin_valide(db, compte, code):
            return _sortie(compte, admin_actif=True, jeton=jetons.emettre(compte.id, portee=jetons.ADMIN))
        return _sortie(compte, admin_actif=False)

    def login(self, donnees: Connexion, db: Session = Depends(get_db)):
        superuser = self.client.connecter_superuser(db, donnees.identifiant, donnees.code)
        if superuser is not None:
            sortie = CompteConnecte.model_validate(superuser)
            sortie.jeton = jetons.emettre(superuser.id)
            return sortie
        compte = self.client.connecter(db, donnees.ecole_id, donnees.identifiant, donnees.code)
        if compte is None:
            self.client.noter_echec_superuser(db, donnees.identifiant)
            # Même message dans tous les cas (y compris Superuser bloqué) :
            # ne rien révéler de l'existence d'un compte.
            raise HTTPException(status_code=401, detail="Identifiant ou code incorrect")
        return self._connexion(db, compte, donnees.code)

    def verifier_bascule(self, donnees: DemandeBascule, db: Session = Depends(get_db)):
        """Le frontend appelle ça avant de basculer : si code_requis est
        faux, il bascule tout de suite (voir §2.2, switch libre vers un
        rôle égal ou inférieur)."""
        code_requis = self.client.demander_code_pour_bascule(
            db, donnees.depuis_compte_id, donnees.vers_compte_id
        )
        return {"code_requis": code_requis}

    def confirmer_bascule(self, donnees: ConfirmationBascule, db: Session = Depends(get_db)):
        if not self.client.verifier_code_bascule(db, donnees.vers_compte_id, donnees.code):
            raise HTTPException(status_code=401, detail="Code incorrect")
        compte = self.client.comptes.get(db, donnees.vers_compte_id)
        if compte is None:
            raise HTTPException(status_code=404, detail="Compte introuvable")
        return self._connexion(db, compte, donnees.code)

    def verifier_recuperation(self, donnees: DemandeRecuperation, db: Session = Depends(get_db)):
        """1ère étape de "Code oublié ?" (§2.2/§2.3) : identifie le rôle du
        compte visé, sans encore révéler ni vérifier quoi que ce soit —
        admin -> le frontend pose la question de récupération ensuite
        (voir repondre_recuperation) ; prof/élève -> juste le contact de
        l'admin à qui demander directement."""
        compte = self.client.resoudre_identifiant(db, donnees.ecole_id, donnees.identifiant)
        if compte is None:
            raise HTTPException(status_code=404, detail="Identifiant introuvable")
        if roles.is_admin(compte):
            return {"role": roles.ADMIN}
        admin = self.client.premier_admin(db, donnees.ecole_id)
        ecole = self.client.ecoles.get(db, donnees.ecole_id)
        return {
            "role": compte.role_principal,
            "admin_nom": admin.nom if admin else None,
            "admin_prenom": admin.prenom if admin else None,
            "admin_email": admin.email if admin else None,
            "ecole_nom": ecole.nom if ecole else None,
        }

    def repondre_recuperation(self, donnees: ConfirmationRecuperation, db: Session = Depends(get_db)):
        """2e étape, admin seulement : bonne réponse -> connecté direct
        (même forme que /auth/login), comme demandé."""
        compte = self.client.resoudre_identifiant(db, donnees.ecole_id, donnees.identifiant)
        if compte is None:
            raise HTTPException(status_code=404, detail="Identifiant introuvable")
        valide = self.client.verifier_reponse_recuperation(db, compte.id, donnees.reponse)
        if valide is None:
            raise HTTPException(status_code=401, detail="Réponse incorrecte")
        # La question de récupération est celle des ADMINS : un élève promu
        # admin qui y répond entre avec ses droits d'admin actifs.
        if roles.admin_sous_condition(valide):
            return _sortie(valide, admin_actif=True, jeton=jetons.emettre(valide.id, portee=jetons.ADMIN))
        return valide
