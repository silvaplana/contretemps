"""Routes REST des écoles — reçoit les requêtes HTTP, délègue tout à
Ecoles (voir ecoles.py) ou aux 2 modules d'export (voir excel_export.py/
backup_technique.py), ne fait aucun calcul métier ici.
"""

from __future__ import annotations

from datetime import datetime

from comptes import Compte, Comptes, rbac
from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from db import get_db

from . import backup_technique, excel_export
from .ecoles import Ecoles
from .excel_export import EcoleExport
from .schemas import (
    EcoleCreation,
    EcoleModification,
    EcolePublique,
    EcoleSortie,
    SauvegardeFichier,
    SauvegardeProgrammeeModification,
)
from .stockage import dossier_ecole

MEDIA_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class EcolesReceiver:
    """Comme les autres receivers (voir main.py) : enregistre ses routes
    sur une app FastAPI existante, partagée avec les autres modules.

    `export`/`comptes` (voir excel_export.py/backup_technique.py) ont
    besoin de comptes/eleves/cours/presence — instancié plus tard dans
    main.py que `client` (qui, lui, n'a aucune dépendance et doit exister
    tôt pour `auth_client`) : voir le commentaire à l'endroit où
    `EcolesReceiver(...)` est construit."""

    def __init__(self, client: Ecoles, export: EcoleExport, comptes: Comptes, app: FastAPI) -> None:
        self.client = client
        self.export = export
        self.comptes = comptes
        self.app = app
        self._register_routes()

    def _register_routes(self) -> None:
        # PUBLIQUE (appelée avant la connexion, pour savoir dans quelle école
        # se connecter) : jamais les codes d'accès — jusqu'au 2026-09-21
        # elle les renvoyait tous, code admin compris, à n'importe qui.
        self.app.get("/ecoles", response_model=list[EcolePublique])(self.lister)
        # Tout le reste est réservé aux admins de l'école (RBAC, §2.4).
        admin = [Depends(self._admin_ecole)]
        self.app.get("/ecoles/{ecole_id}", response_model=EcoleSortie, dependencies=admin)(
            self.obtenir
        )
        # Créer une école : réservé au propriétaire de l'application (§2.5).
        self.app.post(
            "/ecoles",
            response_model=EcoleSortie,
            status_code=201,
            dependencies=[Depends(self._superuser)],
        )(self.creer)
        self.app.put("/ecoles/{ecole_id}", response_model=EcoleSortie, dependencies=admin)(
            self.modifier
        )
        # "Sauvegarder École" (Admin > École, menu) — les 2 fichiers.
        self.app.get("/ecoles/{ecole_id}/export", dependencies=admin)(self.exporter)
        self.app.get("/ecoles/{ecole_id}/export-technique", dependencies=admin)(
            self.exporter_technique
        )
        # "Programmer sauvegarde École".
        self.app.put(
            "/ecoles/{ecole_id}/sauvegarde-programmee",
            response_model=EcoleSortie,
            dependencies=admin,
        )(self.programmer_sauvegarde)
        # Historique des sauvegardes générées par le worker programmé
        # (voir app/sauvegarde_worker.py et ecoles/stockage.py) — filet de
        # sécurité serveur, téléchargeable à la demande.
        self.app.get(
            "/ecoles/{ecole_id}/sauvegardes",
            response_model=list[SauvegardeFichier],
            dependencies=admin,
        )(self.lister_sauvegardes)
        self.app.get("/ecoles/{ecole_id}/sauvegardes/{nom_fichier}", dependencies=admin)(
            self.telecharger_sauvegarde
        )
        # "Supprimer Données École" / "Importer sauvegarde".
        self.app.delete("/ecoles/{ecole_id}/donnees", status_code=204, dependencies=admin)(
            self.supprimer_donnees
        )
        self.app.post("/ecoles/{ecole_id}/restaurer", status_code=204, dependencies=admin)(
            self.restaurer
        )

    def _admin_ecole(self, ecole_id: int, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_admin(appelant, ecole_id)

    def _superuser(self, appelant: Compte = Depends(rbac.compte_appelant)) -> None:
        rbac.require_superuser(appelant)

    def lister(self, db: Session = Depends(get_db)):
        return self.client.list(db)

    def obtenir(self, ecole_id: int, db: Session = Depends(get_db)):
        ecole = self.client.get(db, ecole_id)
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        return ecole

    def creer(self, donnees: EcoleCreation, db: Session = Depends(get_db)):
        """Voir spec §2.3 : crée l'école. La création du premier compte
        admin associé est faite par le module comptes (appelée depuis le
        même endpoint côté frontend, pas ici — ecoles ne connaît pas
        comptes)."""
        existante = self.client.find_by_nom_code_postal(db, donnees.nom, donnees.code_postal)
        if existante is not None:
            raise HTTPException(
                status_code=409,
                detail="Une école avec ce nom et ce code postal existe déjà",
            )
        return self.client.create(db, **donnees.model_dump())

    def modifier(self, ecole_id: int, donnees: EcoleModification, db: Session = Depends(get_db)):
        ecole = self.client.update(db, ecole_id, **donnees.model_dump(exclude_unset=True))
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        return ecole

    def _obtenir_ou_404(self, db: Session, ecole_id: int):
        ecole = self.client.get(db, ecole_id)
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        return ecole

    def exporter(self, ecole_id: int, db: Session = Depends(get_db)):
        """Fichier "humain" (Élèves/Profs/Cours) — voir excel_export.py."""
        ecole = self._obtenir_ou_404(db, ecole_id)
        return Response(
            content=self.export.generer(db, ecole),
            media_type=MEDIA_TYPE_XLSX,
            headers={"Content-Disposition": f'attachment; filename="{excel_export.nom_fichier(ecole)}"'},
        )

    def exporter_technique(self, ecole_id: int, db: Session = Depends(get_db)):
        """Fichier technique complet — voir backup_technique.py."""
        ecole = self._obtenir_ou_404(db, ecole_id)
        return Response(
            content=backup_technique.generer(db, ecole),
            media_type=MEDIA_TYPE_XLSX,
            headers={
                "Content-Disposition": f'attachment; filename="{backup_technique.nom_fichier(ecole)}"'
            },
        )

    def programmer_sauvegarde(
        self, ecole_id: int, donnees: SauvegardeProgrammeeModification, db: Session = Depends(get_db)
    ):
        ecole = self.client.update(
            db,
            ecole_id,
            sauvegarde_active=donnees.active,
            sauvegarde_periodicite=donnees.periodicite,
            sauvegarde_jour_semaine=donnees.jour_semaine,
            sauvegarde_heure=donnees.heure,
        )
        if ecole is None:
            raise HTTPException(status_code=404, detail="École introuvable")
        return ecole

    def lister_sauvegardes(self, ecole_id: int, db: Session = Depends(get_db)):
        self._obtenir_ou_404(db, ecole_id)
        fichiers = sorted(dossier_ecole(ecole_id).glob("*.xlsx"), reverse=True)
        return [
            SauvegardeFichier(
                nom=f.name,
                date=datetime.fromtimestamp(f.stat().st_mtime),
                taille_octets=f.stat().st_size,
            )
            for f in fichiers
        ]

    def telecharger_sauvegarde(self, ecole_id: int, nom_fichier: str, db: Session = Depends(get_db)):
        self._obtenir_ou_404(db, ecole_id)
        # `nom_fichier` vient directement de lister_sauvegardes() (pas
        # saisi à la main) — mais on se protège quand même d'un chemin
        # malicieux ("../../...") avant de toucher au disque.
        if "/" in nom_fichier or "\\" in nom_fichier:
            raise HTTPException(status_code=400, detail="Nom de fichier invalide")
        chemin = dossier_ecole(ecole_id) / nom_fichier
        if not chemin.is_file():
            raise HTTPException(status_code=404, detail="Sauvegarde introuvable")
        return Response(
            content=chemin.read_bytes(),
            media_type=MEDIA_TYPE_XLSX,
            headers={"Content-Disposition": f'attachment; filename="{nom_fichier}"'},
        )

    def supprimer_donnees(self, ecole_id: int, db: Session = Depends(get_db)):
        """"Supprimer Données École" — voir backup_technique.vider(). Garde
        le compte admin le plus ANCIEN (id le plus bas, voir sa docstring)
        pour que quelqu'un puisse encore se connecter ensuite."""
        self._obtenir_ou_404(db, ecole_id)
        admins = sorted(self.comptes.list_par_role(db, ecole_id, role="admin"), key=lambda c: c.id)
        garder_compte_id = admins[0].id if admins else None
        backup_technique.vider(db, ecole_id, garder_compte_id=garder_compte_id)

    async def restaurer(self, ecole_id: int, fichier: UploadFile, db: Session = Depends(get_db)):
        """"Importer sauvegarde" — ÉCRASE toutes les données actuelles de
        l'école (voir backup_technique.restaurer(), aucune confirmation
        ici : déjà faite côté frontend, voir SauvegardeEcoleMenu.jsx)."""
        ecole = self._obtenir_ou_404(db, ecole_id)
        contenu = await fichier.read()
        try:
            backup_technique.restaurer(db, ecole, contenu)
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=400, detail=f"Fichier de sauvegarde illisible ou invalide : {exc}"
            ) from exc
