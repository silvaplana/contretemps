"""Gestion de la liste des administrateurs d'une école (voir spec/SPEC.md
§2.4 : Admin > École, tableau des administrateurs).

Un administrateur est un compte qui a le rôle `admin` (§6.3bis) : soit un
admin "pur" (seul rôle admin, + éventuellement owner), soit un
professeur-admin (professeur + admin). Les règles des rôles (owner ⇒ admin,
au moins un Owner par école...) sont appliquées par Comptes.ajouter_role /
retirer_role, pas ici.

Les DROITS (qui peut lister, créer, modifier, supprimer) sont vérifiés par
le receiver via comptes/rbac.py, pas dans ce service.
"""

from __future__ import annotations

from comptes import Compte, Comptes, RegleRoles, roles
from messagerie.models import ConversationMembre, MessageDelivery
from notifications.models import PushSubscription
from sqlalchemy import delete
from sqlalchemy.orm import Session

# Champs d'un professeur-admin qui ne se modifient PAS ici : ils
# appartiennent au professeur et se gèrent depuis Admin > Profs (même
# compte, pas de duplication, §2.4).
CHAMPS_DU_PROFESSEUR = {"nom", "prenom", "email"}


class Administrateurs:
    def __init__(self, comptes: Comptes) -> None:
        self.comptes = comptes

    def lister(self, db: Session, ecole_id: int) -> list[Compte]:
        return self.comptes.list_par_role(db, ecole_id, roles.ADMIN)

    def get(self, db: Session, compte_id: int) -> Compte | None:
        """L'administrateur `compte_id`, ou None s'il n'existe pas ou n'est
        pas administrateur."""
        compte = self.comptes.get(db, compte_id)
        return compte if compte is not None and roles.is_admin(compte) else None

    def creer(
        self,
        db: Session,
        ecole_id: int,
        *,
        nom: str,
        prenom: str,
        email: str | None,
        code_recuperation: str,
        owner: bool,
    ) -> Compte:
        """Nouveau compte admin "pur" (§2.4, 1re façon de créer un admin)."""
        compte = self.comptes.create(
            db,
            ecole_id=ecole_id,
            role=roles.ADMIN,
            nom=nom,
            prenom=prenom,
            email=email,
            code_recuperation=code_recuperation,
        )
        if owner:
            self.comptes.ajouter_role(db, compte, roles.OWNER)
        return compte

    def promouvoir(
        self, db: Session, ecole_id: int, professeur_id: int, *, code_recuperation: str, owner: bool
    ) -> Compte:
        """Professeur existant promu admin (§2.4, 2e façon) : on AJOUTE le
        rôle admin, le rôle professeur reste."""
        prof = self.comptes.get(db, professeur_id)
        if prof is None or prof.ecole_id != ecole_id or not roles.is_prof(prof):
            raise LookupError("Professeur introuvable dans cette école")
        if roles.is_admin(prof):
            raise RegleRoles("Ce professeur est déjà administrateur")
        self.comptes.ajouter_role(db, prof, roles.ADMIN)
        self.comptes.update(db, prof.id, code_recuperation=code_recuperation)
        if owner:
            self.comptes.ajouter_role(db, prof, roles.OWNER)
        return prof

    def modifier(
        self, db: Session, admin: Compte, *, champs: dict, owner: bool | None, par_superuser: bool = False
    ) -> Compte:
        """`champs` : nom, prénom, email, code de récupération (seulement
        ceux fournis). `owner` : True/False pour donner/retirer ce statut,
        None pour ne pas y toucher."""
        if roles.is_prof(admin) and CHAMPS_DU_PROFESSEUR & champs.keys():
            raise RegleRoles(
                "Le nom, le prénom et l'email d'un professeur se modifient depuis Admin > Profs"
            )
        if champs:
            self.comptes.update(db, admin.id, **champs)
        if owner is True:
            self.comptes.ajouter_role(db, admin, roles.OWNER)
        elif owner is False:
            self.comptes.retirer_role(db, admin, roles.OWNER, autoriser_sans_owner=par_superuser)
        db.refresh(admin)
        return admin

    def supprimer(self, db: Session, admin: Compte, *, par_superuser: bool = False) -> None:
        """Professeur-admin : retire seulement les rôles admin et owner, le
        compte et le professeur restent. Admin "pur" : supprime le compte et
        ce qui n'a de sens que pour lui ; son HISTORIQUE est conservé (ses
        messages restent dans les conversations, ses vidéos aussi —
        décision utilisateur du 2026-09-21, même règle que pour un élève)."""
        if roles.is_prof(admin):
            self.comptes.retirer_role(db, admin, roles.ADMIN, autoriser_sans_owner=par_superuser)
            return
        # Même règle que retirer_role : jamais une école sans Owner (sauf
        # dépannage par le Superuser, §2.5).
        if not par_superuser and roles.is_owner(admin) and self.comptes.est_seul_owner(db, admin):
            raise RegleRoles("L'école doit garder au moins un Owner")
        # Appartenance directe aux conversations (les membres "cours" se
        # résolvent dynamiquement, rien à nettoyer) ; ses abonnements aux
        # notifications ; les statuts de lecture des messages qu'il a
        # REÇUS (sa boîte de réception). Pas ses messages envoyés.
        db.execute(
            delete(ConversationMembre).where(
                ConversationMembre.membre_type == "compte", ConversationMembre.membre_id == admin.id
            )
        )
        db.execute(delete(PushSubscription).where(PushSubscription.compte_id == admin.id))
        db.execute(delete(MessageDelivery).where(MessageDelivery.destinataire_id == admin.id))
        db.commit()
        self.comptes.delete(db, admin.id)
