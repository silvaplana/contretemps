"""Actions des professeurs ouvertes à l'assistant (spec/modules/assistant-ia.md
§3) : créer, modifier, supprimer un professeur, comme Admin > Profs.
L'affecter à un cours passe déjà par « proposer_modifications ».
"""

from __future__ import annotations

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import rbac
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .profs import Profs


class NewTeacher(BaseModel):
    last_name: str = Field(min_length=1, max_length=100, description="Nom.")
    first_name: str = Field(min_length=1, max_length=100, description="Prénom.")
    email: str | None = Field(default=None, description="Email.")
    phone: str | None = Field(default=None, description="Téléphone.")


class UpdateTeacher(BaseModel):
    teacher_id: int = Field(description="Numéro du professeur.")
    last_name: str | None = Field(default=None, min_length=1, max_length=100, description="Nouveau nom, ou null.")
    first_name: str | None = Field(default=None, min_length=1, max_length=100, description="Nouveau prénom, ou null.")
    email: str | None = Field(default=None, description="Nouvel email, ou null.")
    phone: str | None = Field(default=None, description="Nouveau téléphone, ou null.")


class DeleteTeacher(BaseModel):
    teacher_id: int = Field(description="Numéro du professeur.")


CHAMPS = {"last_name": ("nom", "nom"), "first_name": ("prenom", "prénom"), "email": ("email", "email"), "phone": ("telephone", "téléphone")}


def actions(client: Profs) -> list[Action]:
    def teacher(db: Session, org_id: int, teacher_id: int):
        prof = client.get(db, teacher_id)
        if prof is None or prof.ecole_id != org_id:
            raise Refus("professeur introuvable dans cette école")
        return prof

    def prepare_create(db: Session, compte, org_id: int, p: NewTeacher) -> Ligne:
        rbac.require_admin(compte, org_id)
        nom = f"{p.first_name} {p.last_name}".strip()
        return Ligne(
            f"Créer le professeur {nom}" + (f" ({p.email})" if p.email else ""),
            lambda db: client.create(db, org_id, nom=p.last_name.strip(), prenom=p.first_name.strip(), email=p.email, telephone=p.phone),
        )

    def prepare_update(db: Session, compte, org_id: int, p: UpdateTeacher) -> Ligne:
        rbac.require_admin(compte, org_id)
        prof = teacher(db, org_id, p.teacher_id)
        donnees = p.model_dump(exclude_none=True, exclude={"teacher_id"})
        if not donnees:
            raise Refus("rien à changer")
        champs = {CHAMPS[k][0]: v for k, v in donnees.items()}
        prof_id = prof.id
        return Ligne(
            f"Professeur {prof.prenom} {prof.nom} : " + ", ".join(f"{CHAMPS[k][1]} : {v}" for k, v in donnees.items()),
            lambda db: client.update(db, prof_id, **champs),
        )

    def prepare_delete(db: Session, compte, org_id: int, p: DeleteTeacher) -> Ligne:
        rbac.require_admin(compte, org_id)
        prof = teacher(db, org_id, p.teacher_id)
        prof_id = prof.id
        return Ligne(f"Supprimer le professeur {prof.prenom} {prof.nom} (retiré de ses cours)", lambda db: client.delete(db, prof_id))

    return [
        Action("create_teacher", "Professeurs", "Crée un professeur (Admin > Profs).", NewTeacher, prepare_create),
        Action("update_teacher", "Professeurs", "Modifie le nom, le prénom, l'email ou le téléphone d'un professeur. "
               "Ne donne que les champs qui changent.", UpdateTeacher, prepare_update),
        Action("delete_teacher", "Professeurs", "Supprime un professeur ; il est retiré de ses cours.", DeleteTeacher, prepare_delete),
    ]
