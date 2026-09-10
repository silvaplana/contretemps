"""Connexion et bascule de profil famille (voir spec/SPEC.md §2.2).

Dépend de ecoles (pour les 3 codes d'accès) et comptes (pour trouver le
compte visé) — auth ne possède aucune table à lui, juste de la logique.
"""

from __future__ import annotations

from comptes import Compte, Comptes
from ecoles import Ecoles
from sqlalchemy.orm import Session

# Rang de rôle, du plus faible au plus fort (voir §2.2) : sert à savoir si
# passer d'un profil à l'autre est une montée en privilège (code
# redemandé) ou non. Même règle que le frontend (data/roles.js).
RANG_ROLE = {"eleve": 0, "professeur": 1, "admin": 2}


def montee_en_privilege(depuis_role: str, vers_role: str) -> bool:
    return RANG_ROLE[vers_role] > RANG_ROLE[depuis_role]


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
        correspondre au rôle réellement associé au compte trouvé, dans
        cette école — pas juste être un des 3 codes valides de l'école.
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

        codes_par_role = {
            "admin": ecole.code_acces_admin,
            "professeur": ecole.code_acces_prof,
            "eleve": ecole.code_acces_eleve,
        }
        for compte in candidats:
            if _memes_codes(code, codes_par_role.get(compte.role)):
                return compte
        return None

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
        """Pas de gestion multi-admin pour l'instant (voir spec/SPEC.md
        §8) : LE contact affiché aux profs/élèves qui n'ont pas de
        récupération en libre-service (voir "Code oublié ?")."""
        admins = self.comptes.list_par_role(db, ecole_id, "admin")
        return admins[0] if admins else None

    def verifier_reponse_recuperation(self, db: Session, compte_id: int, reponse: str) -> Compte | None:
        """"Code oublié ?" — réservé aux admins (voir §6.3 :
        `code_recuperation`, demandé à la création). Comparaison
        insensible à la casse/aux espaces, comme un identifiant plutôt
        qu'un mot de passe strict — cohérent avec le reste de l'appli
        (codes d'accès non plus sensibles à la casse dans les faits)."""
        compte = self.comptes.get(db, compte_id)
        if compte is None or compte.role != "admin":
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
        return montee_en_privilege(depuis.role, vers.role)

    def verifier_code_bascule(self, db: Session, vers_compte_id: int, code: str) -> bool:
        vers = self.comptes.get(db, vers_compte_id)
        if vers is None:
            return False
        ecole = self.ecoles.get(db, vers.ecole_id)
        if ecole is None:
            return False
        codes_par_role = {
            "admin": ecole.code_acces_admin,
            "professeur": ecole.code_acces_prof,
            "eleve": ecole.code_acces_eleve,
        }
        return _memes_codes(code, codes_par_role.get(vers.role))
