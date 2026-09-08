"""Logique métier de la présence (voir spec/SPEC.md §6.6). Dépend de
`cours` (heure de début théorique, pour déduire un retard) — jamais
l'inverse.
"""

from __future__ import annotations

import datetime as dt

from cours import CoursService
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PresenceEleve, PresenceProf, SeancePresence


def _minutes(heure: str | None) -> int | None:
    """Parse "HH:MM" en minutes depuis minuit. `None`/format invalide
    -> `None` (pas d'heure saisie, voir §6.6 : afficher "–")."""
    if not heure:
        return None
    try:
        h, m = heure.split(":")
        return int(h) * 60 + int(m)
    except ValueError:
        return None


def duree_minutes(heure_debut_reelle: str | None, heure_fin_reelle: str | None) -> int | None:
    debut, fin = _minutes(heure_debut_reelle), _minutes(heure_fin_reelle)
    if debut is None or fin is None:
        return None
    return fin - debut


def statut_prof(presence: PresenceProf, heure_debut_theorique: str | None) -> str:
    """PAS de statut stocké : déduit des heures (voir §6.6). "retard" se
    calcule en comparant à l'heure de début théorique du cours."""
    if presence.heure_debut_reelle is None:
        return "absent"
    if heure_debut_theorique and presence.heure_debut_reelle > heure_debut_theorique:
        return "retard"
    return "present"


class Presence:
    def __init__(self, cours: CoursService) -> None:
        self.cours = cours

    # --- Séances ---

    def creer_seance(self, db: Session, cours_id: int, date: dt.date) -> SeancePresence:
        seance = SeancePresence(cours_id=cours_id, date=date)
        db.add(seance)
        db.commit()
        db.refresh(seance)
        return seance

    def lister_seances(self, db: Session, cours_id: int) -> list[SeancePresence]:
        return list(
            db.scalars(
                select(SeancePresence)
                .where(SeancePresence.cours_id == cours_id)
                .order_by(SeancePresence.date)
            )
        )

    def get_seance(self, db: Session, seance_id: int) -> SeancePresence | None:
        return db.get(SeancePresence, seance_id)

    def supprimer_seance(self, db: Session, seance_id: int) -> bool:
        seance = self.get_seance(db, seance_id)
        if seance is None:
            return False
        for pe in self.presences_eleves(db, seance_id):
            db.delete(pe)
        for pp in self.presences_profs(db, seance_id):
            db.delete(pp)
        db.delete(seance)
        db.commit()
        return True

    # --- Présence élèves ---

    def presences_eleves(self, db: Session, seance_id: int) -> list[PresenceEleve]:
        return list(
            db.scalars(select(PresenceEleve).where(PresenceEleve.seance_id == seance_id))
        )

    def set_presence_eleve(
        self, db: Session, seance_id: int, eleve_id: int, statut: str
    ) -> PresenceEleve:
        """Upsert (voir §6.6 : "une ligne par élève présent", mise à jour
        si déjà saisie plutôt que doublon)."""
        presence = db.scalar(
            select(PresenceEleve).where(
                PresenceEleve.seance_id == seance_id, PresenceEleve.eleve_id == eleve_id
            )
        )
        if presence is None:
            presence = PresenceEleve(seance_id=seance_id, eleve_id=eleve_id, statut=statut)
            db.add(presence)
        else:
            presence.statut = statut
        db.commit()
        db.refresh(presence)
        return presence

    # --- Présence profs ---

    def presences_profs(self, db: Session, seance_id: int) -> list[PresenceProf]:
        return list(
            db.scalars(select(PresenceProf).where(PresenceProf.seance_id == seance_id))
        )

    def set_presence_prof(
        self,
        db: Session,
        seance_id: int,
        professeur_id: int,
        heure_debut_reelle: str | None = None,
        heure_fin_reelle: str | None = None,
        depassement_minutes: int | None = None,
    ) -> PresenceProf:
        """Upsert. Droit d'édition (§6.6 : un prof ne modifie que sa
        propre ligne) : vérification laissée au frontend/futur middleware
        d'autorisation, pas encore branché ici (voir backend-architecture)."""
        presence = db.scalar(
            select(PresenceProf).where(
                PresenceProf.seance_id == seance_id,
                PresenceProf.professeur_id == professeur_id,
            )
        )
        if presence is None:
            presence = PresenceProf(seance_id=seance_id, professeur_id=professeur_id)
            db.add(presence)
        if heure_debut_reelle is not None:
            presence.heure_debut_reelle = heure_debut_reelle
        if heure_fin_reelle is not None:
            presence.heure_fin_reelle = heure_fin_reelle
        if depassement_minutes is not None:
            presence.depassement_minutes = depassement_minutes
        db.commit()
        db.refresh(presence)
        return presence

    # --- Comptage d'heures (Admin > Professeurs / Profil > "Mes heures") ---

    def heures_professeur(
        self,
        db: Session,
        professeur_id: int,
        depuis: dt.date | None = None,
        jusqua: dt.date | None = None,
    ) -> dict:
        """Total des minutes travaillées (fin - début, dépassement inclus)
        et des minutes de dépassement, sur une période optionnelle."""
        requete = (
            select(PresenceProf, SeancePresence.date)
            .join(SeancePresence, SeancePresence.id == PresenceProf.seance_id)
            .where(PresenceProf.professeur_id == professeur_id)
        )
        if depuis is not None:
            requete = requete.where(SeancePresence.date >= depuis)
        if jusqua is not None:
            requete = requete.where(SeancePresence.date <= jusqua)

        minutes_total = 0
        minutes_depassement = 0
        for presence, _date in db.execute(requete).all():
            duree = duree_minutes(presence.heure_debut_reelle, presence.heure_fin_reelle)
            if duree is not None:
                minutes_total += duree
                minutes_depassement += presence.depassement_minutes
        return {"minutes_total": minutes_total, "minutes_depassement": minutes_depassement}
