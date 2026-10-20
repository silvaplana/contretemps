"""Routes REST du module finances (/finances/...). Qui appelle est
fourni par l'appli hôte (`current_member`, une dépendance FastAPI qui
renvoie un `Member`) ; les droits sont vérifiés par le service."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db

from .assemblies import PPTX, AssemblyError, AssemblyNotFoundError, GeneralAssemblies
from .exports import to_pdf, to_xlsx
from .forecasts import ForecastError, ForecastNotFoundError, Forecasts
from .ports import Member, Season
from .reports import FinancialReports, ReportError, ReportNotFoundError
from .service import AccountNotFoundError, Finances


class ReportRequest(BaseModel):
    """Corps de POST /finances/reports et PUT /finances/reports/{id}.
    state : "brouillon", "valide" ou "officiel" ; model : clé de ai.MODELS."""

    seasonId: int | None = None
    name: str
    state: str = "brouillon"
    prompt: str = ""
    model: str | None = None


class RunRequest(BaseModel):
    """Corps de POST /finances/reports/{id}/run : consignes et modèle du
    calcul (enregistrés dans le bilan)."""

    prompt: str | None = None
    model: str | None = None


class ForecastRequest(BaseModel):
    """Corps de POST /finances/forecasts et PUT /finances/forecasts/{id} :
    comme ReportRequest, plus startDate (AAAA-MM-JJ, vide pour le dernier
    jour connu des comptes)."""

    seasonId: int | None = None
    name: str
    state: str = "brouillon"
    prompt: str = ""
    model: str | None = None
    startDate: str | None = None


class ForecastRunRequest(BaseModel):
    """Corps de POST /finances/forecasts/{id}/run : champs du formulaire,
    enregistrés avant le calcul."""

    name: str | None = None
    state: str | None = None
    prompt: str | None = None
    model: str | None = None
    startDate: str | None = None


class ParamsRequest(BaseModel):
    """Corps de PUT /finances/forecasts/{id}/params : position des curseurs."""

    params: dict[str, float]


class ModelRequest(BaseModel):
    """Corps de PUT /finances/assemblies/{id}/model : PowerPoint à copier
    comme modèle de l'AG. kind : "modele", "genere" ou "modifie" d'une autre
    AG (sourceId), ou "general" (modèle général de l'organisation)."""

    sourceId: int | None = None
    kind: str


def _http(error: Exception) -> HTTPException:
    if isinstance(error, ReportNotFoundError):
        return HTTPException(status_code=404, detail="Bilan inconnu")
    if isinstance(error, AssemblyNotFoundError):
        return HTTPException(status_code=404, detail="Introuvable")
    if isinstance(error, ForecastNotFoundError):
        return HTTPException(status_code=404, detail="Prévisionnel inconnu")
    if isinstance(error, PermissionError):
        return HTTPException(status_code=403, detail=str(error))
    return HTTPException(status_code=400, detail=str(error))


class FinancesReceiver:
    def __init__(
        self,
        client: Finances,
        app: FastAPI,
        current_member: Callable[..., Member],
        seasons: Callable[[Session, int], list[Season]],
        reports: FinancialReports | None = None,
        assemblies: GeneralAssemblies | None = None,
        forecasts: Forecasts | None = None,
    ) -> None:
        """seasons(db, org_id) : les saisons de l'organisation (période
        « Saisons » du graphique) ; reports : sous-module Bilan ; assemblies :
        sous-module Assemblée générale ; forecasts : sous-module Prévisionnel."""
        self.client = client
        self.app = app
        self.current_member = current_member
        self.seasons = seasons
        self.reports = reports
        self.assemblies = assemblies
        self.forecasts = forecasts
        self._register_routes()
        if reports is not None:
            self._register_report_routes()
        if assemblies is not None:
            self._register_assembly_routes()
        if forecasts is not None:
            self._register_forecast_routes()

    def _register_routes(self) -> None:
        app, client = self.app, self.client
        db_dep = Depends(get_db)
        member_dep = Depends(self.current_member)

        @app.post("/finances/import")
        async def import_statements(files: list[UploadFile], db: Session = db_dep, member: Member = member_dep) -> dict:
            """Relevés PDF ou archives (multipart, champ "files" répété) :
            compte rendu importés / déjà présents / erreurs."""
            uploaded = [(f.filename or "releve.pdf", await f.read()) for f in files]
            try:
                # Lecture des PDF dans un thread : plusieurs secondes pour une
                # archive de relevés.
                return await run_in_threadpool(client.import_files, db, member, uploaded)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc

        @app.get("/finances/ledger")
        def get_ledger(account: int | None = None, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Historique de tous les comptes ensemble (défaut) ou d'un seul."""
            try:
                return client.get_ledger(db, member, account)
            except AccountNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Compte inconnu") from exc
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc

        @app.get("/finances/seasons")
        def get_seasons(db: Session = db_dep, member: Member = member_dep) -> dict:
            """Saisons de l'organisation, de la plus ancienne à la plus
            récente, et la date du jour."""
            if not member.keeps_accounts:
                raise HTTPException(status_code=403, detail="Réservé aux trésoriers")
            return {
                "seasons": [
                    {"id": s.id, "name": s.name, "startDate": s.start_date, "endDate": s.end_date, "current": s.current}
                    for s in self.seasons(db, member.org_id)
                ],
                "today": dt.date.today().isoformat(),
            }

    def _register_report_routes(self) -> None:
        app, reports = self.app, self.reports
        db_dep = Depends(get_db)
        member_dep = Depends(self.current_member)

        def call(action, *args):
            try:
                return action(*args)
            except (ReportError, ReportNotFoundError, PermissionError) as error:
                raise _http(error) from error

        @app.get("/finances/reports")
        def list_reports(seasonId: int | None = None, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Bilans de la saison (sans leur résultat), modèles et états
            possibles, nombre de bilans par saison."""
            return {
                **reports.models(),
                "counts": call(reports.counts, db, member),
                "reports": call(reports.list, db, member, seasonId) if seasonId is not None else [],
            }

        @app.post("/finances/reports", status_code=201)
        def create_report(request: ReportRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(reports.create, db, member, request.model_dump())

        @app.get("/finances/reports/{report_id}")
        def get_report(report_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Bilan complet, relu par l'écran pendant un calcul."""
            return call(reports.get, db, member, report_id)

        @app.put("/finances/reports/{report_id}")
        def update_report(report_id: int, request: ReportRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(reports.update, db, member, report_id, request.model_dump())

        @app.delete("/finances/reports/{report_id}", status_code=204)
        def delete_report(report_id: int, db: Session = db_dep, member: Member = member_dep) -> Response:
            call(reports.delete, db, member, report_id)
            return Response(status_code=204)

        @app.post("/finances/reports/{report_id}/run")
        def run_report(report_id: int, request: RunRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Lance le calcul (tableau + analyse) en arrière-plan."""
            return call(reports.run, db, member, report_id, request.model_dump())

        @app.get("/finances/reports/{report_id}/download")
        def download_report(report_id: int, format: str = "xlsx", db: Session = db_dep, member: Member = member_dep) -> Response:
            """Résultat du dernier calcul en fichier (xlsx ou pdf)."""
            report = call(reports.get, db, member, report_id)
            if report["result"] is None:
                raise HTTPException(status_code=400, detail="Ce bilan n'a pas encore été calculé")
            if format == "pdf":
                content, media_type = to_pdf(report), "application/pdf"
            elif format == "xlsx":
                content = to_xlsx(report)
                media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            else:
                raise HTTPException(status_code=400, detail="Format inconnu (xlsx ou pdf)")
            name = f"bilan-{report['result']['seasonName']}-{report['id']}.{format}"
            return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{name}"'})

    def _register_assembly_routes(self) -> None:
        """Routes du sous-module Assemblée générale (/finances/assemblies)."""
        app, assemblies = self.app, self.assemblies
        db_dep = Depends(get_db)
        member_dep = Depends(self.current_member)

        def call(action, *args):
            try:
                return action(*args)
            except (AssemblyError, AssemblyNotFoundError, PermissionError) as error:
                raise _http(error) from error

        @app.get("/finances/assemblies")
        def list_assemblies(seasonId: int | None = None, db: Session = db_dep, member: Member = member_dep) -> dict:
            """AG de la saison, modèles, états, bilan et PowerPoint modèle que
            prendrait un calcul, nombre d'AG par saison."""
            return {
                **call(assemblies.options, db, member, seasonId),
                "counts": call(assemblies.counts, db, member),
                "assemblies": call(assemblies.list, db, member, seasonId) if seasonId is not None else [],
            }

        @app.post("/finances/assemblies", status_code=201)
        def create_assembly(request: ReportRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(assemblies.create, db, member, request.model_dump())

        @app.post("/finances/assemblies/template")
        async def upload_template(file: UploadFile, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Modèle général de l'organisation (pris quand la saison
            précédente n'a pas d'AG officielle)."""
            content = await file.read()
            return call(assemblies.set_template, member, content)

        # Avant /finances/assemblies/{assembly_id} : sinon pris pour un id.
        @app.get("/finances/assemblies/model-sources")
        def model_sources(exclude: int | None = None, db: Session = db_dep, member: Member = member_dep) -> list[dict]:
            return call(assemblies.model_sources, db, member, exclude)

        @app.get("/finances/assemblies/{assembly_id}")
        def get_assembly(assembly_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(assemblies.get, db, member, assembly_id)

        @app.put("/finances/assemblies/{assembly_id}")
        def update_assembly(assembly_id: int, request: ReportRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(assemblies.update, db, member, assembly_id, request.model_dump())

        @app.delete("/finances/assemblies/{assembly_id}", status_code=204)
        def delete_assembly(assembly_id: int, db: Session = db_dep, member: Member = member_dep) -> Response:
            call(assemblies.delete, db, member, assembly_id)
            return Response(status_code=204)

        @app.post("/finances/assemblies/{assembly_id}/run")
        def run_assembly(assembly_id: int, request: RunRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Lance la préparation du PowerPoint en arrière-plan."""
            return call(assemblies.run, db, member, assembly_id, request.model_dump())

        @app.post("/finances/assemblies/{assembly_id}/upload")
        async def upload_modified(assembly_id: int, file: UploadFile, db: Session = db_dep, member: Member = member_dep) -> dict:
            """PowerPoint retouché par le trésorier (remplace le précédent)."""
            content = await file.read()
            return call(assemblies.upload, db, member, assembly_id, content, file.filename or "ag.pptx")

        @app.post("/finances/assemblies/{assembly_id}/model")
        async def upload_model(assembly_id: int, file: UploadFile, db: Session = db_dep, member: Member = member_dep) -> dict:
            """PowerPoint modèle de l'AG, envoyé depuis l'ordinateur."""
            content = await file.read()
            return call(assemblies.set_model, db, member, assembly_id, content, file.filename or "modele.pptx")

        @app.put("/finances/assemblies/{assembly_id}/model")
        def copy_model(assembly_id: int, request: ModelRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(assemblies.copy_model, db, member, assembly_id, request.sourceId, request.kind)

        @app.get("/finances/assemblies/{assembly_id}/download")
        def download_assembly(assembly_id: int, kind: str | None = None, db: Session = db_dep, member: Member = member_dep) -> FileResponse:
            """Un des 3 PowerPoint de l'AG (kind "modele", "genere", "modifie") ;
            sans kind, le PowerPoint final (modifié, sinon produit)."""
            path, filename = call(assemblies.file_path, db, member, assembly_id, kind)
            return FileResponse(path, media_type=PPTX, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"})

        @app.get("/finances/assemblies/{assembly_id}/files/{kind}/slides")
        async def get_slides(assembly_id: int, kind: str, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Textes des diapos et images disponibles (LibreOffice)."""
            return await run_in_threadpool(call, assemblies.slides, db, member, assembly_id, kind)

        @app.get("/finances/assemblies/{assembly_id}/files/{kind}/slides/{image}.png")
        def get_thumbnail(assembly_id: int, kind: str, image: int, db: Session = db_dep, member: Member = member_dep) -> FileResponse:
            return FileResponse(call(assemblies.thumbnail, db, member, assembly_id, kind, image), media_type="image/png")

    def _register_forecast_routes(self) -> None:
        """Routes du sous-module Prévisionnel (/finances/forecasts)."""
        app, forecasts = self.app, self.forecasts
        db_dep = Depends(get_db)
        member_dep = Depends(self.current_member)

        def call(action, *args):
            try:
                return action(*args)
            except (ForecastError, ForecastNotFoundError, PermissionError, ValueError) as error:
                raise _http(error) from error

        @app.get("/finances/forecasts")
        def list_forecasts(seasonId: int | None = None, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Prévisionnels de la saison (sans leur résultat), modèles et
            états possibles, nombre de prévisionnels par saison."""
            return {
                **forecasts.models(),
                "counts": call(forecasts.counts, db, member),
                "forecasts": call(forecasts.list, db, member, seasonId) if seasonId is not None else [],
            }

        @app.post("/finances/forecasts", status_code=201)
        def create_forecast(request: ForecastRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(forecasts.create, db, member, request.model_dump())

        @app.get("/finances/forecasts/{forecast_id}")
        def get_forecast(forecast_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Prévisionnel complet (formule, curseurs, courbe), relu par
            l'écran pendant un calcul."""
            return call(forecasts.get, db, member, forecast_id)

        @app.put("/finances/forecasts/{forecast_id}")
        def update_forecast(forecast_id: int, request: ForecastRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(forecasts.update, db, member, forecast_id, request.model_dump())

        @app.delete("/finances/forecasts/{forecast_id}", status_code=204)
        def delete_forecast(forecast_id: int, db: Session = db_dep, member: Member = member_dep) -> Response:
            call(forecasts.delete, db, member, forecast_id)
            return Response(status_code=204)

        @app.post("/finances/forecasts/{forecast_id}/run")
        def run_forecast(forecast_id: int, request: ForecastRunRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Lance le calcul (formule + courbe) en arrière-plan."""
            return call(forecasts.run, db, member, forecast_id, request.model_dump())

        @app.put("/finances/forecasts/{forecast_id}/params")
        def set_forecast_params(forecast_id: int, request: ParamsRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Rejoue la formule avec les curseurs (sans rappeler le modèle)."""
            return call(forecasts.set_params, db, member, forecast_id, request.params)

        @app.get("/finances/forecasts/{forecast_id}/download")
        def download_forecast(
            forecast_id: int, format: str = "png", seasons: str | None = None, db: Session = db_dep, member: Member = member_dep
        ) -> Response:
            """Résultat en image (png) ou PDF. seasons : ids des saisons
            comparées, séparés par des virgules (absent : la précédente)."""
            ids = [int(s) for s in seasons.split(",") if s.strip()] if seasons is not None else None
            content, media_type, name = call(forecasts.export, db, member, forecast_id, format, ids)
            return Response(content, media_type=media_type, headers={"Content-Disposition": f'attachment; filename="{name}"'})
