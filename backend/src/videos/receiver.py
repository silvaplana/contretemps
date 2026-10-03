"""Routes REST des vidéos — reçoit les requêtes HTTP, délègue tout à
Videos (voir videos.py), ne fait aucun calcul métier ici.

Module générique (voir models.py) : ces routes ne couvrent que ce qui ne
dépend d'aucun métier — envoyer un fichier, lire une vidéo, l'administrer.
Créer une vidéo à partir d'un envoi, et décider qui peut la modifier ou la
supprimer en dehors des admins, revient au métier qui la rattache à ses
objets (pour Contretemps : choregraphies/receiver.py).
"""

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException, Request
from sqlalchemy.orm import Session

from db import get_db

from .schemas import (
    TeleversementCreation,
    TeleversementSortie,
    UsageVideosEcole,
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
        # Upload par blocs (voir videos.py : Televersement). Dans l'ordre
        # d'utilisation : ouvrir la session, y écrire des blocs. La vidéo
        # elle-même est créée par le métier (clic "Ajouter").
        self.app.post(
            "/ecoles/{ecole_id}/videos/televersements",
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

        self.app.get("/videos/{video_id}", response_model=VideoSortie)(self.obtenir)
        self.app.put("/videos/{video_id}", response_model=VideoSortie)(self.modifier)
        self.app.delete("/videos/{video_id}", status_code=204)(self.supprimer)

        # Panneau "Usage vidéo", Admin > École (voir §5.1.1).
        self.app.get(
            "/ecoles/{ecole_id}/videos/usage",
            response_model=UsageVideosEcole,
            dependencies=[Depends(self._admin_ecole)],
        )(self.usage)

    def ouvrir_televersement(
        self,
        ecole_id: int,
        donnees: TeleversementCreation,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        rbac.require_membre(appelant, ecole_id)
        return self.client.creer_televersement(db, ecole_id, donnees.extension, donnees.octets_total)

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

    def _video(self, db: Session, video_id: int):
        video = self.client.get(db, video_id)
        if video is None:
            raise HTTPException(status_code=404, detail="Vidéo introuvable")
        return video

    def obtenir(
        self,
        video_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        video = self._video(db, video_id)
        rbac.require_membre(appelant, video.ecole_id)
        return video

    # Modifier ou supprimer une vidéo par son seul numéro : réservé aux
    # admins de son école (panneau "Usage vidéo"). Les autres passent par
    # le métier, qui applique ses propres règles.

    def modifier(
        self,
        video_id: int,
        donnees: VideoModification,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        rbac.require_admin(appelant, self._video(db, video_id).ecole_id)
        return self.client.update(db, video_id, **donnees.model_dump(exclude_unset=True))

    def supprimer(
        self,
        video_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        rbac.require_admin(appelant, self._video(db, video_id).ecole_id)
        self.client.delete(db, video_id)

    # --- RBAC (spec §2.4) : l'école que touche chaque route protégée, la
    # règle elle-même étant dans comptes/rbac.py. ---

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def usage(self, ecole_id: int, db: Session = Depends(get_db)):
        return self.client.usage_ecole(db, ecole_id)
