"""Connexion et bascule de profil famille (voir spec/SPEC.md §2.2).

Dépend de ecoles (pour les 3 codes d'accès) et comptes (pour trouver le
compte visé) — auth ne possède aucune table à lui, juste de la logique.
"""

from __future__ import annotations

from comptes import Compte, Comptes
from comptes import roles as r
from ecoles import Ecole, Ecoles
from securite import limiteur, mots_de_passe
from sqlalchemy.orm import Session


def montee_en_privilege(depuis: Compte, vers: Compte) -> bool:
    """Passer de `depuis` à `vers` monte-t-il en privilège (§2.2) ? Un
    compte à plusieurs rôles compte pour son rôle le plus élevé."""
    return r.rang(vers) > r.rang(depuis)


def _codes_du_compte(ecole: Ecole, compte: Compte) -> list[str | None]:
    """Codes d'accès acceptés pour ce compte : celui de CHACUN de ses rôles
    (§2.2 — un professeur-admin entre avec le code prof comme avec le code
    admin). Owner n'a pas de code propre : il est toujours aussi Admin."""
    codes_par_role = {
        r.ADMIN: ecole.code_acces_admin,
        r.PROFESSEUR: ecole.code_acces_prof,
        r.ELEVE: ecole.code_acces_eleve,
    }
    return [codes_par_role[nom] for nom in r.noms_roles(compte) if nom in codes_par_role]


def _memes_codes(saisi: str, attendu: str | None) -> bool:
    """Comparaison des codes d'accès insensible à la casse/aux espaces
    superflus (voir connecter/verifier_code_bascule, §2.2) — les codes
    sont de simples mots (ADMIN/PROF/ELEVE...), une différence de casse
    ne doit pas bloquer la connexion."""
    return attendu is not None and saisi.strip().lower() == attendu.strip().lower()


class Auth:
    def __init__(self, ecoles: Ecoles, comptes: Comptes) -> None:
        self.ecoles = ecoles
        self.comptes = comptes

    def connecter(self, db: Session, ecole_id: int, identifiant: str, code: str) -> Compte | None:
        """identifiant = 'Prénom Nom' OU email (voir §2.2). Le code doit
        correspondre à l'UN des rôles du compte trouvé, dans cette école —
        pas juste être un des 3 codes valides de l'école.
        """
        ecole = self.ecoles.get(db, ecole_id)
        if ecole is None:
            return None

        candidats: list[Compte] = []
        if "@" in identifiant:
            trouve = self.comptes.trouver_par_email(db, ecole_id, identifiant)
            if trouve is not None:
                candidats = [trouve]
        elif " " in identifiant:
            # rpartition (pas split) : un prénom composé ("Marie-Laure")
            # n'a pas d'espace, seul le dernier mot est le nom de famille.
            prenom, _, nom = identifiant.rpartition(" ")
            candidats = self.comptes.trouver_par_nom_prenom(db, ecole_id, nom, prenom)

        for compte in candidats:
            if any(_memes_codes(code, attendu) for attendu in _codes_du_compte(ecole, compte)):
                return compte
        return None

    def code_admin_valide(self, db: Session, compte: Compte, code: str) -> bool:
        """`code` est-il le code d'accès ADMIN de l'école du compte ? Sert à
        activer les droits d'un élève promu admin (§2.4)."""
        ecole = self.ecoles.get(db, compte.ecole_id) if compte.ecole_id else None
        return ecole is not None and _memes_codes(code, ecole.code_acces_admin)

    def connecter_superuser(self, db: Session, identifiant: str, code: str) -> Compte | None:
        """Connexion du Superuser (§2.5), tentée AVANT celle des écoles :
        même formulaire, son mot de passe personnel dans le champ "Code".
        None si l'identifiant n'est pas le sien, si le mot de passe est
        faux, ou s'il est bloqué (trop d'essais) — dans tous ces cas, la
        connexion d'école normale est tentée ensuite."""
        superuser = self.comptes.trouver_superuser(db, identifiant)
        if superuser is None or limiteur.est_bloque(superuser.id):
            return None
        if not mots_de_passe.verifier(code, superuser.hashed_password_ou_code):
            return None
        limiteur.noter_succes(superuser.id)
        return superuser

    def noter_echec_superuser(self, db: Session, identifiant: str) -> None:
        """Appelé seulement quand la connexion d'école a AUSSI échoué : si
        l'email du Superuser sert aussi à un compte d'école, une connexion
        d'école réussie ne doit pas compter comme un mot de passe faux."""
        superuser = self.comptes.trouver_superuser(db, identifiant)
        if superuser is not None:
            limiteur.noter_echec(superuser.id)

    def resoudre_identifiant(self, db: Session, ecole_id: int, identifiant: str) -> Compte | None:
        """Même résolution nom+prénom/email que `connecter`, mais sans
        code à vérifier — utilisé par "Code oublié ?" (écran de
        connexion). None si rien trouvé, ou si ambigu (plusieurs comptes
        partagent exactement le même nom+prénom, voir §6.2 : cas très
        rare, pas de moyen de désambiguïser sans code)."""
        ecole = self.ecoles.get(db, ecole_id)
        if ecole is None:
            return None
        if "@" in identifiant:
            return self.comptes.trouver_par_email(db, ecole_id, identifiant)
        if " " in identifiant:
            prenom, _, nom = identifiant.rpartition(" ")
            candidats = self.comptes.trouver_par_nom_prenom(db, ecole_id, nom, prenom)
            return candidats[0] if len(candidats) == 1 else None
        return None

    def premier_admin(self, db: Session, ecole_id: int) -> Compte | None:
        """LE contact affiché aux comptes sans récupération en libre-service
        (voir "Code oublié ?") : le plus ancien Owner de l'école (§2.2,
        §2.4), à défaut le plus ancien admin."""
        for role in (r.OWNER, r.ADMIN):
            comptes = self.comptes.list_par_role(db, ecole_id, role)
            if comptes:
                return comptes[0]
        return None

    def verifier_reponse_recuperation(self, db: Session, compte_id: int, reponse: str) -> Compte | None:
        """"Code oublié ?" — réservé aux admins (voir §6.3 :
        `code_recuperation`, demandé à la création). Comparaison
        insensible à la casse/aux espaces, comme un identifiant plutôt
        qu'un mot de passe strict — cohérent avec le reste de l'appli
        (codes d'accès non plus sensibles à la casse dans les faits)."""
        compte = self.comptes.get(db, compte_id)
        # Tout admin, professeur-admin compris (§2.2, §2.4).
        if compte is None or not r.is_admin(compte):
            return None
        attendu = (compte.code_recuperation or "").strip().lower()
        if not attendu or reponse.strip().lower() != attendu:
            return None
        return compte

    def demander_code_pour_bascule(self, db: Session, depuis_compte_id: int, vers_compte_id: int) -> bool:
        """True si le code du rôle visé doit être redemandé (voir §2.2)."""
        depuis = self.comptes.get(db, depuis_compte_id)
        vers = self.comptes.get(db, vers_compte_id)
        if depuis is None or vers is None:
            return True
        return montee_en_privilege(depuis, vers)

    def verifier_code_bascule(self, db: Session, vers_compte_id: int, code: str) -> bool:
        vers = self.comptes.get(db, vers_compte_id)
        if vers is None:
            return False
        ecole = self.ecoles.get(db, vers.ecole_id)
        if ecole is None:
            return False
        return any(_memes_codes(code, attendu) for attendu in _codes_du_compte(ecole, vers))
