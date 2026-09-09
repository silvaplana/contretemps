"""Routes REST des vidéos — reçoit les requêtes HTTP, délègue tout à
Videos (voir videos.py), ne fait aucun calcul métier ici.
"""

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session

from db import get_db

from .schemas import ReordonnerVideos, VideoCreation, VideoModification, VideoSortie
from .videos import Videos


class VideosReceiver:
    def __init__(self, client: Videos, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get("/cours/{cours_id}/videos", response_model=list[VideoSortie])(
            self.lister_par_cours
        )
        self.app.post(
            "/cours/{cours_id}/videos", response_model=VideoSortie, status_code=201
        )(self.creer)
        self.app.get(
            "/choregraphies/{choregraphie_id}/videos", response_model=list[VideoSortie]
        )(self.lister_par_choregraphie)
        self.app.put(
            "/choregraphies/{choregraphie_id}/videos/ordre", status_code=204
        )(self.reordonner)

        self.app.get("/videos/{video_id}", response_model=VideoSortie)(self.obtenir)
        self.app.put("/videos/{video_id}", response_model=VideoSortie)(self.modifier)
        self.app.delete("/videos/{video_id}", status_code=204)(self.supprimer)

    def lister_par_cours(self, cours_id: int, db: Session = Depends(get_db)):
        return self.client.list_par_cours(db, cours_id)

    def lister_par_choregraphie(self, choregraphie_id: int, db: Session = Depends(get_db)):
        return self.client.list_par_choregraphie(db, choregraphie_id)

    def creer(self, cours_id: int, donnees: VideoCreation, db: Session = Depends(get_db)):
        return self.client.create(db, cours_id, **donnees.model_dump())

    def obtenir(self, video_id: int, db: Session = Depends(get_db)):
        video = self.client.get(db, video_id)
        if video is None:
            raise HTTPException(status_code=404, detail="Vidéo introuvable")
        return video

    def modifier(self, video_id: int, donnees: VideoModification, db: Session = Depends(get_db)):
        video = self.client.update(db, video_id, **donnees.model_dump(exclude_unset=True))
        if video is None:
            raise HTTPException(status_code=404, detail="Vidéo introuvable")
        return video

    def supprimer(self, video_id: int, db: Session = Depends(get_db)):
        if not self.client.delete(db, video_id):
            raise HTTPException(status_code=404, detail="Vidéo introuvable")

    def reordonner(
        self, choregraphie_id: int, donnees: ReordonnerVideos, db: Session = Depends(get_db)
    ):
        self.client.reordonner(db, choregraphie_id, donnees.ordre_video_ids)
