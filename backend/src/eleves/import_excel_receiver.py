"""Routes REST de l'import Excel des élèves (voir spec/SPEC.md §6.4bis).
Fichier séparé de receiver.py (comme import_excel.py l'est de eleves.py)
— même écran (Admin > Élèves, bouton "Importer depuis Excel"), mais un
sous-ensemble de routes assez spécifique pour être isolé.
"""

from __future__ import annotations

import io

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from sqlalchemy.orm import Session

from db import get_db

from .import_excel import ImportExcel, LigneApercu
from .schemas import (
    ApercuImportSortie,
    LigneApercuSortie,
    MappingColonneEntree,
    MappingColonneSortie,
    ResultatImportSortie,
    ValidationImportEntree,
)


class ImportExcelReceiver:
    def __init__(self, client: ImportExcel, app: FastAPI) -> None:
        self.client = client
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        self.app.post(
            "/eleves/import/previsualiser", response_model=ApercuImportSortie
        )(self.previsualiser)
        self.app.post(
            "/eleves/import/valider", response_model=ResultatImportSortie
        )(self.valider)
        self.app.post(
            "/eleves/import/mapping-colonne",
            response_model=MappingColonneSortie,
            status_code=201,
        )(self.memoriser_mapping_colonne)

    async def previsualiser(
        self, ecole_id: int, fichier: UploadFile, db: Session = Depends(get_db)
    ):
        contenu = await fichier.read()
        try:
            apercu = self.client.previsualiser(db, ecole_id, io.BytesIO(contenu))
        except Exception as exc:  # fichier illisible/mal formé
            raise HTTPException(status_code=400, detail=f"Fichier illisible : {exc}") from exc
        return apercu

    def valider(
        self, ecole_id: int, donnees: ValidationImportEntree, db: Session = Depends(get_db)
    ):
        lignes = [
            LigneApercu(
                numero_ligne=ligne.numero_ligne,
                nom=ligne.nom,
                prenom=ligne.prenom,
                email=ligne.email,
                telephone=ligne.telephone,
                telephone_suspect=False,
                adresse=ligne.adresse,
                date_naissance=ligne.date_naissance,
                contact_parent_brut=ligne.contact_parent_brut,
                cours_ids=ligne.cours_ids,
                eleve_existant_id=ligne.eleve_existant_id,
                action=ligne.action,
            )
            for ligne in donnees.lignes
        ]
        return self.client.valider(db, ecole_id, lignes)

    def memoriser_mapping_colonne(
        self, ecole_id: int, donnees: MappingColonneEntree, db: Session = Depends(get_db)
    ):
        return self.client.memoriser_mapping_colonne(
            db, ecole_id, donnees.en_tete_excel, donnees.cours_id
        )
