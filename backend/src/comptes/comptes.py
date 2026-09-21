"""Logique métier commune aux comptes (voir spec/SPEC.md §2.1, §6.2, §6.3).

Réutilisée par eleves/profs (création/liste filtrée par rôle) et par auth
(vérification identifiant/code) — comptes ne connaît lui-même ni l'un ni
l'autre, c'est le socle sur lequel ils s'appuient.
"""

from __future__ import annotations

import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import roles as r
from .models import Compte, Famille, RoleCompte


class RegleRoles(ValueError):
    """Une règle des rôles cumulables (§6.3bis) serait violée : message
    lisible, renvoyé tel quel à l'écran par les routes (409)."""


def _normaliser(texte: str) -> str:
    """Insensible à la casse ET aux accents (demande utilisateur du
    2026-09-18 : le champ "Nom Prénom ou Email" du login doit accepter
    "Melanie"/"melanie" pour "Mélanie"). Même technique que eleves/
    import_excel.py: _normaliser (NFKD + encodage ascii), mais SANS
    retirer la ponctuation : un email a besoin de garder son "@"/".",
    "Marie-Laure" son trait d'union."""
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii").lower()


class Comptes:
    def get(self, db: Session, compte_id: int) -> Compte | None:
        return db.get(Compte, compte_id)

    def list_ecole(self, db: Session, ecole_id: int) -> list[Compte]:
        """Tous les comptes de l'école, tous rôles confondus — utilisé
        pour diffuser un événement temps réel à tout le monde (voir
        cours/receiver.py : un changement de cours n'a pas un ensemble de
        destinataires simple à calculer côté serveur — admin/profs/élèves
        n'en voient pas les mêmes — plus simple et plus sûr de prévenir
        tout le monde et de laisser le filtrage par rôle, déjà en place
        côté client, faire son travail habituel)."""
        return list(db.scalars(select(Compte).where(Compte.ecole_id == ecole_id)))

    def list_par_role(self, db: Session, ecole_id: int, role: str) -> list[Compte]:
        """Comptes de l'école qui ONT ce rôle, parmi d'autres éventuellement
        (§6.3bis) : un professeur-admin sort à la fois pour "professeur" et
        pour "admin". Triés par id, donc par ancienneté."""
        return list(
            db.scalars(
                select(Compte)
                .join(RoleCompte, RoleCompte.compte_id == Compte.id)
                .where(Compte.ecole_id == ecole_id, RoleCompte.role == role)
                .order_by(Compte.id)
            )
        )

    def trouver_par_email(self, db: Session, ecole_id: int, email: str) -> Compte | None:
        # Insensible à la casse ET aux accents (voir connecter, §2.2 : le
        # champ "Nom Prénom ou Email" du login doit l'être) — comparaison
        # faite en Python (voir _normaliser) plutôt qu'en SQL : ni SQLite
        # ni Postgres n'ont un équivalent portable d'unaccent() en natif.
        # Le filtre ecole_id (indexé) garde ça peu coûteux même sans
        # égalité SQL directe sur `email`.
        cible = _normaliser(email)
        for compte in db.scalars(
            select(Compte).where(Compte.ecole_id == ecole_id, Compte.email.isnot(None))
        ):
            if _normaliser(compte.email) == cible:
                return compte
        return None

    def trouver_par_nom_prenom(
        self, db: Session, ecole_id: int, nom: str, prenom: str, role: str | None = None
    ) -> list[Compte]:
        """Utilisé par auth (connexion par nom+prénom, voir §2.2 —
        insensible à la casse ET aux accents) et par l'import Excel
        (détection de doublon, voir §6.4bis). Voir trouver_par_email
        ci-dessus pour pourquoi la comparaison se fait en Python."""
        nom_cible, prenom_cible = _normaliser(nom), _normaliser(prenom)
        requete = select(Compte).where(Compte.ecole_id == ecole_id)
        if role is not None:
            requete = requete.join(RoleCompte, RoleCompte.compte_id == Compte.id).where(
                RoleCompte.role == role
            )
        return [
            compte
            for compte in db.scalars(requete)
            if _normaliser(compte.nom) == nom_cible and _normaliser(compte.prenom) == prenom_cible
        ]

    def get_or_create_famille(self, db: Session, ecole_id: int, email: str | None) -> Famille:
        """Regroupement automatique par email, DANS une même école (voir
        §6.2). Un compte sans email reste seul dans sa propre famille."""
        if email:
            existant = db.scalar(
                select(Compte).where(Compte.ecole_id == ecole_id, Compte.email == email)
            )
            if existant is not None:
                return existant.famille
        famille = Famille(ecole_id=ecole_id)
        db.add(famille)
        db.flush()
        return famille

    def create(
        self,
        db: Session,
        ecole_id: int,
        role: str,
        nom: str,
        prenom: str,
        email: str | None = None,
        telephone: str | None = None,
        code_recuperation: str | None = None,
    ) -> Compte:
        if role not in r.ROLES or role in (r.OWNER, r.SUPERUSER):
            # Owner ne se donne pas à la création : il s'ajoute à un admin
            # (voir ci-dessous et §2.4), jamais seul (owner ⇒ admin).
            raise ValueError(f"Rôle inconnu ou non attribuable à la création : {role}")
        famille = self.get_or_create_famille(db, ecole_id, email)
        # Le premier admin d'une école en devient Owner (§2.4) — décidé
        # AVANT d'ajouter ce compte, sinon il se compterait lui-même.
        devient_owner = role == r.ADMIN and not self.list_par_role(db, ecole_id, r.OWNER)
        compte = Compte(
            ecole_id=ecole_id,
            famille_id=famille.id,
            nom=nom,
            prenom=prenom,
            email=email,
            telephone=telephone,
            code_recuperation=code_recuperation,
        )
        compte.roles.append(RoleCompte(role=role))
        if devient_owner:
            compte.roles.append(RoleCompte(role=r.OWNER))
        db.add(compte)
        db.commit()
        db.refresh(compte)
        return compte

    def update(self, db: Session, compte_id: int, **champs) -> Compte | None:
        """Champs communs (nom/prénom/email/téléphone) — utilisé par
        eleves/profs pour éditer leur part de `Compte` (les champs
        spécifiques au rôle sont gérés dans leur propre module), et par
        Profil admin (crayon email/téléphone/code_recuperation)."""
        compte = self.get(db, compte_id)
        if compte is None:
            return None
        # Le regroupement familial (§6.2) se fait par email partagé, PAS
        # figé à la création (get_or_create_famille) — sans ça, changer
        # l'email d'un compte laissait `famille_id` périmé : plus
        # regroupé avec la bonne famille (ou toujours avec l'ancienne).
        # Calculé AVANT le setattr ci-dessous : la recherche d'un compte
        # existant avec ce nouvel email doit se faire sur l'email ACTUEL
        # (pas encore changé) de `compte`, sinon il se retrouverait à se
        # matcher lui-même.
        if "email" in champs and champs["email"] != compte.email:
            compte.famille_id = self.get_or_create_famille(db, compte.ecole_id, champs["email"]).id
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable (ex. effacer
        # l'email/téléphone d'un compte).
        for cle, valeur in champs.items():
            setattr(compte, cle, valeur)
        db.commit()
        db.refresh(compte)
        return compte

    # --- Rôles cumulables (§6.3bis) : SEULS points d'écriture des rôles
    # après la création, pour que les règles ci-dessous soient toujours
    # appliquées par le serveur, jamais seulement masquées dans l'IHM. ---

    def ajouter_role(self, db: Session, compte: Compte, role: str) -> None:
        """Règles : `owner` exige `admin` ; `eleve` ne se cumule avec aucun
        autre rôle. Sans effet si le compte a déjà ce rôle."""
        if role not in r.ROLES:
            raise RegleRoles(f"Rôle inconnu : {role}")
        if role == r.SUPERUSER or r.is_superuser(compte):
            # Jamais depuis l'appli : seulement par la commande serveur
            # (voir app/creer_superuser.py et §2.5).
            raise RegleRoles("Le rôle Superuser ne s'attribue pas depuis l'application")
        if r.a_le_role(compte, role):
            return
        if role == r.OWNER and not r.is_admin(compte):
            raise RegleRoles("Seul un administrateur peut être Owner")
        if r.is_eleve(compte) or (role == r.ELEVE and compte.roles):
            raise RegleRoles("Le rôle élève ne se cumule avec aucun autre rôle")
        compte.roles.append(RoleCompte(role=role))
        db.commit()
        db.refresh(compte)

    def retirer_role(
        self, db: Session, compte: Compte, role: str, *, autoriser_sans_owner: bool = False
    ) -> None:
        """Retirer `admin` retire aussi `owner` (owner ⇒ admin). Refusé si
        l'école se retrouverait sans aucun Owner, ou le compte sans rôle.
        `autoriser_sans_owner` : réservé au Superuser, qui peut dépanner une
        école en retirant même son dernier Owner (§2.5)."""
        a_retirer = {role, r.OWNER} if role == r.ADMIN else {role}
        restants = [ligne for ligne in compte.roles if ligne.role not in a_retirer]
        if not restants:
            raise RegleRoles("Un compte doit garder au moins un rôle")
        if (
            not autoriser_sans_owner
            and r.OWNER in a_retirer
            and r.is_owner(compte)
            and self.est_seul_owner(db, compte)
        ):
            raise RegleRoles("L'école doit garder au moins un Owner")
        compte.roles = restants
        db.commit()
        db.refresh(compte)

    def est_seul_owner(self, db: Session, compte: Compte) -> bool:
        """Ce compte est-il le DERNIER Owner de son école ?"""
        owners = self.list_par_role(db, compte.ecole_id, r.OWNER)
        return [c.id for c in owners] == [compte.id]

    # --- Superuser (§2.5) : hors de toute école ---

    def trouver_superuser(self, db: Session, identifiant: str) -> Compte | None:
        """Le Superuser désigné par `identifiant` (email, ou "Prénom Nom"),
        mêmes règles de saisie qu'à la connexion d'école (casse et accents
        ignorés)."""
        cible = _normaliser(identifiant.strip())
        superusers = db.scalars(
            select(Compte)
            .join(RoleCompte, RoleCompte.compte_id == Compte.id)
            .where(Compte.ecole_id.is_(None), RoleCompte.role == r.SUPERUSER)
        )
        for compte in superusers:
            noms = {_normaliser(f"{compte.prenom} {compte.nom}")}
            if compte.email:
                noms.add(_normaliser(compte.email))
            if cible in noms:
                return compte
        return None

    def enregistrer_superuser(
        self, db: Session, *, nom: str, prenom: str, email: str, mot_de_passe_hache: str
    ) -> Compte:
        """Crée le Superuser, ou met à jour celui qui a cet email (nouveau
        mot de passe). Appelé UNIQUEMENT par la commande serveur."""
        compte = self.trouver_superuser(db, email)
        if compte is None:
            compte = Compte(ecole_id=None, famille_id=None, nom=nom, prenom=prenom, email=email)
            compte.roles.append(RoleCompte(role=r.SUPERUSER))
            db.add(compte)
        compte.nom, compte.prenom = nom, prenom
        compte.hashed_password_ou_code = mot_de_passe_hache
        db.commit()
        db.refresh(compte)
        return compte

    def delete(self, db: Session, compte_id: int) -> bool:
        """Suppression du socle commun — les modules eleves/profs
        suppriment d'abord leurs propres tables (ProfilEleve, contacts...)
        avant d'appeler ceci (voir eleves.py)."""
        compte = self.get(db, compte_id)
        if compte is None:
            return False
        db.delete(compte)
        db.commit()
        return True

    def membres_de_la_famille(self, db: Session, compte_id: int) -> list[Compte]:
        """Pour l'écran Profil et le sélecteur de profil famille (§2.1,
        §4) : les autres comptes de la même famille, lui compris."""
        compte = self.get(db, compte_id)
        if compte is None:
            return []
        return list(
            db.scalars(select(Compte).where(Compte.famille_id == compte.famille_id))
        )
