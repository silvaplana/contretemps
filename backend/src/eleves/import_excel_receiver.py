"""Routes REST de l'import du fichier élèves officiel (voir
spec/SPEC.md §6.4bis). Fichier séparé de receiver.py (comme
import_excel.py l'est de eleves.py) — MÊME code appelé depuis 2 écrans
(Admin > École > menu "Intégrer fichier élèves officiel" ET Admin >
Élèves > "Importer", décision utilisateur explicite : une seule fonction,
jamais 2 implémentations)."""

from __future__ import annotations

import io

from comptes import Compte, rbac
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
        # Les 3 routes sont réservées aux admins de l'école (RBAC, §2.4).
        admin = [Depends(self._admin_ecole)]
        self.app.post(
            "/eleves/import/previsualiser", response_model=ApercuImportSortie, dependencies=admin
        )(self.previsualiser)
        self.app.post(
            "/eleves/import/valider", response_model=ResultatImportSortie, dependencies=admin
        )(self.valider)
        self.app.post(
            "/eleves/import/mapping-colonne",
            response_model=MappingColonneSortie,
            status_code=201,
            dependencies=admin,
        )(self.memoriser_mapping_colonne)

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    async def previsualiser(
        self, ecole_id: int, fichier: UploadFile, db: Session = Depends(get_db)
    ):
        contenu = await fichier.read()
        try:
            apercu = self.client.previsualiser(
                db, ecole_id, io.BytesIO(contenu), fichier.filename or ""
            )
        except Exception as exc:  # fichier illisible/mal formé/contrainte de format non respectée
            raise HTTPException(status_code=400, detail=f"Fichier invalide : {exc}") from exc
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
                creer=ligne.creer,
                champs_a_appliquer=ligne.champs_a_appliquer,
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
