"""Action des chorégraphies ouverte à l'assistant (spec/modules/assistant-ia.md
§3) : supprimer une chorégraphie. La créer et la modifier passent déjà par
« proposer_modifications ».
"""

from __future__ import annotations

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import rbac
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .choregraphies import Choregraphies


class DeleteChoreography(BaseModel):
    choreography_id: int = Field(description="Numéro de la chorégraphie.")


def actions(client: Choregraphies) -> list[Action]:
    def prepare_delete(db: Session, compte, org_id: int, p: DeleteChoreography) -> Ligne:
        rbac.require_admin(compte, org_id)
        choregraphie = client.get(db, p.choreography_id)
        cours = client.cours.get(db, choregraphie.cours_id) if choregraphie else None
        if cours is None or cours.ecole_id != org_id:
            raise Refus("chorégraphie introuvable dans cette école")
        videos = len(client.videos_par_choregraphie(db, [choregraphie.id])[choregraphie.id])
        choregraphie_id = choregraphie.id
        return Ligne(
            f"Supprimer la chorégraphie « {choregraphie.nom} »" + (f" et ses {videos} vidéo(s)" if videos else ""),
            lambda db: client.delete(db, choregraphie_id),
        )

    return [Action("delete_choreography", "Chorégraphies", "Supprime une chorégraphie, avec ses vidéos.",
                   DeleteChoreography, prepare_delete)]
