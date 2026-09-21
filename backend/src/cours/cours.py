"""Logique métier des cours (voir spec/SPEC.md §5.1.4 et §6.5)."""

from __future__ import annotations

from comptes import Compte
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import Cours, CoursHoraireSupplementaire, cours_professeurs, eleves_cours


class CoursService:
    def list(self, db: Session, ecole_id: int) -> list[Cours]:
        # Jamais alphabétique (voir models.py:Cours.ordre) — `Cours.id`
        # en 2e critère juste pour un ordre stable entre 2 cours de même
        # `ordre` (ex. anciennes données, avant l'introduction du champ).
        return list(
            db.scalars(
                select(Cours)
                .where(Cours.ecole_id == ecole_id)
                .order_by(Cours.ordre, Cours.id)
            )
        )

    def get(self, db: Session, cours_id: int) -> Cours | None:
        return db.get(Cours, cours_id)

    def create(
        self,
        db: Session,
        ecole_id: int,
        nom: str,
        horaires_supplementaires: list[dict] | None = None,
        **champs,
    ) -> Cours:
        # Toujours auto-calculé (jamais fourni par CoursCreation, voir
        # schemas.py) : un nouveau cours va à la fin de la liste, pas
        # avant tous les autres.
        if champs.get("ordre") is None:
            max_ordre = db.scalar(select(func.max(Cours.ordre)).where(Cours.ecole_id == ecole_id))
            champs["ordre"] = (max_ordre or 0) + 1
        cours = Cours(ecole_id=ecole_id, nom=nom, **champs)
        if horaires_supplementaires:
            cours.horaires_supplementaires = [
                CoursHoraireSupplementaire(**h) for h in horaires_supplementaires
            ]
        db.add(cours)
        db.commit()
        db.refresh(cours)
        return cours

    def update(
        self,
        db: Session,
        cours_id: int,
        horaires_supplementaires: list[dict] | None = None,
        **champs,
    ) -> Cours | None:
        cours = self.get(db, cours_id)
        if cours is None:
            return None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable.
        for cle, valeur in champs.items():
            setattr(cours, cle, valeur)
        # None = pas touché (voir receiver.py) ; une liste (même vide)
        # remplace entièrement les créneaux en plus — SQLAlchemy
        # supprime les anciens (cascade="all, delete-orphan", voir
        # models.py) et insère les nouveaux.
        if horaires_supplementaires is not None:
            cours.horaires_supplementaires = [
                CoursHoraireSupplementaire(**h) for h in horaires_supplementaires
            ]
        db.commit()
        db.refresh(cours)
        return cours

    def delete(self, db: Session, cours_id: int) -> bool:
        cours = self.get(db, cours_id)
        if cours is None:
            return False
        # `cours_professeurs`/`eleves_cours` sont de simples tables de
        # jointure (voir models.py), sans `relationship()` ORM dessus :
        # `db.delete(cours)` seul ne les nettoie pas. Sans ce ménage, un
        # futur cours peut hériter en silence du prof et des élèves d'un
        # cours pourtant supprimé, dès que SQLite réutilise son id (pas
        # de mot-clé AUTOINCREMENT) — repéré lors de tests manuels par
        # id réutilisé après suppression.
        db.execute(cours_professeurs.delete().where(cours_professeurs.c.cours_id == cours_id))
        db.execute(eleves_cours.delete().where(eleves_cours.c.cours_id == cours_id))
        db.delete(cours)
        db.commit()
        return True

    # --- Relations (voir §6.5 : tables de jointure, rien stocké sur Cours) ---

    def ajouter_professeur(self, db: Session, cours_id: int, professeur_id: int) -> None:
        exists = db.execute(
            select(cours_professeurs).where(
                cours_professeurs.c.cours_id == cours_id,
                cours_professeurs.c.professeur_id == professeur_id,
            )
        ).first()
        if exists is None:
            db.execute(cours_professeurs.insert().values(cours_id=cours_id, professeur_id=professeur_id))
            db.commit()

    def retirer_professeur(self, db: Session, cours_id: int, professeur_id: int) -> None:
        db.execute(
            cours_professeurs.delete().where(
                cours_professeurs.c.cours_id == cours_id,
                cours_professeurs.c.professeur_id == professeur_id,
            )
        )
        db.commit()

    def professeurs_du_cours(self, db: Session, cours_id: int) -> list[Compte]:
        return list(
            db.scalars(
                select(Compte)
                .join(cours_professeurs, cours_professeurs.c.professeur_id == Compte.id)
                .where(cours_professeurs.c.cours_id == cours_id)
            )
        )

    def inscrire_eleve(self, db: Session, cours_id: int, eleve_id: int) -> None:
        exists = db.execute(
            select(eleves_cours).where(
                eleves_cours.c.cours_id == cours_id, eleves_cours.c.eleve_id == eleve_id
            )
        ).first()
        if exists is None:
            db.execute(eleves_cours.insert().values(cours_id=cours_id, eleve_id=eleve_id))
            db.commit()

    def desinscrire_eleve(self, db: Session, cours_id: int, eleve_id: int) -> None:
        db.execute(
            eleves_cours.delete().where(
                eleves_cours.c.cours_id == cours_id, eleves_cours.c.eleve_id == eleve_id
            )
        )
        db.commit()

    def eleves_du_cours(self, db: Session, cours_id: int) -> list[Compte]:
        return list(
            db.scalars(
                select(Compte)
                .join(eleves_cours, eleves_cours.c.eleve_id == Compte.id)
                .where(eleves_cours.c.cours_id == cours_id)
            )
        )

    def cours_du_professeur(self, db: Session, professeur_id: int) -> list[Cours]:
        """Utilisé pour le sélecteur de cours d'un prof (§4) et pour
        Présence (§5.2)."""
        return list(
            db.scalars(
                select(Cours)
                .join(cours_professeurs, cours_professeurs.c.cours_id == Cours.id)
                .where(cours_professeurs.c.professeur_id == professeur_id)
            )
        )

    def cours_par_eleve(self, db: Session, ecole_id: int) -> dict[int, list[int]]:
        """Toutes les inscriptions élève→cours d'une école, en UNE requête.

        Pendant groupé de `cours_de_leleve` : Admin > Élèves affiche une
        colonne "cours suivis" par ligne, soit un appel par élève — plus
        de cent requêtes HTTP à l'ouverture de l'écran sur la vraie école
        (voir receiver.py). Ici c'est un seul aller-retour, même ordre de
        cours (`Cours.ordre`, voir `list`) pour que l'affichage soit
        identique.

        Renvoie les inscriptions telles qu'elles sont en base : un compte
        inscrit à un cours mais sans profil d'élève (donc absent de
        GET /eleves) apparaît quand même ici. Les appelants itèrent sur
        la liste d'élèves, pas sur ce mapping, et ignorent donc ces
        entrées — même comportement qu'avec l'appel par élève.
        """
        lignes = db.execute(
            select(eleves_cours.c.eleve_id, eleves_cours.c.cours_id)
            .join(Cours, Cours.id == eleves_cours.c.cours_id)
            .where(Cours.ecole_id == ecole_id)
            .order_by(Cours.ordre, Cours.id)
        )
        resultat: dict[int, list[int]] = {}
        for eleve_id, cours_id in lignes:
            resultat.setdefault(eleve_id, []).append(cours_id)
        return resultat

    def professeurs_par_cours(self, db: Session, ecole_id: int) -> dict[int, list[int]]:
        """Pendant groupé de `professeurs_du_cours`, même motivation que
        `cours_par_eleve` : Admin > Cours en faisait un appel par cours."""
        lignes = db.execute(
            select(cours_professeurs.c.cours_id, cours_professeurs.c.professeur_id)
            .join(Cours, Cours.id == cours_professeurs.c.cours_id)
            .where(Cours.ecole_id == ecole_id)
            .order_by(Cours.ordre, Cours.id)
        )
        resultat: dict[int, list[int]] = {}
        for cours_id, professeur_id in lignes:
            resultat.setdefault(cours_id, []).append(professeur_id)
        return resultat

    def cours_de_leleve(self, db: Session, eleve_id: int) -> list[Cours]:
        return list(
            db.scalars(
                select(Cours)
                .join(eleves_cours, eleves_cours.c.cours_id == Cours.id)
                .where(eleves_cours.c.eleve_id == eleve_id)
            )
        )
