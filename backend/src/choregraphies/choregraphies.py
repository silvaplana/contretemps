"""Logique métier des chorégraphies (voir spec/SPEC.md §5.3 et §6.7).

Une chorégraphie est associée à un cours dès sa création ; ses élèves sont
choisis dans toute l'école ; ses vidéos sont celles du module générique
`videos`, qu'elle référence par `choregraphies_videos` (ce module-là ne
connaît pas les chorégraphies).
"""

from __future__ import annotations

from comptes import Compte, roles
from cours import Cours, CoursService
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from saisons.portee import verifier_modifiable
from videos import Video, Videos

from .models import Choregraphie, choregraphies_eleves, choregraphies_videos


class Choregraphies:
    def __init__(self, cours: CoursService, videos: Videos) -> None:
        self.cours = cours
        self.videos = videos
        # Une vidéo supprimée (ou dont l'envoi est annulé) quitte sa chorégraphie.
        videos.quand_supprimee(self._detacher_video)

    # --- Lecture ---

    def list_par_ecole(self, db: Session, ecole_id: int) -> list[Choregraphie]:
        """Toutes les chorégraphies de l'école, dans la saison affichée
        (les cours sont filtrés par saison, voir saisons/portee.py)."""
        return list(
            db.scalars(
                select(Choregraphie)
                .join(Cours, Cours.id == Choregraphie.cours_id)
                .where(Cours.ecole_id == ecole_id)
                .order_by(Cours.ordre, Cours.id, Choregraphie.id)
            )
        )

    def list(self, db: Session, cours_id: int) -> list[Choregraphie]:
        return list(
            db.scalars(select(Choregraphie).where(Choregraphie.cours_id == cours_id))
        )

    def get(self, db: Session, choregraphie_id: int) -> Choregraphie | None:
        return db.get(Choregraphie, choregraphie_id)

    def eleves_par_choregraphie(self, db: Session, ids: list[int]) -> dict[int, list[int]]:
        resultat: dict[int, list[int]] = {i: [] for i in ids}
        if ids:
            for choregraphie_id, eleve_id in db.execute(
                select(choregraphies_eleves.c.choregraphie_id, choregraphies_eleves.c.eleve_id).where(
                    choregraphies_eleves.c.choregraphie_id.in_(ids)
                )
            ):
                resultat[choregraphie_id].append(eleve_id)
        return resultat

    def videos_par_choregraphie(self, db: Session, ids: list[int]) -> dict[int, list[Video]]:
        """Les vidéos de chaque chorégraphie, dans l'ordre choisi."""
        resultat: dict[int, list[Video]] = {i: [] for i in ids}
        if not ids:
            return resultat
        liens = db.execute(
            select(choregraphies_videos.c.choregraphie_id, choregraphies_videos.c.video_id)
            .where(choregraphies_videos.c.choregraphie_id.in_(ids))
            .order_by(choregraphies_videos.c.ordre, choregraphies_videos.c.video_id)
        ).all()
        videos = self.videos.par_ids(db, [video_id for _, video_id in liens])
        for choregraphie_id, video_id in liens:
            if video_id in videos:
                resultat[choregraphie_id].append(videos[video_id])
        return resultat

    def choregraphie_de_la_video(self, db: Session, video_id: int) -> int | None:
        return db.scalar(
            select(choregraphies_videos.c.choregraphie_id).where(
                choregraphies_videos.c.video_id == video_id
            )
        )

    # --- Qui peut gérer une chorégraphie (spec §5.3) ---

    def peut_gerer(self, db: Session, appelant: Compte, cours: Cours) -> bool:
        """Un admin de l'école, ou un professeur DU cours."""
        if roles.is_superuser(appelant):
            return True
        if appelant.ecole_id != cours.ecole_id:
            return False
        if roles.is_admin(appelant):
            return True
        return any(p.id == appelant.id for p in self.cours.professeurs_du_cours(db, cours.id))

    # --- Écriture ---

    def create(
        self, db: Session, cours_id: int, nom: str, eleve_ids: list[int] | None = None, **champs
    ) -> Choregraphie:
        choregraphie = Choregraphie(cours_id=cours_id, nom=nom, **champs)
        db.add(choregraphie)
        db.commit()
        db.refresh(choregraphie)
        if eleve_ids:
            self.definir_eleves(db, choregraphie.id, eleve_ids)
        return choregraphie

    def update(
        self, db: Session, choregraphie_id: int, eleve_ids: list[int] | None = None, **champs
    ) -> Choregraphie | None:
        choregraphie = self.get(db, choregraphie_id)
        if choregraphie is None:
            return None
        # `champs` ne contient déjà que les champs explicitement fournis
        # (exclude_unset=True côté receiver) — un `if valeur is not None`
        # ici empêchait à tort de vider un champ nullable.
        for cle, valeur in champs.items():
            setattr(choregraphie, cle, valeur)
        db.commit()
        db.refresh(choregraphie)
        if eleve_ids is not None:
            self.definir_eleves(db, choregraphie_id, eleve_ids)
        return choregraphie

    def delete(self, db: Session, choregraphie_id: int) -> bool:
        """Supprime la chorégraphie, ses liens, et ses vidéos (fichiers
        compris) : une vidéo n'existe que dans sa chorégraphie."""
        choregraphie = self.get(db, choregraphie_id)
        if choregraphie is None:
            return False
        verifier_modifiable(db, "choregraphies", choregraphie_id)
        for video in self.videos_par_choregraphie(db, [choregraphie_id])[choregraphie_id]:
            self.videos.delete(db, video.id)
        db.execute(
            choregraphies_eleves.delete().where(
                choregraphies_eleves.c.choregraphie_id == choregraphie_id
            )
        )
        db.delete(choregraphie)
        db.commit()
        return True

    # --- Élèves participants ---

    def definir_eleves(self, db: Session, choregraphie_id: int, eleve_ids: list[int]) -> None:
        """Remplace la liste des participants. Ne retient que des élèves de
        l'école du cours (n'importe quel cours, voir models.py)."""
        choregraphie = self.get(db, choregraphie_id)
        if choregraphie is None:
            return
        verifier_modifiable(db, "choregraphies", choregraphie_id)
        ecole_id = self.cours.get(db, choregraphie.cours_id).ecole_id
        demandes = list(dict.fromkeys(eleve_ids))
        retenus = [
            compte.id
            for compte in db.scalars(select(Compte).where(Compte.id.in_(demandes)))
            if compte.ecole_id == ecole_id and roles.is_eleve(compte)
        ] if demandes else []
        db.execute(
            choregraphies_eleves.delete().where(
                choregraphies_eleves.c.choregraphie_id == choregraphie_id
            )
        )
        for eleve_id in retenus:
            db.execute(
                choregraphies_eleves.insert().values(
                    choregraphie_id=choregraphie_id, eleve_id=eleve_id
                )
            )
        db.commit()

    # --- Vidéos ---

    def ajouter_video(
        self,
        db: Session,
        choregraphie_id: int,
        upload_id: str,
        nom: str,
        uploaded_by: int,
        description: str = "",
    ) -> Video | None:
        """Clic « Ajouter » : l'envoi devient une vidéo (voir
        videos.py:finaliser), rangée à la fin de la chorégraphie. `None`
        si l'envoi est inconnu."""
        verifier_modifiable(db, "choregraphies", choregraphie_id)
        video = self.videos.finaliser(
            db, upload_id, nom=nom, uploaded_by=uploaded_by, description=description
        )
        if video is None:
            return None
        self.attacher_video(db, choregraphie_id, video.id)
        return video

    def attacher_video(self, db: Session, choregraphie_id: int, video_id: int) -> None:
        if self.choregraphie_de_la_video(db, video_id) is not None:
            return  # double clic : déjà rangée (voir videos.py:finaliser)
        dernier = db.scalar(
            select(func.max(choregraphies_videos.c.ordre)).where(
                choregraphies_videos.c.choregraphie_id == choregraphie_id
            )
        )
        db.execute(
            choregraphies_videos.insert().values(
                choregraphie_id=choregraphie_id,
                video_id=video_id,
                ordre=0 if dernier is None else dernier + 1,
            )
        )
        db.commit()

    def reordonner_videos(self, db: Session, choregraphie_id: int, ordre_video_ids: list[int]) -> None:
        """`ordre_video_ids` : le nouvel ordre complet des vidéos."""
        verifier_modifiable(db, "choregraphies", choregraphie_id)
        for position, video_id in enumerate(ordre_video_ids):
            db.execute(
                choregraphies_videos.update()
                .where(
                    choregraphies_videos.c.choregraphie_id == choregraphie_id,
                    choregraphies_videos.c.video_id == video_id,
                )
                .values(ordre=position)
            )
        db.commit()

    def _detacher_video(self, db: Session, video_id: int) -> None:
        db.execute(choregraphies_videos.delete().where(choregraphies_videos.c.video_id == video_id))
