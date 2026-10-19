"""Action des élèves ouverte à l'assistant (spec/modules/assistant-ia.md §3) :
supprimer un élève, comme Admin > Élèves. Le créer et le modifier passent
déjà par « proposer_modifications ».
"""

from __future__ import annotations

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import rbac
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .eleves import Eleves


class DeleteStudent(BaseModel):
    student_id: int = Field(description="Numéro de l'élève.")


def actions(client: Eleves) -> list[Action]:
    def prepare_delete(db: Session, compte, org_id: int, p: DeleteStudent) -> Ligne:
        rbac.require_admin(compte, org_id)
        eleve = client.get_compte(db, p.student_id)
        if eleve is None or eleve.ecole_id != org_id:
            raise Refus("élève introuvable dans cette école")
        eleve_id = eleve.id
        return Ligne(
            f"Supprimer l'élève {eleve.prenom} {eleve.nom} (ses présences restent dans l'historique)",
            lambda db: client.delete(db, eleve_id),
        )

    return [Action("delete_student", "Élèves", "Supprime un élève (Admin > Élèves).", DeleteStudent, prepare_delete)]
