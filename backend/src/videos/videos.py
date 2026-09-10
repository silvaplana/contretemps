"""Logique métier des vidéos (voir spec/SPEC.md §6.8)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from choregraphies import Choregraphie
from cours import CoursService

from .models import Video
from .schemas import UsageVideosEcole, VideoUsage
from .stockage import DOSSIER_VIDEOS_LIVE


class Videos:
    def __init__(self, cours: CoursService) -> None:
        self.cours = cours

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
        # `champs` ne contient déjà que les champs explicitement fournis
        # (le receiver appelle model_dump(exclude_unset=True)) — un
        # `if valeur is not None` ici empêchait à tort de vider un champ
        # nullable (ex. détacher une vidéo d'une chorégraphie en envoyant
        # choregraphie_id=null, bug signalé : "on ne peut prendre que les
        # vidéos qui sont taguées pour cette chorégraphie").
        for cle, valeur in champs.items():
            setattr(video, cle, valeur)
        db.commit()
        db.refresh(video)
        return video

    def delete(self, db: Session, video_id: int) -> bool:
        video = self.get(db, video_id)
        if video is None:
            return False
        # Aucune table ne référence videos.id (pas de FK entrante) — rien
        # d'autre à nettoyer côté base. Le vrai risque d'orphelin, c'est
        # le FICHIER lui-même : sans ça, le fichier (et sa vignette)
        # restait sur le disque pour toujours, jamais compté nulle part
        # une fois la ligne supprimée (bug latent trouvé en construisant
        # le panneau "Usage vidéo", qui aurait fini par lister du vide).
        for chemin_relatif in (video.lien_fichier, video.poster):
            if not chemin_relatif:
                continue
            # `chemin_relatif` est en théorie toujours une valeur qu'on a
            # nous-même écrite (voir stockage.chemin_relatif), mais rien
            # n'empêche l'API de l'accepter arbitraire (VideoModification
            # accepte n'importe quelle chaîne) — un chemin ABSOLU dans
            # `/` ferait sortir `DOSSIER_VIDEOS_LIVE / chemin_relatif` du
            # dossier vidéos (Path : joindre avec un chemin absolu
            # REMPLACE la base). Vérifié avant de supprimer quoi que ce
            # soit, plutôt que de faire confiance à la valeur en base.
            cible = (DOSSIER_VIDEOS_LIVE / chemin_relatif).resolve()
            if cible.is_relative_to(DOSSIER_VIDEOS_LIVE.resolve()):
                cible.unlink(missing_ok=True)
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

    def usage_ecole(self, db: Session, ecole_id: int) -> UsageVideosEcole:
        """Panneau "Usage vidéo" (Admin > École) : Go utilisés, minutes de
        vidéo, top 10 par taille décroissante — toutes les vidéos AVEC un
        vrai fichier (lien_fichier non vide), tous cours de l'école
        confondus. La taille se lit sur le disque à la demande (pas
        stockée, toujours exacte même si un fichier est remplacé à la
        main) ; la durée vient de Video.duree_secondes (mesurée une fois,
        voir duree.py)."""
        cours_par_id = {c.id: c for c in self.cours.list(db, ecole_id)}
        if not cours_par_id:
            return UsageVideosEcole(total_octets=0, total_secondes=0, top_videos=[])

        videos = list(
            db.scalars(
                select(Video).where(
                    Video.cours_id.in_(cours_par_id.keys()), Video.lien_fichier != ""
                )
            )
        )

        choregraphie_ids = {v.choregraphie_id for v in videos if v.choregraphie_id is not None}
        noms_choregraphies = (
            {
                c.id: c.nom
                for c in db.scalars(select(Choregraphie).where(Choregraphie.id.in_(choregraphie_ids)))
            }
            if choregraphie_ids
            else {}
        )

        lignes: list[VideoUsage] = []
        total_octets = 0
        total_secondes = 0
        for video in videos:
            chemin = DOSSIER_VIDEOS_LIVE / video.lien_fichier
            try:
                taille = chemin.stat().st_size
            except OSError:
                continue  # fichier manquant sur le disque — ignoré, pas d'erreur 500
            total_octets += taille
            total_secondes += video.duree_secondes or 0
            lignes.append(
                VideoUsage(
                    id=video.id,
                    titre=video.nom,
                    cours=cours_par_id[video.cours_id].nom,
                    choregraphie=noms_choregraphies.get(video.choregraphie_id),
                    taille_octets=taille,
                    duree_secondes=video.duree_secondes,
                )
            )

        lignes.sort(key=lambda l: l.taille_octets, reverse=True)
        return UsageVideosEcole(
            total_octets=total_octets, total_secondes=total_secondes, top_videos=lignes[:10]
        )
