"""Actions de la messagerie ouvertes à l'assistant (spec/modules/assistant-ia.md §3) :
créer, renommer, supprimer un groupe, y ajouter ou en retirer des membres. Elles passent par les mêmes méthodes
que les écrans d'Admin > Conversations, donc les écrans ouverts se mettent à
jour pareil.
"""

from __future__ import annotations

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import rbac, roles
from comptes.models import Compte
from cours.models import Cours
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .receiver import MessagerieReceiver
from .schemas import ConversationCreation, ConversationModification, MembreEntree


class NewGroup(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="Nom du groupe.")
    member_ids: list[int] = Field(default=[], description="Numéros des personnes (élèves, professeurs, administrateurs).")
    course_ids: list[int] = Field(default=[], description="Numéros des cours dont tous les élèves et professeurs sont membres.")


class RenameGroup(BaseModel):
    group_name: str = Field(description="Nom actuel du groupe.")
    new_name: str = Field(min_length=1, max_length=100, description="Nouveau nom.")


class DeleteGroup(BaseModel):
    group_name: str = Field(description="Nom du groupe à supprimer.")


class GroupMembers(BaseModel):
    group_name: str = Field(description="Nom du groupe.")
    member_ids: list[int] = Field(default=[], description="Numéros des personnes.")
    course_ids: list[int] = Field(default=[], description="Numéros des cours.")


def actions(receiver: MessagerieReceiver) -> list[Action]:
    conversations = receiver.conversations

    def group(db: Session, org_id: int, name: str):
        """Un groupe créé à la main (pas celui d'un cours), par son nom."""
        groupes = [c for c in conversations.lister_ecole(db, org_id) if c.type == "groupe" and c.nom]
        trouve = [c for c in groupes if c.nom.casefold() == name.strip().casefold()]
        if not trouve:
            noms = ", ".join(f"« {c.nom} »" for c in groupes) or "aucun"
            raise Refus(f"pas de groupe « {name} ». Groupes existants : {noms}")
        return trouve[0]

    def members(db: Session, org_id: int, member_ids: list[int], course_ids: list[int]):
        """(noms pour la carte, membres) ; le Super User, hors école, s'ajoute
        dans toute école (spec/core.md §6.1)."""
        personnes = [db.get(Compte, i) for i in dict.fromkeys(member_ids)]
        cours = [db.get(Cours, i) for i in dict.fromkeys(course_ids)]
        if any(x is None or (x.ecole_id != org_id and not roles.is_superuser(x)) for x in personnes) or any(
            c is None or c.ecole_id != org_id for c in cours
        ):
            raise Refus("une personne ou un cours est introuvable dans cette école")
        noms = [f"{x.prenom} {x.nom}".strip() for x in personnes] + [f"le cours {c.nom}" for c in cours]
        membres = [MembreEntree(membre_type="compte", membre_id=x.id) for x in personnes] + [
            MembreEntree(membre_type="cours", membre_id=c.id) for c in cours
        ]
        return noms, membres

    def prepare_create(db: Session, compte, org_id: int, p: NewGroup) -> Ligne:
        rbac.require_admin(compte, org_id)
        noms, membres = members(db, org_id, p.member_ids, p.course_ids)
        donnees = ConversationCreation(nom=p.name.strip(), membres=membres)
        return Ligne(
            f"Créer le groupe « {donnees.nom} » avec {', '.join(noms) or 'personne pour l’instant'}",
            lambda db: receiver.creer(org_id, donnees, db),
        )

    def prepare_rename(db: Session, compte, org_id: int, p: RenameGroup) -> Ligne:
        rbac.require_admin(compte, org_id)
        g = group(db, org_id, p.group_name)
        conversation_id, nom = g.id, p.new_name.strip()
        return Ligne(
            f"Renommer le groupe « {g.nom} » en « {nom} »",
            lambda db: receiver.renommer(conversation_id, ConversationModification(nom=nom), db),
        )

    def prepare_delete(db: Session, compte, org_id: int, p: DeleteGroup) -> Ligne:
        rbac.require_admin(compte, org_id)
        g = group(db, org_id, p.group_name)
        conversation_id = g.id
        return Ligne(
            f"Supprimer le groupe « {g.nom} » (ses messages disparaissent)",
            lambda db: receiver.supprimer(conversation_id, db),
        )

    def prepare_add(db: Session, compte, org_id: int, p: GroupMembers) -> Ligne:
        rbac.require_admin(compte, org_id)
        g = group(db, org_id, p.group_name)
        noms, membres = members(db, org_id, p.member_ids, p.course_ids)
        if not membres:
            raise Refus("personne à ajouter")
        conversation_id = g.id

        def faire(db: Session) -> None:
            for m in membres:
                receiver.ajouter_membre(conversation_id, m, db)

        return Ligne(f"Ajouter au groupe « {g.nom} » : {', '.join(noms)}", faire)

    def prepare_remove(db: Session, compte, org_id: int, p: GroupMembers) -> Ligne:
        rbac.require_admin(compte, org_id)
        g = group(db, org_id, p.group_name)
        noms, membres = members(db, org_id, p.member_ids, p.course_ids)
        if not membres:
            raise Refus("personne à retirer")
        conversation_id = g.id

        def faire(db: Session) -> None:
            for m in membres:
                receiver.retirer_membre(conversation_id, m.membre_type, m.membre_id, db)

        return Ligne(f"Retirer du groupe « {g.nom} » : {', '.join(noms)}", faire)

    return [
        Action("create_group_chat", "Messagerie", "Crée un groupe de discussion dans la messagerie. "
               "Lis d'abord les numéros des personnes et des cours avec les outils de lecture.", NewGroup, prepare_create),
        Action("rename_group_chat", "Messagerie", "Renomme un groupe de discussion de la messagerie.", RenameGroup, prepare_rename),
        Action("delete_group_chat", "Messagerie", "Supprime un groupe de discussion de la messagerie, avec ses messages. "
               "Les groupes automatiques des cours ne se suppriment pas.", DeleteGroup, prepare_delete),
        Action("add_group_members", "Messagerie", "Ajoute des personnes ou des cours à un groupe de la messagerie.",
               GroupMembers, prepare_add),
        Action("remove_group_members", "Messagerie", "Retire des personnes ou des cours d'un groupe de la messagerie.",
               GroupMembers, prepare_remove),
    ]
