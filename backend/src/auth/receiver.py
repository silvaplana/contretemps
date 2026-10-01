"""Routes de connexion, de bascule de profil, de liens d'invitation et de
réinitialisation, et d'invitation par les admins (voir spec §2.2).

Publiques (voir comptes/rbac.py : ROUTES_PUBLIQUES) : la connexion, « Mot
de passe oublié ? » et les deux routes d'un lien reçu par mail. Toutes les
autres exigent une session.
"""

import logging
import re

from acces import INVITATION, ErreurAcces, AccesEmail
from comptes import Compte, rbac, roles
from ecoles.models import Ecole
from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db

from .auth import Auth, MotDePasseRequis, destinataire
from .invitations import Invitations, raison_echec
from .mails import MailsIndisponibles
from .schemas import (
    Bascule,
    ChangementMotDePasse,
    ChoixEcole,
    Connexion,
    Invitation,
    InvitationSortie,
    LienSortie,
    MotDePasseOublie,
    NouveauMotDePasse,
    SessionOuverte,
    StatutAcces,
)

logger = logging.getLogger(__name__)

# Contrôle de forme seulement (quelque chose@domaine.ext) : évite d'envoyer
# vers une adresse manifestement mal saisie.
_ADRESSE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s.]+$")

# Même message dans tous les cas (compte inconnu, mot de passe faux, email
# bloqué après trop d'essais) : ne rien révéler de l'existence d'un compte.
_REFUS = "Identifiant ou mot de passe incorrect"
_LIEN_INVALIDE = "Ce lien n'est plus valable. Demandez-en un nouveau."


class AuthReceiver:
    def __init__(self, client: Auth, invitations: Invitations, app: FastAPI) -> None:
        self.client = client
        self.invitations = invitations
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.post("/auth/login", response_model=SessionOuverte)(self.login)
        self.app.post("/auth/bascule", response_model=SessionOuverte)(self.basculer)
        self.app.post("/auth/mot-de-passe-oublie", status_code=204)(self.mot_de_passe_oublie)
        self.app.get("/auth/liens/{jeton}", response_model=LienSortie)(self.lire_lien)
        self.app.post("/auth/liens/{jeton}/mot-de-passe", response_model=SessionOuverte)(
            self.definir_mot_de_passe
        )
        self.app.post("/auth/mot-de-passe", response_model=SessionOuverte)(self.changer_mot_de_passe)
        self.app.post("/auth/appli-installee", status_code=204)(self.appli_installee)
        admin = [Depends(self._admin_ecole)]
        self.app.post(
            "/ecoles/{ecole_id}/invitations", response_model=InvitationSortie, dependencies=admin
        )(self.inviter)
        self.app.get(
            "/ecoles/{ecole_id}/acces", response_model=dict[int, StatutAcces], dependencies=admin
        )(self.statuts)

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _session(self, db: Session, compte: Compte) -> SessionOuverte:
        return SessionOuverte(compte=compte, jeton=self.client.ouvrir_session(db, compte))

    # --- Connexion ---

    def login(self, donnees: Connexion, db: Session = Depends(get_db)):
        profils = self.client.profils_possibles(db, donnees.identifiant, donnees.mot_de_passe)
        if donnees.compte_id is not None:
            profils = [p for p in profils if p.id == donnees.compte_id]
        if not profils:
            raise HTTPException(status_code=401, detail=_REFUS)
        if len(profils) == 1:
            return self._session(db, profils[0])
        ecoles = {p.ecole_id: db.get(Ecole, p.ecole_id) for p in profils if p.ecole_id is not None}
        return SessionOuverte(
            choix=[
                ChoixEcole(
                    compte_id=p.id,
                    ecole_id=p.ecole_id,
                    ecole_nom=ecoles[p.ecole_id].nom if p.ecole_id is not None else None,
                    prenom=p.prenom,
                    nom=p.nom,
                    role=p.role_principal,
                )
                for p in profils
            ]
        )

    def basculer(self, donnees: Bascule, request: Request, db: Session = Depends(get_db)):
        jeton, acces_email = rbac.session_de_la_requete(request, db)
        try:
            resultat = self.client.basculer(db, jeton, acces_email, donnees.vers_compte_id, donnees.mot_de_passe)
        except MotDePasseRequis:
            raise HTTPException(
                status_code=403,
                detail={"code": "mot_de_passe_requis", "message": "Mot de passe requis pour ce profil"},
            ) from None
        if resultat is None:
            raise HTTPException(status_code=401, detail="Mot de passe incorrect")
        compte, nouveau_jeton = resultat
        return SessionOuverte(compte=compte, jeton=nouveau_jeton)

    # --- Liens reçus par mail (invitation, réinitialisation) ---

    def _lien_ou_404(self, db: Session, jeton: str):
        lien = self.client.acces.lire_lien(db, jeton)
        if lien is None:
            raise HTTPException(status_code=404, detail=_LIEN_INVALIDE)
        return lien, db.get(AccesEmail, lien.acces_email_id)

    def lire_lien(self, jeton: str, db: Session = Depends(get_db)):
        """Ouverture de « Créer mon mot de passe » : c'est ce qui fait
        passer l'invitation à « consultée » (lien cliqué, §2.2)."""
        lien, acces_email = self._lien_ou_404(db, jeton)
        if lien.type == INVITATION:
            self.client.acces.noter_consultee(db, acces_email)
        fiches = self.client.fiches_designees(db, acces_email.email)
        ecole = db.get(Ecole, lien.ecole_id) if lien.ecole_id else None
        fiches = [f for f in fiches if lien.ecole_id is None or f.ecole_id == lien.ecole_id]
        a_qui = destinataire(fiches) if fiches else None
        return LienSortie(
            type=lien.type,
            email=acces_email.email,
            destinataire=f"{a_qui.prenom} {a_qui.nom}" if a_qui else None,
            prenoms=[f.prenom for f in fiches],
            ecole_nom=ecole.nom if ecole else None,
        )

    def definir_mot_de_passe(self, jeton: str, donnees: NouveauMotDePasse, db: Session = Depends(get_db)):
        """Le lien ne sert qu'une fois ; la personne est ensuite connectée
        directement, sans retaper son mot de passe (§2.2)."""
        lien, acces_email = self._lien_ou_404(db, jeton)
        try:
            self.client.acces.definir_mot_de_passe(db, acces_email, donnees.mot_de_passe)
        except ErreurAcces as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        self.client.acces.consommer_lien(db, lien)
        compte = self.client.profil_de_plus_haut_rang(db, acces_email, lien.ecole_id)
        if compte is None:
            # Mot de passe créé, mais plus aucune fiche à cet email dans la
            # saison courante : rien à ouvrir.
            return SessionOuverte()
        return self._session(db, compte)

    def mot_de_passe_oublie(self, donnees: MotDePasseOublie, db: Session = Depends(get_db)):
        """Toujours la même réponse, qu'un compte existe ou non (§2.2)."""
        for fiche, jeton in self.client.liens_de_reinitialisation(db, donnees.identifiant):
            ecole = db.get(Ecole, fiche.ecole_id) if fiche.ecole_id else None
            try:
                self.invitations.mails.reinitialisation(
                    fiche.email.strip(), ecole.nom if ecole else None, f"{fiche.prenom} {fiche.nom}", jeton
                )
            except Exception:  # noqa: BLE001 — ne rien révéler à l'écran
                logger.exception("Mail de réinitialisation non envoyé")

    def changer_mot_de_passe(
        self, donnees: ChangementMotDePasse, request: Request, db: Session = Depends(get_db)
    ):
        """Depuis Profil. Tous les jetons déjà remis deviennent invalides
        (autres appareils déconnectés) ; celui-ci reçoit un jeton neuf."""
        jeton, acces_email = rbac.session_de_la_requete(request, db)
        try:
            if not self.client.changer_mot_de_passe(db, acces_email, donnees.ancien, donnees.nouveau):
                raise HTTPException(status_code=401, detail="Mot de passe actuel incorrect")
        except ErreurAcces as erreur:
            raise HTTPException(status_code=422, detail=str(erreur)) from erreur
        from securite import jetons

        return SessionOuverte(
            jeton=jetons.emettre(
                acces_email.id,
                portee=jeton.portee,
                rang=jeton.rang,
                empreinte=self.client.acces.empreinte(acces_email),
            )
        )

    def appli_installee(self, request: Request, db: Session = Depends(get_db)):
        """Signalé par l'appli elle-même (§2.2) : le premier signal fixe la
        date, les suivants sont ignorés."""
        _, acces_email = rbac.session_de_la_requete(request, db)
        self.client.acces.noter_appli_installee(db, acces_email)

    # --- Invitation par un admin ---

    def inviter(
        self,
        ecole_id: int,
        donnees: Invitation,
        taches: BackgroundTasks,
        db: Session = Depends(get_db),
    ):
        ecole = db.get(Ecole, ecole_id)
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        emails = self.invitations.emails_a_inviter(db, ecole_id, donnees.compte_ids)
        if not emails:
            raise HTTPException(status_code=409, detail="Aucune adresse email à inviter")
        # Adresses mal saisies : notées en échec dans le Statut, jamais envoyées.
        invalides = [e for e in emails if not _ADRESSE.match(e)]
        for email in invalides:
            self.invitations.noter_adresse_invalide(db, email)
        emails = [e for e in emails if e not in invalides]
        if not emails:
            raise HTTPException(status_code=422, detail=f"Adresse email mal saisie : {', '.join(invalides)}")
        if len(emails) == 1:
            # Une seule adresse : envoi immédiat, l'admin voit tout de
            # suite si le mail est parti.
            try:
                self.invitations.inviter(db, ecole, emails[0])
            except MailsIndisponibles as erreur:
                raise HTTPException(status_code=503, detail=str(erreur)) from erreur
            except Exception as erreur:  # noqa: BLE001
                logger.exception("Invitation non envoyée")
                raise HTTPException(status_code=502, detail=f"{raison_echec(erreur)} : {emails[0]}") from erreur
            return InvitationSortie(emails=1, adresses=emails)
        if not self.invitations.mails.disponible:
            raise HTTPException(status_code=503, detail="L'envoi de mails n'est pas configuré sur ce serveur")
        # « Inviter tous les non-invités » : des dizaines de mails, envoyés
        # après la réponse. Sa propre session de base : celle de la requête
        # est déjà refermée à ce moment-là.
        taches.add_task(self._inviter_en_tache_de_fond, db.get_bind(), ecole_id, emails)
        return InvitationSortie(emails=len(emails), en_cours=True, adresses=emails)

    def _inviter_en_tache_de_fond(self, moteur, ecole_id: int, emails: list[str]) -> None:
        with Session(moteur) as db:
            ecole = db.get(Ecole, ecole_id)
            for email in emails:
                try:
                    self.invitations.inviter(db, ecole, email)
                except Exception:  # noqa: BLE001 — une adresse en échec n'arrête pas les autres
                    db.rollback()
                    logger.exception("Invitation non envoyée à une adresse")

    def statuts(self, ecole_id: int, db: Session = Depends(get_db)):
        return self.invitations.statuts(db, ecole_id)
