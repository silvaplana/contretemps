"""Logique métier commune aux comptes (voir spec/SPEC.md §2.1, §6.2, §6.3).

Réutilisée par eleves/profs (création/liste filtrée par rôle) et par auth
(vérification identifiant/code) — comptes ne connaît lui-même ni l'un ni
l'autre, c'est le socle sur lequel ils s'appuient.
"""

from __future__ import annotations

import unicodedata

from groups import rights, teachers
from saisons import saison_courante_id
from saisons.portee import TOUTES_SAISONS
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from . import roles as r
from .models import Compte, EmailCompte, Famille, RoleCompte, separer_emails


def _entrer_dans_le_groupe(db: Session, compte: Compte, role: str) -> None:
    """Professeur et Trésorier sont des groupes (comptes/roles.py)."""
    if role == r.PROFESSEUR:
        teachers.add(db, compte)
    else:
        rights.add(db, compte, r.DROIT_FINANCIER)


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

    def get_toutes_saisons(self, db: Session, compte_id: int) -> Compte | None:
        """Comme `get`, mais trouve aussi une fiche d'une autre saison que
        celle affichée (voir saisons/portee.py)."""
        return db.get(Compte, compte_id, execution_options={TOUTES_SAISONS: True})

    def est_de_la_saison_courante(self, db: Session, compte: Compte) -> bool:
        """Toujours vrai pour le Superuser, qui n'a ni école ni saison."""
        return compte.ecole_id is None or compte.saison_id == saison_courante_id(db, compte.ecole_id)

    def fiche_courante(self, db: Session, compte: Compte) -> Compte | None:
        """La fiche de la même personne dans la saison courante (§2.6), en
        suivant les recopies d'une saison à l'autre ; None si elle n'y a
        pas été reprise."""
        vues = set()
        while not self.est_de_la_saison_courante(db, compte):
            vues.add(compte.id)
            suivante = db.scalar(
                select(Compte)
                .where(Compte.compte_precedent_id == compte.id)
                .execution_options(**{TOUTES_SAISONS: True})
            )
            if suivante is None or suivante.id in vues:
                return None
            compte = suivante
        return compte

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
                .where(Compte.ecole_id == ecole_id, r.filtre_role(role))
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
        cible = _normaliser(email.strip())
        for compte in db.scalars(
            select(Compte).where(Compte.ecole_id == ecole_id, Compte.adresses.any()).order_by(Compte.id)
        ):
            if any(_normaliser(e) == cible for e in compte.emails):
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
            requete = requete.where(r.filtre_role(role))
        return [
            compte
            for compte in db.scalars(requete)
            if _normaliser(compte.nom) == nom_cible and _normaliser(compte.prenom) == prenom_cible
        ]

    def recalculer_familles(self, db: Session, ecole_id: int | None) -> None:
        """Famille = les fiches de l'école (saison affichée) qui ont le même
        email du payeur (spec/core.md §4.4, `Compte.payeur`), calculée,
        jamais éditée. Une fiche sans email reste seule. Chaque groupe garde,
        si possible, la famille que la plupart de ses membres avaient déjà :
        rien ne bouge pour les familles inchangées."""
        if ecole_id is None:
            return
        db.flush()
        comptes = list(db.scalars(select(Compte).where(Compte.ecole_id == ecole_id).order_by(Compte.id)))
        groupes: dict[object, list[Compte]] = {}
        for c in comptes:
            groupes.setdefault(c.payeur or c.id, []).append(c)
        prises: set[int] = set()
        # Les plus grands groupes choisissent d'abord leur famille.
        for membres in sorted(groupes.values(), key=lambda g: (-len(g), g[0].id)):
            votes: dict[int, int] = {}
            for c in membres:
                if c.famille_id is not None and c.famille_id not in prises:
                    votes[c.famille_id] = votes.get(c.famille_id, 0) + 1
            if votes:
                famille_id = max(votes, key=lambda f: (votes[f], -f))
            else:
                famille = Famille(ecole_id=ecole_id)
                db.add(famille)
                db.flush()
                famille_id = famille.id
            prises.add(famille_id)
            for c in membres:
                if c.famille_id != famille_id:
                    c.famille_id = famille_id
        db.flush()

    def profils_de_l_email(self, db: Session, compte: Compte, emails: list[str]) -> list[Compte]:
        """Pour le sélecteur de profil (§2.1, §4) : les fiches de la même
        école (saison affichée) qui portent l'email connecté — pas toute
        la famille, pour que deux sœurs n'entrent pas l'une chez l'autre
        avec leur propre mot de passe. La fiche elle-même au minimum."""
        if compte.ecole_id is None or not emails:
            return [compte]
        return list(
            db.scalars(
                select(Compte)
                .where(
                    Compte.ecole_id == compte.ecole_id,
                    Compte.adresses.any(EmailCompte.email.in_(separer_emails(emails))),
                )
                .order_by(Compte.id)
            )
        ) or [compte]

    def create(
        self,
        db: Session,
        ecole_id: int,
        role: str,
        nom: str,
        prenom: str,
        email=None,
        telephone: str | None = None,
    ) -> Compte:
        if role not in r.ROLES or role in (r.OWNER, r.TRESORIER, r.SUPERUSER):
            # Owner ne se donne pas à la création : il s'ajoute à un admin
            # (voir ci-dessous et §2.4), jamais seul (owner ⇒ admin).
            raise ValueError(f"Rôle inconnu ou non attribuable à la création : {role}")
        # Le premier admin d'une école en devient Owner (§2.4) — décidé
        # AVANT d'ajouter ce compte, sinon il se compterait lui-même.
        devient_owner = role == r.ADMIN and not self.list_par_role(db, ecole_id, r.OWNER)
        compte = Compte(
            ecole_id=ecole_id,
            nom=nom,
            prenom=prenom,
            telephone=telephone,
        )
        # `email` : une adresse, plusieurs séparées par « ; » ou « , », ou
        # une liste (§2.1, plusieurs emails par fiche).
        compte.definir_emails(email)
        if role != r.PROFESSEUR:
            compte.roles.append(RoleCompte(role=role))
        if devient_owner:
            compte.roles.append(RoleCompte(role=r.OWNER))
        db.add(compte)
        self.recalculer_familles(db, ecole_id)
        if role == r.PROFESSEUR:
            _entrer_dans_le_groupe(db, compte, role)
        db.commit()
        db.refresh(compte)
        return compte

    def update(self, db: Session, compte_id: int, **champs) -> Compte | None:
        """Champs communs (nom/prénom/email/téléphone) — utilisé par
        eleves/profs pour éditer leur part de `Compte` (les champs
        spécifiques au rôle sont gérés dans leur propre module), et par
        Profil admin (crayon email/téléphone)."""
        compte = self.get(db, compte_id)
        if compte is None:
            return None
        # Emails (§2.1) : `emails` (liste) ou `email` (texte, plusieurs
        # adresses séparées par « ; » ou « , »). Le regroupement familial
        # (§6.2) suit : recalculé dès que les emails changent.
        emails = champs.pop("emails", None)
        if emails is None and "email" in champs:
            emails = champs.pop("email") or []
        champs.pop("email", None)
        famille_a_revoir = emails is not None and compte.definir_emails(emails)
        # Email du payeur (§4.4) : une adresse, vide = le premier email.
        if "payer_email" in champs:
            payeur = separer_emails(champs.pop("payer_email"))
            if len(payeur) > 1:
                raise ValueError("Un seul email du payeur")
            famille_a_revoir |= compte.payer_email != (payeur[0] if payeur else None)
            compte.payer_email = payeur[0] if payeur else None
        if famille_a_revoir:
            self.recalculer_familles(db, compte.ecole_id)
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
        """Règles : `owner` et `tresorier` exigent `admin`. Sans effet si le
        compte a déjà ce rôle."""
        if role not in r.ROLES:
            raise RegleRoles(f"Rôle inconnu : {role}")
        if role == r.SUPERUSER or r.is_superuser(compte):
            # Jamais depuis l'appli : seulement par la commande serveur
            # (voir app/creer_superuser.py et §2.5).
            raise RegleRoles("Le rôle Superuser ne s'attribue pas depuis l'application")
        if r.a_le_role(compte, role):
            return
        if role == r.OWNER and not r.is_admin(compte):
            raise RegleRoles("Seul un administrateur peut être administrateur principal")
        if role == r.TRESORIER and not r.is_admin(compte):
            raise RegleRoles("Seul un administrateur peut être trésorier")
        # Une personne = une fiche (spec/core.md §4, décision de Seb du
        # 2026-10-18) : tous les rôles se cumulent, élève et professeur
        # compris. Le rôle élève vient avec sa fiche élève : l'ajouter par
        # Eleves.create ou la fusion, jamais seul.
        if role in r.ROLES_EN_GROUPE:
            _entrer_dans_le_groupe(db, compte, role)
        else:
            compte.roles.append(RoleCompte(role=role))
        db.commit()
        db.refresh(compte)

    def retirer_role(
        self, db: Session, compte: Compte, role: str, *, autoriser_sans_owner: bool = False
    ) -> None:
        """Retirer `admin` retire aussi `owner` et `tresorier` (tous deux ⇒ admin). Refusé si
        l'école se retrouverait sans aucun Owner, ou le compte sans rôle.
        `autoriser_sans_owner` : réservé au Superuser, qui peut dépanner une
        école en retirant même son dernier Owner (§2.5)."""
        a_retirer = {role, r.OWNER, r.TRESORIER} if role == r.ADMIN else {role}
        restants = [ligne for ligne in compte.roles if ligne.role not in a_retirer]
        en_groupe = [role for role in r.ROLES_EN_GROUPE if role not in a_retirer and r.a_le_role(compte, role)]
        if not restants and not en_groupe:
            raise RegleRoles("Un compte doit garder au moins un rôle")
        if (
            not autoriser_sans_owner
            and r.OWNER in a_retirer
            and r.is_owner(compte)
            and self.est_seul_owner(db, compte)
        ):
            raise RegleRoles("L'école doit garder au moins un administrateur principal")
        compte.roles = restants
        if r.PROFESSEUR in a_retirer:
            teachers.remove(db, compte)
        if r.TRESORIER in a_retirer:
            rights.remove(db, compte, r.DROIT_FINANCIER)
        db.commit()
        db.refresh(compte)

    def est_seul_owner(self, db: Session, compte: Compte) -> bool:
        """Ce compte est-il le DERNIER Owner de son école ?"""
        owners = self.list_par_role(db, compte.ecole_id, r.OWNER)
        return [c.id for c in owners] == [compte.id]

    # --- Superuser (§2.5) : hors de toute école ---

    def superusers(self, db: Session) -> list[Compte]:
        """Tous les Superusers (comptes hors école, §2.5), triés par id."""
        return list(
            db.scalars(
                select(Compte)
                .join(RoleCompte, RoleCompte.compte_id == Compte.id)
                .where(Compte.ecole_id.is_(None), RoleCompte.role == r.SUPERUSER)
                .order_by(Compte.id)
            )
        )

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
            noms |= {_normaliser(e) for e in compte.emails}
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
            compte = Compte(ecole_id=None, famille_id=None, nom=nom, prenom=prenom)
            compte.definir_emails(email)
            compte.roles.append(RoleCompte(role=r.SUPERUSER))
            db.add(compte)
        compte.nom, compte.prenom = nom, prenom
        # Le mot de passe vit dans `acces_emails`, sur la ligne de son email
        # (§6.3ter), comme pour tout le monde.
        from acces import Acces
        from acces.models import maintenant

        acces_email = Acces().obtenir_ou_creer(db, email)
        acces_email.mot_de_passe_hache = mot_de_passe_hache
        if acces_email.profil_finalise_le is None:
            acces_email.profil_finalise_le = maintenant()
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
        ecole_id = compte.ecole_id
        from groups import GroupMember

        from members import MemberValue

        db.execute(delete(GroupMember).where(GroupMember.member_id == compte.id))
        db.execute(delete(MemberValue).where(MemberValue.member_id == compte.id))
        db.delete(compte)
        # Une fiche peut être le seul lien entre deux groupes (§6.2).
        self.recalculer_familles(db, ecole_id)
        db.commit()
        return True

    def membres_de_la_famille(self, db: Session, compte_id: int) -> list[Compte]:
        """Les comptes de la même famille, lui compris (vue d'ensemble :
        ce n'est PAS la liste du sélecteur de profil, voir
        profils_de_l_email)."""
        compte = self.get(db, compte_id)
        if compte is None:
            return []
        return list(
            db.scalars(select(Compte).where(Compte.famille_id == compte.famille_id))
        )
