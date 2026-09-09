"""Logique métier des vidéos (voir spec/SPEC.md §6.8)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Video


class Videos:
    def list_par_cours(self, db: Session, cours_id: int) -> list[Video]:
        """Écran Vidéo (liste générale) : tri par date_publication, les
        plus récentes en premier — `ordre` est ignoré (voir §6.8)."""
        return list(
            db.scalars(
                select(Video)
                .where(Video.cours_id == cours_id)
                .order_by(Video.date_publication.desc())
            )
        )

    def list_par_choregraphie(self, db: Session, choregraphie_id: int) -> list[Video]:
        """Dans une chorégraphie : triées par `ordre` manuel (voir §6.8),
        les vidéos sans ordre défini passent en dernier."""
        videos = list(
            db.scalars(select(Video).where(Video.choregraphie_id == choregraphie_id))
        )
        return sorted(videos, key=lambda v: (v.ordre is None, v.ordre))

    def get(self, db: Session, video_id: int) -> Video | None:
        return db.get(Video, video_id)

    def create(
        self,
        db: Session,
        cours_id: int,
        nom: str,
        lien_fichier: str,
        uploaded_by: int,
        **champs,
    ) -> Video:
        video = Video(
            cours_id=cours_id, nom=nom, lien_fichier=lien_fichier, uploaded_by=uploaded_by,
            **champs,
        )
        db.add(video)
        db.commit()
        db.refresh(video)
        return video

    def update(self, db: Session, video_id: int, **champs) -> Video | None:
        video = self.get(db, video_id)
        if video is None:
            return None
        for cle, valeur in champs.items():
            if valeur is not None:
                setattr(video, cle, valeur)
        db.commit()
        db.refresh(video)
        return video

    def delete(self, db: Session, video_id: int) -> bool:
        video = self.get(db, video_id)
        if video is None:
            return False
        db.delete(video)
        db.commit()
        return True

    def reordonner(self, db: Session, choregraphie_id: int, ordre_video_ids: list[int]) -> None:
        """Réordonnancement manuel (glisser-déposer côté IHM, voir §6.8) :
        `ordre_video_ids` donne le nouvel ordre complet des vidéos de
        cette chorégraphie."""
        for position, video_id in enumerate(ordre_video_ids):
            video = self.get(db, video_id)
            if video is not None and video.choregraphie_id == choregraphie_id:
                video.ordre = position
        db.commit()
