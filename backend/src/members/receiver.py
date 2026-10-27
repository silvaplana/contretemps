"""Routes des champs des membres (spec/core.md §4.3) : la fiche, réglée par
les admins de l'école (Admin > Élèves > ⋯ > Champs), et les réponses d'une
fiche, saisies par un admin dans la fiche de l'élève."""

from __future__ import annotations

import os
from pathlib import Path

from comptes import Compte, rbac
from fastapi import Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.responses import FileResponse
from saisons import saison_courante_id
from saisons.portee import saison_demandee
from sqlalchemy.orm import Session
from storage import FileTooLarge, LocalStorage, guess_mime
from videos.stockage import DOSSIER_VIDEOS_LIVE

from db import get_db

from . import columns as cols
from . import fields as f
from . import values
from .models import MemberField
from .schemas import AnswerIn, AnswerOut, Choices, ColumnIn, ColumnOut, FieldIn, FieldOut, FieldPatch

DOSSIER_MEMBRES = Path(os.environ.get("MEMBRES_DIR", DOSSIER_VIDEOS_LIVE.parent / "membres"))
TAILLE_MAX_FICHIER = 25 * 1024 * 1024


def _saison(db: Session, ecole_id: int) -> int | None:
    return saison_demandee() or saison_courante_id(db, ecole_id)


def _erreur(erreur: Exception) -> HTTPException:
    if isinstance(erreur, LookupError):
        return HTTPException(status_code=404, detail=str(erreur))
    return HTTPException(status_code=422, detail=str(erreur))


class MembersReceiver:
    def __init__(self, app: FastAPI, storage: LocalStorage | None = None) -> None:
        self.storage = storage or LocalStorage(DOSSIER_MEMBRES, TAILLE_MAX_FICHIER)
        admin = [Depends(self._admin_ecole)]
        app.get("/ecoles/{ecole_id}/champs", response_model=list[FieldOut], dependencies=admin)(self.lister)
        app.get("/ecoles/{ecole_id}/champs/groupes", response_model=Choices, dependencies=admin)(self.groupes)
        app.post("/ecoles/{ecole_id}/champs", response_model=FieldOut, status_code=201, dependencies=admin)(
            self.creer
        )
        app.get("/ecoles/{ecole_id}/champs/reponses", dependencies=admin)(self.toutes_reponses)
        app.get("/ecoles/{ecole_id}/colonnes", response_model=list[ColumnOut], dependencies=admin)(self.colonnes)
        app.put("/ecoles/{ecole_id}/colonnes", response_model=list[ColumnOut], dependencies=admin)(
            self.changer_colonnes
        )
        app.patch("/champs/{field_id}", response_model=FieldOut)(self.modifier)
        app.delete("/champs/{field_id}", status_code=204)(self.retirer)
        app.post("/champs/{field_id}/remettre", response_model=FieldOut)(self.remettre)
        app.get("/membres/{compte_id}/champs", response_model=list[AnswerOut])(self.reponses)
        app.put("/membres/{compte_id}/champs/{field_id}", status_code=204)(self.repondre)
        app.post("/membres/{compte_id}/champs/{field_id}/fichier")(self.envoyer_fichier)
        app.get("/membres/{compte_id}/champs/{field_id}/fichier")(self.fichier)

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    @staticmethod
    def _champ(db: Session, field_id: int, appelant: Compte | None) -> MemberField:
        field = db.get(MemberField, field_id)
        rbac.require_admin(appelant, field.org_id if field else None)
        if field is None:
            raise HTTPException(status_code=404, detail="Champ introuvable")
        return field

    @staticmethod
    def _fiche(db: Session, compte_id: int, appelant: Compte | None) -> Compte:
        fiche = db.get(Compte, compte_id)
        rbac.require_admin(appelant, fiche.ecole_id if fiche else None)
        if fiche is None:
            raise HTTPException(status_code=404, detail="Fiche introuvable")
        return fiche

    # --- La fiche ---

    def lister(self, ecole_id: int, db: Session = Depends(get_db)):
        return f.fields(db, ecole_id, _saison(db, ecole_id))

    def groupes(self, ecole_id: int, db: Session = Depends(get_db)):
        saison = _saison(db, ecole_id)
        return {
            "parents": [
                {"id": g.id, "name": g.name, "children": [{"id": c.id, "name": c.name} for c in f.children(db, g.id)]}
                for g in f.parent_groups(db, ecole_id, saison)
            ],
            "audiences": [{"id": g.id, "name": g.name} for g in f.audience_groups(db, ecole_id, saison)],
        }

    def creer(self, ecole_id: int, donnees: FieldIn, db: Session = Depends(get_db)):
        try:
            field = f.create(db, ecole_id, _saison(db, ecole_id), **donnees.model_dump())
        except f.FieldError as erreur:
            raise _erreur(erreur) from erreur
        db.commit()
        return field

    def modifier(
        self, field_id: int, donnees: FieldPatch, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        field = self._champ(db, field_id, appelant)
        try:
            f.update(db, field, **donnees.model_dump(exclude_unset=True))
        except f.FieldError as erreur:
            db.rollback()
            raise _erreur(erreur) from erreur
        db.commit()
        return field

    def retirer(self, field_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        try:
            f.remove(self._champ(db, field_id, appelant))
        except f.FieldError as erreur:
            raise _erreur(erreur) from erreur
        db.commit()
        return Response(status_code=204)

    def remettre(self, field_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        field = self._champ(db, field_id, appelant)
        f.restore(field)
        db.commit()
        return field

    def toutes_reponses(self, ecole_id: int, db: Session = Depends(get_db)):
        """{fiche: {champ: réponse}} : les colonnes du tableau des membres."""
        return values.all_answers(db, ecole_id, _saison(db, ecole_id))

    # --- L'affichage dans Admin ---

    def colonnes(self, ecole_id: int, db: Session = Depends(get_db)):
        return cols.columns(db, ecole_id, _saison(db, ecole_id))

    def changer_colonnes(self, ecole_id: int, donnees: list[ColumnIn], db: Session = Depends(get_db)):
        try:
            resultat = cols.save(db, ecole_id, _saison(db, ecole_id), [c.model_dump() for c in donnees])
        except f.FieldError as erreur:
            db.rollback()
            raise _erreur(erreur) from erreur
        db.commit()
        return resultat

    # --- Les réponses d'une fiche ---

    def reponses(self, compte_id: int, db: Session = Depends(get_db), appelant: Compte = Depends(rbac.compte_appelant)):
        return values.answers(db, self._fiche(db, compte_id, appelant))

    def repondre(
        self, compte_id: int, field_id: int, donnees: AnswerIn, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        fiche = self._fiche(db, compte_id, appelant)
        try:
            values.set_answer(db, fiche, field_id, donnees.value)
        except (LookupError, f.FieldError) as erreur:
            db.rollback()
            raise _erreur(erreur) from erreur
        db.commit()
        return Response(status_code=204)

    def envoyer_fichier(
        self, compte_id: int, field_id: int, fichier: UploadFile = File(...), db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        fiche = self._fiche(db, compte_id, appelant)
        try:
            valeur = values.set_file(db, self.storage, fiche, field_id, fichier.file, fichier.filename or "")
        except FileTooLarge as erreur:
            raise HTTPException(status_code=413, detail=str(erreur)) from erreur
        except (LookupError, f.FieldError) as erreur:
            db.rollback()
            raise _erreur(erreur) from erreur
        db.commit()
        return valeur

    def fichier(
        self, compte_id: int, field_id: int, db: Session = Depends(get_db),
        appelant: Compte = Depends(rbac.compte_appelant),
    ):
        fiche = self._fiche(db, compte_id, appelant)
        try:
            valeur = values.file_of(db, fiche, field_id)
        except LookupError as erreur:
            raise _erreur(erreur) from erreur
        chemin = self.storage.path(fiche.ecole_id, valeur["sha256"])
        if not chemin.is_file():
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        return FileResponse(
            chemin, media_type=guess_mime(valeur["name"]), filename=valeur["name"],
            content_disposition_type="inline", headers={"Cache-Control": "private, max-age=3600"},
        )
