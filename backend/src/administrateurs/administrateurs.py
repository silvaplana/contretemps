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

# Champs d'un professeur-admin ou d'un élève-admin qui ne se modifient PAS
# ici : ils appartiennent au professeur (Admin > Profs) ou à l'élève (Admin >
# Élèves) — même compte, pas de duplication (§2.4).
CHAMPS_IDENTITE = {"nom", "prenom", "email"}


def _promu(compte: Compte) -> bool:
    """Admin qui est AUSSI professeur ou élève : le retirer des admins lui
    laisse son compte et son autre rôle."""
    return roles.is_prof(compte) or roles.is_eleve(compte)


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
        self, db: Session, ecole_id: int, compte_id: int, *, code_recuperation: str, owner: bool
    ) -> Compte:
        """Professeur OU élève existant promu admin (§2.4, 2e façon) : on
        AJOUTE le rôle admin, son rôle de professeur ou d'élève reste. Un
        élève-admin n'a ses droits actifs qu'avec le code ADMIN (voir
        comptes/rbac.py)."""
        compte = self.comptes.get(db, compte_id)
        if compte is None or compte.ecole_id != ecole_id or not _promu(compte):
            raise LookupError("Professeur ou élève introuvable dans cette école")
        if roles.is_admin(compte):
            raise RegleRoles("Ce compte est déjà administrateur")
        self.comptes.ajouter_role(db, compte, roles.ADMIN)
        self.comptes.update(db, compte.id, code_recuperation=code_recuperation)
        if owner:
            self.comptes.ajouter_role(db, compte, roles.OWNER)
        return compte

    def modifier(
        self, db: Session, admin: Compte, *, champs: dict, owner: bool | None, par_superuser: bool = False
    ) -> Compte:
        """`champs` : nom, prénom, email, code de récupération (seulement
        ceux fournis). `owner` : True/False pour donner/retirer ce statut,
        None pour ne pas y toucher."""
        if _promu(admin) and CHAMPS_IDENTITE & champs.keys():
            ecran = "Admin > Profs" if roles.is_prof(admin) else "Admin > Élèves"
            raise RegleRoles(f"Son nom, son prénom et son email se modifient depuis {ecran}")
        if champs:
            self.comptes.update(db, admin.id, **champs)
        if owner is True:
            self.comptes.ajouter_role(db, admin, roles.OWNER)
        elif owner is False:
            self.comptes.retirer_role(db, admin, roles.OWNER, autoriser_sans_owner=par_superuser)
        db.refresh(admin)
        return admin

    def supprimer(self, db: Session, admin: Compte, *, par_superuser: bool = False) -> None:
        """Professeur-admin ou élève-admin : retire seulement les rôles admin
        et owner, le compte et son autre rôle restent. Admin "pur" : supprime le compte et
        ce qui n'a de sens que pour lui ; son HISTORIQUE est conservé (ses
        messages restent dans les conversations, ses vidéos aussi —
        décision utilisateur du 2026-09-21, même règle que pour un élève)."""
        if _promu(admin):
            self.comptes.retirer_role(db, admin, roles.ADMIN, autoriser_sans_owner=par_superuser)
            return
        # Même règle que retirer_role : jamais une école sans Owner (sauf
        # dépannage par le Superuser, §2.5).
        if not par_superuser and roles.is_owner(admin) and self.comptes.est_seul_owner(db, admin):
            raise RegleRoles("L'école doit garder au moins un administrateur principal")
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
