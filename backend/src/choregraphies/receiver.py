"""Routes REST des chorégraphies — reçoit les requêtes HTTP, délègue tout
à Choregraphies (voir choregraphies.py), ne fait aucun calcul métier ici.

Droits (spec §5.3, décision du 2026-10-03) :
- lire : toute personne de l'école, toutes les chorégraphies ;
- ajouter une vidéo à une chorégraphie : toute personne de l'école ;
- créer, modifier, supprimer une chorégraphie, modifier, réordonner ou
  supprimer une vidéo : un admin, ou un professeur du cours de la
  chorégraphie (« gérer ») ;
- supprimer SA vidéo : celui qui l'a ajoutée.
"""

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy.orm import Session
from videos.schemas import VideoModification, VideoSortie

from db import get_db

from .choregraphies import Choregraphies
from .models import Choregraphie
from .schemas import (
    ChoregraphieCreation,
    ChoregraphieModification,
    ChoregraphieSortie,
    ReordonnerVideos,
    VideoAjout,
)


class ChoregraphiesReceiver:
    def __init__(self, client: Choregraphies, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.get(
            "/ecoles/{ecole_id}/choregraphies", response_model=list[ChoregraphieSortie]
        )(self.lister)
        self.app.post(
            "/cours/{cours_id}/choregraphies",
            response_model=ChoregraphieSortie,
            status_code=201,
        )(self.creer)
        self.app.get("/choregraphies/{choregraphie_id}", response_model=ChoregraphieSortie)(
            self.obtenir
        )
        self.app.put("/choregraphies/{choregraphie_id}", response_model=ChoregraphieSortie)(
            self.modifier
        )
        self.app.delete("/choregraphies/{choregraphie_id}", status_code=204)(self.supprimer)

        self.app.post(
            "/choregraphies/{choregraphie_id}/videos", response_model=VideoSortie, status_code=201
        )(self.ajouter_video)
        # "ordre" AVANT "{video_id}" : sinon "ordre" serait pris pour un numéro.
        self.app.put("/choregraphies/{choregraphie_id}/videos/ordre", status_code=204)(
            self.reordonner_videos
        )
        self.app.put(
            "/choregraphies/{choregraphie_id}/videos/{video_id}", response_model=VideoSortie
        )(self.modifier_video)
        self.app.delete("/choregraphies/{choregraphie_id}/videos/{video_id}", status_code=204)(
            self.supprimer_video
        )

    # --- Aides ---

    def _sorties(self, db: Session, choregraphies: list[Choregraphie]) -> list[ChoregraphieSortie]:
        ids = [c.id for c in choregraphies]
        eleves = self.client.eleves_par_choregraphie(db, ids)
        videos = self.client.videos_par_choregraphie(db, ids)
        return [
            ChoregraphieSortie(
                id=c.id,
                cours_id=c.cours_id,
                nom=c.nom,
                horaire_repetition=c.horaire_repetition,
                costume=c.costume,
                eleve_ids=eleves[c.id],
                videos=[VideoSortie.model_validate(v) for v in videos[c.id]],
            )
            for c in choregraphies
        ]

    def _cours(self, db: Session, cours_id: int):
        cours = self.client.cours.get(db, cours_id)
        if cours is None:
            raise HTTPException(status_code=404, detail="Cours introuvable")
        return cours

    def _choregraphie(self, db: Session, choregraphie_id: int):
        """(chorégraphie, son cours), ou 404."""
        choregraphie = self.client.get(db, choregraphie_id)
        if choregraphie is None:
            raise HTTPException(status_code=404, detail="Chorégraphie introuvable")
        return choregraphie, self._cours(db, choregraphie.cours_id)

    def _exiger_gestion(self, db: Session, appelant: Compte | None, cours) -> None:
        # `appelant=None` : droits neutralisés (tests, voir tests/conftest.py).
        if appelant is not None and not self.client.peut_gerer(db, appelant, cours):
            raise HTTPException(
                status_code=403, detail="Réservé aux administrateurs et aux professeurs de ce cours"
            )

    def _video_de(self, db: Session, choregraphie_id: int, video_id: int):
        video = self.client.videos.get(db, video_id)
        if video is None or self.client.choregraphie_de_la_video(db, video_id) != choregraphie_id:
            raise HTTPException(status_code=404, detail="Vidéo introuvable")
        return video

    # --- Chorégraphies ---

    def lister(
        self,
        ecole_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        rbac.require_membre(appelant, ecole_id)
        return self._sorties(db, self.client.list_par_ecole(db, ecole_id))

    def obtenir(
        self,
        choregraphie_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        choregraphie, cours = self._choregraphie(db, choregraphie_id)
        rbac.require_membre(appelant, cours.ecole_id)
        return self._sorties(db, [choregraphie])[0]

    def creer(
        self,
        cours_id: int,
        donnees: ChoregraphieCreation,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        self._exiger_gestion(db, appelant, self._cours(db, cours_id))
        choregraphie = self.client.create(db, cours_id, **donnees.model_dump())
        return self._sorties(db, [choregraphie])[0]

    def modifier(
        self,
        choregraphie_id: int,
        donnees: ChoregraphieModification,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        _, cours = self._choregraphie(db, choregraphie_id)
        self._exiger_gestion(db, appelant, cours)
        champs = donnees.model_dump(exclude_unset=True)
        if champs.get("cours_id") is None:
            champs.pop("cours_id", None)
        elif champs["cours_id"] != cours.id:
            nouveau = self._cours(db, champs["cours_id"])
            if nouveau.ecole_id != cours.ecole_id:
                raise HTTPException(status_code=400, detail="Ce cours appartient à une autre école")
            self._exiger_gestion(db, appelant, nouveau)
        choregraphie = self.client.update(db, choregraphie_id, **champs)
        return self._sorties(db, [choregraphie])[0]

    def supprimer(
        self,
        choregraphie_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        _, cours = self._choregraphie(db, choregraphie_id)
        self._exiger_gestion(db, appelant, cours)
        self.client.delete(db, choregraphie_id)

    # --- Vidéos d'une chorégraphie ---

    def ajouter_video(
        self,
        choregraphie_id: int,
        donnees: VideoAjout,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        _, cours = self._choregraphie(db, choregraphie_id)
        rbac.require_membre(appelant, cours.ecole_id)
        televersement = self.client.videos.obtenir_televersement(db, donnees.upload_id)
        if televersement is None or televersement.ecole_id != cours.ecole_id:
            raise HTTPException(status_code=404, detail="Envoi introuvable")
        return self.client.ajouter_video(
            db,
            choregraphie_id,
            donnees.upload_id,
            nom=donnees.nom,
            uploaded_by=appelant.id,
            description=donnees.description or "",
        )

    def modifier_video(
        self,
        choregraphie_id: int,
        video_id: int,
        donnees: VideoModification,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        _, cours = self._choregraphie(db, choregraphie_id)
        self._video_de(db, choregraphie_id, video_id)
        self._exiger_gestion(db, appelant, cours)
        return self.client.videos.update(db, video_id, **donnees.model_dump(exclude_unset=True))

    def supprimer_video(
        self,
        choregraphie_id: int,
        video_id: int,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        _, cours = self._choregraphie(db, choregraphie_id)
        video = self._video_de(db, choregraphie_id, video_id)
        # Celui qui a ajouté la vidéo peut toujours la retirer.
        if appelant is None or video.uploaded_by != appelant.id:
            self._exiger_gestion(db, appelant, cours)
        self.client.videos.delete(db, video_id)

    def reordonner_videos(
        self,
        choregraphie_id: int,
        donnees: ReordonnerVideos,
        db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        _, cours = self._choregraphie(db, choregraphie_id)
        self._exiger_gestion(db, appelant, cours)
        self.client.reordonner_videos(db, choregraphie_id, donnees.ordre_video_ids)
