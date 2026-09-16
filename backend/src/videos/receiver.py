"""Routes REST des vidéos — reçoit les requêtes HTTP, délègue tout à
Videos (voir videos.py), ne fait aucun calcul métier ici.
"""

from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db

from .schemas import (
    FinaliserVideoEntree,
    ReordonnerVideos,
    TeleversementCreation,
    TeleversementSortie,
    UsageVideosEcole,
    VideoCreation,
    VideoModification,
    VideoSortie,
)
from .videos import DecalageInvalide, Videos


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
        # Upload par blocs (voir videos.py : Televersement) — mutualisé
        # entre l'écran Vidéo et le détail d'une chorégraphie (même
        # AddVideoModal.jsx côté frontend). 3 routes séparées, dans
        # l'ordre d'utilisation : ouvrir la session, y écrire des blocs,
        # créer la ligne Video (au clic "Ajouter", même si pas fini).
        self.app.post(
            "/cours/{cours_id}/videos/televersements",
            response_model=TeleversementSortie,
            status_code=201,
        )(self.ouvrir_televersement)
        self.app.put(
            "/videos/televersements/{upload_id}", response_model=TeleversementSortie
        )(self.ecrire_bloc)
        self.app.get(
            "/videos/televersements/{upload_id}", response_model=TeleversementSortie
        )(self.obtenir_televersement)
        self.app.delete("/videos/televersements/{upload_id}", status_code=204)(
            self.annuler_televersement
        )
        self.app.post(
            "/cours/{cours_id}/videos/depuis-televersement",
            response_model=VideoSortie,
            status_code=201,
        )(self.finaliser)
        self.app.get(
            "/choregraphies/{choregraphie_id}/videos", response_model=list[VideoSortie]
        )(self.lister_par_choregraphie)
        self.app.put(
            "/choregraphies/{choregraphie_id}/videos/ordre", status_code=204
        )(self.reordonner)

        self.app.get("/videos/{video_id}", response_model=VideoSortie)(self.obtenir)
        self.app.put("/videos/{video_id}", response_model=VideoSortie)(self.modifier)
        self.app.delete("/videos/{video_id}", status_code=204)(self.supprimer)

        # Panneau "Usage vidéo", Admin > École (voir §5.1.1).
        self.app.get("/ecoles/{ecole_id}/videos/usage", response_model=UsageVideosEcole)(
            self.usage
        )

    def lister_par_cours(self, cours_id: int, db: Session = Depends(get_db)):
        return self.client.list_par_cours(db, cours_id)

    def lister_par_choregraphie(self, choregraphie_id: int, db: Session = Depends(get_db)):
        return self.client.list_par_choregraphie(db, choregraphie_id)

    def creer(self, cours_id: int, donnees: VideoCreation, db: Session = Depends(get_db)):
        return self.client.create(db, cours_id, **donnees.model_dump())

    def ouvrir_televersement(
        self, cours_id: int, donnees: TeleversementCreation, db: Session = Depends(get_db)
    ):
        televersement = self.client.creer_televersement(
            db, cours_id, donnees.extension, donnees.octets_total
        )
        if televersement is None:
            raise HTTPException(status_code=404, detail="Cours introuvable")
        return televersement

    async def ecrire_bloc(self, upload_id: str, request: Request, db: Session = Depends(get_db)):
        donnees = await request.body()
        decalage = int(request.headers.get("X-Decalage", "-1"))
        try:
            televersement = self.client.ecrire_bloc(db, upload_id, decalage, donnees)
        except DecalageInvalide as exc:
            # 409 Conflict : le corps renvoie le VRAI décalage (voir
            # DecalageInvalide) pour que le client resynchronise son envoi
            # dessus, plutôt qu'une simple erreur sans info exploitable.
            raise HTTPException(
                status_code=409, detail={"octets_recus": exc.octets_recus}
            ) from exc
        if televersement is None:
            raise HTTPException(status_code=404, detail="Envoi introuvable")
        return televersement

    def obtenir_televersement(self, upload_id: str, db: Session = Depends(get_db)):
        televersement = self.client.obtenir_televersement(db, upload_id)
        if televersement is None:
            raise HTTPException(status_code=404, detail="Envoi introuvable")
        return televersement

    def annuler_televersement(self, upload_id: str, db: Session = Depends(get_db)):
        if not self.client.annuler_televersement(db, upload_id):
            raise HTTPException(status_code=404, detail="Envoi introuvable")

    def finaliser(
        self, cours_id: int, donnees: FinaliserVideoEntree, db: Session = Depends(get_db)
    ):
        video = self.client.finaliser(
            db,
            cours_id,
            donnees.upload_id,
            nom=donnees.nom,
            uploaded_by=donnees.uploaded_by,
            description=donnees.description or "",
            choregraphie_id=donnees.choregraphie_id,
        )
        if video is None:
            raise HTTPException(status_code=404, detail="Envoi introuvable")
        return video

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

    def usage(self, ecole_id: int, db: Session = Depends(get_db)):
        return self.client.usage_ecole(db, ecole_id)
