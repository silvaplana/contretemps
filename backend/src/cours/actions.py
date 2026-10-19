"""Actions des cours ouvertes à l'assistant (spec/modules/assistant-ia.md §3) :
créer et supprimer un cours. Le modifier passe déjà par
« proposer_modifications » (assistant/modifications.py). Mêmes méthodes que
l'écran Admin > Cours.
"""

from __future__ import annotations

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import rbac
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from .receiver import CoursReceiver
from .schemas import CoursCreation

HEURE = r"^\d{2}:\d{2}$"


class NewCourse(BaseModel):
    name: str = Field(min_length=1, max_length=100, description="Nom du cours, ex. « Salsa débutants ».")
    day: str | None = Field(default=None, description="Jour en toutes lettres, ex. « Mardi ».")
    start: str | None = Field(default=None, pattern=HEURE, description="Heure de début HH:MM.")
    end: str | None = Field(default=None, pattern=HEURE, description="Heure de fin HH:MM.")
    room: str | None = Field(default=None, description="Salle.")
    description: str | None = Field(default=None, description="Descriptif.")


class DeleteCourse(BaseModel):
    course_id: int = Field(description="Numéro du cours.")


def actions(receiver: CoursReceiver) -> list[Action]:
    def prepare_create(db: Session, compte, org_id: int, p: NewCourse) -> Ligne:
        rbac.require_admin(compte, org_id)
        donnees = CoursCreation(
            nom=p.name.strip(), jour=p.day, heure_debut=p.start, heure_fin=p.end, salle=p.room, descriptif=p.description
        )
        quand = " ".join(x for x in (p.day, f"{p.start}-{p.end}" if p.start and p.end else None) if x)
        return Ligne(
            f"Créer le cours « {donnees.nom} »" + (f", {quand}" if quand else "") + (f", salle {p.room}" if p.room else ""),
            lambda db: receiver.creer(org_id, donnees, db),
        )

    def prepare_delete(db: Session, compte, org_id: int, p: DeleteCourse) -> Ligne:
        rbac.require_admin(compte, org_id)
        cours = receiver.client.get(db, p.course_id)
        if cours is None or cours.ecole_id != org_id:
            raise Refus("cours introuvable dans cette école")
        eleves = len(receiver.client.eleves_du_cours(db, cours.id))
        cours_id = cours.id
        return Ligne(
            f"Supprimer le cours « {cours.nom} » ({eleves} élève{'s' if eleves > 1 else ''} inscrit{'s' if eleves > 1 else ''})",
            lambda db: receiver.supprimer(cours_id, db),
        )

    return [
        Action("create_course", "Cours", "Crée un cours (nom, jour, horaires, salle). Discipline et niveau sont déduits du nom.",
               NewCourse, prepare_create),
        Action("delete_course", "Cours", "Supprime un cours ; ses élèves et professeurs n'y sont plus inscrits. "
               "Lis d'abord son numéro avec « lister_cours ».", DeleteCourse, prepare_delete),
    ]
