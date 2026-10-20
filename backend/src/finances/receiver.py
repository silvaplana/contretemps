"""Routes REST du sous-module Comptes (/finances/...). Qui appelle est
fourni par l'appli hôte (`current_member`, une dépendance FastAPI qui
renvoie un `Member`) ; les droits sont vérifiés par le service."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db

from .exports import to_pdf, to_xlsx
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


def _http(error: Exception) -> HTTPException:
    if isinstance(error, ReportNotFoundError):
        return HTTPException(status_code=404, detail="Bilan inconnu")
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
    ) -> None:
        """seasons(db, org_id) : les saisons de l'organisation (période
        « Saisons » du graphique) ; reports : sous-module Bilan."""
        self.client = client
        self.app = app
        self.current_member = current_member
        self.seasons = seasons
        self.reports = reports
        self._register_routes()
        if reports is not None:
            self._register_report_routes()

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
