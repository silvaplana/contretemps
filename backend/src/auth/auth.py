"""Connexion par mot de passe et bascule de profil famille (voir
spec/SPEC.md §2.2).

Le mot de passe appartient à une adresse email (acces/ : table
`acces_emails`), pas à une fiche : la connexion trouve des fiches par le
nom ou l'email saisi, dans TOUTES les écoles, puis ne garde que celles dont
l'email a ce mot de passe. `auth` ne possède aucune table.
"""

from __future__ import annotations

import unicodedata

from acces import REINITIALISATION, Acces, AccesEmail, normaliser_email
from comptes import Compte, Comptes
from comptes import roles as r
from securite import jetons, limiteur
from sqlalchemy import select
from sqlalchemy.orm import Session


class MotDePasseRequis(Exception):
    """Bascule vers un profil de rang supérieur sans mot de passe (§2.2)."""


def _normaliser(texte: str) -> str:
    """Sans casse ni accents, espaces superflus retirés (même règle que
    comptes/comptes.py : « melanie » trouve « Mélanie »)."""
    sans_accents = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(sans_accents.lower().split())


def _cle_connexion(email: str) -> str:
    return f"connexion:{email}"


def destinataire(fiches: list[Compte]) -> Compte:
    """La personne à qui s'adresse un mail envoyé à une adresse qui porte
    plusieurs profils : celui de plus haut rang, puis le plus ancien (même
    règle que la connexion par email)."""
    return min(fiches, key=lambda c: (-r.rang(c), c.id))


class Auth:
    def __init__(self, comptes: Comptes, acces: Acces) -> None:
        self.comptes = comptes
        self.acces = acces

    # --- Trouver les fiches désignées par ce qui est saisi ---

    def fiches_designees(self, db: Session, identifiant: str) -> list[Compte]:
        """Fiches de TOUTES les écoles (saison courante de chacune, voir
        saisons/portee.py : ces routes ignorent la saison affichée), plus
        le Superuser, que désigne « Prénom Nom » ou un email."""
        cible = _normaliser(identifiant)
        if not cible:
            return []
        toutes = db.scalars(select(Compte).order_by(Compte.id))
        if "@" in cible:
            return [c for c in toutes if c.email and _normaliser(c.email) == cible]
        return [c for c in toutes if _normaliser(f"{c.prenom} {c.nom}") == cible]

    def _emails_dont_le_mot_de_passe_est_bon(self, db: Session, fiches: list[Compte], mot_de_passe: str) -> set[str]:
        """Essais limités PAR EMAIL (§2.2) : 5 mots de passe faux bloquent
        cet email 15 minutes, bon mot de passe compris."""
        bons: set[str] = set()
        for email in {normaliser_email(c.email) for c in fiches} - {None}:
            cle = _cle_connexion(email)
            if limiteur.est_bloque(cle):
                continue
            if self.acces.mot_de_passe_valide(self.acces.par_email(db, email), mot_de_passe):
                limiteur.noter_succes(cle)
                bons.add(email)
            else:
                limiteur.noter_echec(cle)
        return bons

    # --- Connexion ---

    def profils_possibles(self, db: Session, identifiant: str, mot_de_passe: str) -> list[Compte]:
        """Une fiche par école où cette personne peut entrer (le Superuser
        compte comme une « école » à part). Vide : identifiant ou mot de
        passe incorrect. Plusieurs : l'écran demande « Choisissez votre
        école ». Dans une école, plusieurs fiches possibles (famille
        connectée par son email) : celle de plus haut rang, puis la plus
        ancienne (décision utilisateur du 2026-10-01)."""
        fiches = self.fiches_designees(db, identifiant)
        bons = self._emails_dont_le_mot_de_passe_est_bon(db, fiches, mot_de_passe)
        par_ecole: dict[int | None, Compte] = {}
        for fiche in fiches:
            if normaliser_email(fiche.email) not in bons:
                continue
            retenue = par_ecole.get(fiche.ecole_id)
            if retenue is None or r.rang(fiche) > r.rang(retenue):
                par_ecole[fiche.ecole_id] = fiche
        return list(par_ecole.values())

    def ouvrir_session(self, db: Session, compte: Compte, rang: int | None = None) -> str:
        """Le jeton de session pour ce profil : portée "superuser" (12 h)
        pour le Superuser, "standard" (30 jours glissants) sinon."""
        acces_email = self.acces.par_email(db, compte.email)
        return jetons.emettre(
            acces_email.id,
            portee=jetons.SUPERUSER if r.is_superuser(compte) else jetons.STANDARD,
            rang=r.rang(compte) if rang is None else rang,
            empreinte=self.acces.empreinte(acces_email),
        )

    def profil_de_plus_haut_rang(self, db: Session, acces_email: AccesEmail, ecole_id: int | None) -> Compte | None:
        """Après la création du mot de passe par un lien : on entre
        directement, de préférence dans l'école qui a invité."""
        fiches = self.fiches_designees(db, acces_email.email)
        fiches.sort(key=lambda c: (c.ecole_id != ecole_id, -r.rang(c), c.id))
        return fiches[0] if fiches else None

    # --- Bascule de profil famille ---

    def basculer(
        self,
        db: Session,
        jeton: jetons.Jeton,
        acces_email: AccesEmail,
        vers_compte_id: int,
        mot_de_passe: str | None,
    ) -> tuple[Compte, str] | None:
        """Vers un autre profil du même email. Libre vers un rang égal ou
        inférieur ; une montée en privilège redemande le mot de passe
        (§2.2). La session prend le rang du nouveau profil : redescendre
        vers un enfant puis remonter redemande donc le mot de passe.
        None : profil inconnu, ou mot de passe faux."""
        vers = self.comptes.get(db, vers_compte_id)
        if vers is None or r.is_superuser(vers) or normaliser_email(vers.email) != acces_email.email:
            return None
        if r.rang(vers) > jeton.rang:
            if not mot_de_passe:
                raise MotDePasseRequis()
            cle = _cle_connexion(acces_email.email)
            if limiteur.est_bloque(cle) or not self.acces.mot_de_passe_valide(acces_email, mot_de_passe):
                limiteur.noter_echec(cle)
                return None
            limiteur.noter_succes(cle)
        return vers, self.ouvrir_session(db, vers)

    # --- Mot de passe oublié ---

    def liens_de_reinitialisation(self, db: Session, identifiant: str) -> list[tuple[Compte, str]]:
        """(fiche destinataire, jeton en clair) pour chaque adresse que désigne
        l'identifiant — toute personne dont l'email est dans une école,
        même jamais invitée (décision utilisateur du 2026-10-01). Demandes
        limitées par email, comme les essais de connexion."""
        liens = []
        par_email: dict[str, list[Compte]] = {}
        for fiche in self.fiches_designees(db, identifiant):
            if normaliser_email(fiche.email):
                par_email.setdefault(normaliser_email(fiche.email), []).append(fiche)
        for email, fiches in par_email.items():
            cle = f"oubli:{email}"
            if limiteur.est_bloque(cle):
                continue
            limiteur.noter_echec(cle)
            acces_email = self.acces.obtenir_ou_creer(db, email)
            liens.append((destinataire(fiches), self.acces.creer_lien(db, acces_email, REINITIALISATION)))
        return liens

    def changer_mot_de_passe(self, db: Session, acces_email: AccesEmail, ancien: str, nouveau: str) -> bool:
        """Depuis Profil : l'ancien mot de passe est redemandé."""
        cle = _cle_connexion(acces_email.email)
        if limiteur.est_bloque(cle) or not self.acces.mot_de_passe_valide(acces_email, ancien):
            limiteur.noter_echec(cle)
            return False
        limiteur.noter_succes(cle)
        self.acces.definir_mot_de_passe(db, acces_email, nouveau)
        return True
