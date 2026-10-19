"""Actions de la messagerie ouvertes à l'assistant (spec/modules/assistant-ia.md §3) :
créer, renommer, supprimer un groupe, changer ses membres. Elles passent par les mêmes méthodes
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
    group_name: str = Field(description="Nom du groupe (un groupe de cours porte le nom du cours).")
    add_member_ids: list[int] = Field(default=[], description="Numéros des personnes à ajouter.")
    add_course_ids: list[int] = Field(default=[], description="Numéros des cours à ajouter (tous leurs élèves et professeurs).")
    remove_member_ids: list[int] = Field(default=[], description="Numéros des personnes à retirer.")
    remove_course_ids: list[int] = Field(default=[], description="Numéros des cours à retirer.")


def actions(receiver: MessagerieReceiver) -> list[Action]:
    conversations = receiver.conversations

    def group(db: Session, org_id: int, name: str, with_courses: bool = False):
        """Un groupe par son nom : créé à la main, ou aussi celui d'un cours
        (nommé par son cours) avec `with_courses`."""
        groupes = []
        for c in conversations.lister_ecole(db, org_id):
            nom = c.nom if not with_courses else conversations.nom_groupe_affiche(db, c)
            if c.type == "groupe" and nom:
                groupes.append((nom, c))
        trouve = [c for nom, c in groupes if nom.casefold() == name.strip().casefold()]
        if not trouve:
            noms = ", ".join(f"« {nom} »" for nom, _ in groupes) or "aucun"
            raise Refus(f"pas de groupe « {name} ». Groupes existants : {noms}")
        return trouve[0]

    def prepare_create(db: Session, compte, org_id: int, p: NewGroup) -> Ligne:
        rbac.require_admin(compte, org_id)
        personnes = [db.get(Compte, i) for i in dict.fromkeys(p.member_ids)]
        cours = [db.get(Cours, i) for i in dict.fromkeys(p.course_ids)]
        if any(not dans_l_ecole(x, org_id) for x in [*personnes, *cours]):
            raise Refus("une personne ou un cours est introuvable dans cette école")
        noms = [f"{x.prenom} {x.nom}".strip() for x in personnes] + [f"le cours {c.nom}" for c in cours]
        membres = [MembreEntree(membre_type="compte", membre_id=x.id) for x in personnes] + [
            MembreEntree(membre_type="cours", membre_id=c.id) for c in cours
        ]
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

    def prepare_members(db: Session, compte, org_id: int, p: GroupMembers) -> Ligne:
        rbac.require_admin(compte, org_id)
        g = group(db, org_id, p.group_name, with_courses=True)
        nom_groupe = conversations.nom_groupe_affiche(db, g)

        def lire(modele, ids):
            trouves = [db.get(modele, i) for i in dict.fromkeys(ids)]
            if any(not dans_l_ecole(x, org_id) for x in trouves):
                raise Refus("une personne ou un cours est introuvable dans cette école")
            return trouves

        ajouts = [("compte", x) for x in lire(Compte, p.add_member_ids)] + [("cours", c) for c in lire(Cours, p.add_course_ids)]
        retraits = [("compte", x) for x in lire(Compte, p.remove_member_ids)] + [
            ("cours", c) for c in lire(Cours, p.remove_course_ids)
        ]
        blocs = {(b.membre_type, b.membre_id) for b in conversations.blocs(db, g.id)}
        pas_dedans = [x for t, x in retraits if (t, x.id) not in blocs]
        if pas_dedans:
            raise Refus(f"{libelle(pas_dedans[0])} n'est pas membre direct de ce groupe")
        if not ajouts and not retraits:
            raise Refus("rien à changer")

        morceaux = []
        if ajouts:
            morceaux.append("ajouter " + ", ".join(libelle(x) for _, x in ajouts))
        if retraits:
            morceaux.append("retirer " + ", ".join(libelle(x) for _, x in retraits))
        conversation_id = g.id

        def faire(db):
            for t, x in ajouts:
                receiver.ajouter_membre(conversation_id, MembreEntree(membre_type=t, membre_id=x.id), db)
            for t, x in retraits:
                receiver.retirer_membre(conversation_id, t, x.id, db)

        return Ligne(f"Groupe « {nom_groupe} » : {' ; '.join(morceaux)}", faire)

    return [
        Action("create_group_chat", "Messagerie", "Crée un groupe de discussion dans la messagerie. "
               "Lis d'abord les numéros des personnes et des cours avec les outils de lecture.", NewGroup, prepare_create),
        Action("rename_group_chat", "Messagerie", "Renomme un groupe de discussion de la messagerie.", RenameGroup, prepare_rename),
        Action("delete_group_chat", "Messagerie", "Supprime un groupe de discussion de la messagerie, avec ses messages. "
               "Les groupes automatiques des cours ne se suppriment pas.", DeleteGroup, prepare_delete),
        Action("update_group_chat_members", "Messagerie", "Ajoute ou retire des membres d'un groupe de discussion "
               "de la messagerie (aussi le groupe d'un cours). Lis d'abord les numéros des personnes et des cours "
               "avec les outils de lecture.", GroupMembers, prepare_members),
    ]


def libelle(x) -> str:
    """Une personne (Compte) ou un cours, tel qu'écrit sur la carte."""
    if isinstance(x, Cours):
        return f"le cours {x.nom}"
    return f"{x.prenom} {x.nom}".strip()


def dans_l_ecole(x, org_id: int) -> bool:
    """Une personne ou un cours de l'école ; le Super User, hors école, s'ajoute
    dans toute école (spec/core.md §6.1)."""
    return x is not None and (x.ecole_id == org_id or (isinstance(x, Compte) and roles.is_superuser(x)))
