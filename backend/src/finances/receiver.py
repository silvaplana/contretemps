"""Routes REST du module finances (/finances/...). Qui appelle est
fourni par l'appli hôte (`current_member`, une dépendance FastAPI qui
renvoie un `Member`) ; les droits sont vérifiés par le service."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Response, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db

from .accounting import Accounting, AccountingError
from .ag_documents import AgDocuments
from .ai import AnalysisError
from .written_report import WrittenReports
from .assemblies import PPTX, AssemblyError, AssemblyNotFoundError, GeneralAssemblies
from .bank import Bank, BankError
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


class ConnectRequest(BaseModel):
    """Corps de POST /finances/bank/connect : la banque (nom exact de la
    liste) et l'espace, "personal" (particuliers) ou "business" (pros)."""

    bank: str
    psuType: str = "personal"


class FollowRequest(BaseModel):
    """Corps de PUT /finances/bank/accounts : les comptes suivis (uid)."""

    uids: list[str]


class RenameRequest(BaseModel):
    """Corps de PUT /finances/accounts/{id}."""

    name: str


class ChartAccountRequest(BaseModel):
    """Corps de POST /finances/chart et PUT /finances/chart/{id} : un compte
    du plan (spec §8.2)."""

    number: str
    label: str
    nature: str | None = None
    event: str | None = None
    keywords: list[str] = []
    active: bool | None = None


class LevelRequest(BaseModel):
    """Corps de PUT /finances/chart/level : "simple" ou "complet"."""

    level: str


class WriteRequest(BaseModel):
    """Corps de POST /finances/reports/{id}/rapport : consignes et modèle."""

    prompt: str = ""
    model: str | None = None


class OpeningRequest(BaseModel):
    """Corps de PUT /finances/opening-balances/{season_id} : un solde par compte."""

    accounts: list[dict]


class LinesRequest(BaseModel):
    """Corps de PUT /finances/operations/{id}/accounts : la ventilation
    confirmée ({accountId, amount en euros}) ; une seule ligne = tout le
    montant ; vide = compte retiré."""

    lines: list[dict]


class CashLineRequest(BaseModel):
    """Corps de POST /finances/cash : une ligne de caisse (spec §8.5)."""

    date: str
    label: str
    amount: float
    accountId: int | None = None
    transferOperationId: int | None = None
    docNodeId: int | None = None


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
        bank: Bank | None = None,
        org_url: Callable[[Session, int | None], str] | None = None,
        accounting: Accounting | None = None,
        ag_documents: AgDocuments | None = None,
        written_reports: WrittenReports | None = None,
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
        self.bank = bank
        # org_url(db, org_id) : l'adresse de l'appli de l'organisation, où
        # revenir après la banque.
        self.org_url = org_url
        self.accounting = accounting
        self.ag_documents = ag_documents
        self.written_reports = written_reports
        self._register_routes()
        if accounting is not None:
            self._register_accounting_routes()
        if bank is not None:
            self._register_bank_routes()
        if reports is not None:
            self._register_report_routes()
        if reports is not None and ag_documents is not None:
            self._register_ag_document_routes()
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

    def _register_bank_routes(self) -> None:
        """Connexion bancaire (bank.py, spec financier.md §3.5)."""
        app, bank = self.app, self.bank
        db_dep = Depends(get_db)
        member_dep = Depends(self.current_member)

        def call(action, *args):
            try:
                return action(*args)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except BankError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc

        @app.get("/finances/bank")
        def bank_status(db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(bank.status, db, member)

        @app.get("/finances/bank/banks")
        def bank_list(q: str = "", member: Member = member_dep) -> dict:
            return {"banks": call(bank.banks, member, q)}

        @app.post("/finances/bank/connect")
        def bank_connect(data: ConnectRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return {"url": call(bank.connect, db, member, data.bank, data.psuType)}

        @app.put("/finances/bank/accounts")
        def bank_follow(data: FollowRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(bank.follow, db, member, data.uids)

        @app.post("/finances/bank/sync")
        def bank_sync(db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(bank.sync, db, member)

        @app.get("/finances/bank/return")
        def bank_return(state: str = "", code: str = "", error: str = "", db: Session = db_dep):
            """Retour de la banque (route publique : `state`, aléatoire et
            valable 30 minutes, dit quelle organisation revient). Le serveur
            termine la connexion, puis renvoie vers l'adresse de l'école :
            la session de connexion de la personne est liée à cette adresse."""
            from sqlalchemy import select

            from .models import FinBankConnection

            connection = db.scalar(select(FinBankConnection).where(FinBankConnection.state == state)) if state else None
            org_id = connection.org_id if connection is not None else None
            if error or not code:
                if connection is not None:
                    connection.state, connection.state_at, connection.pending = None, None, None
                    db.commit()
                resultat = "annule"
            else:
                try:
                    org_id = bank.complete(db, code, state)
                    resultat = "ok"
                except BankError:
                    resultat = "erreur"
            # org_id inconnu (retour inconnu ou expiré) : l'adresse générale de
            # l'appli, jamais une adresse relative (qui remonterait à la racine
            # du site).
            base = self.org_url(db, org_id) if self.org_url is not None else ""
            return RedirectResponse(f"{base.rstrip('/')}/?banque={resultat}", status_code=303)

        @app.put("/finances/accounts/{account_id}")
        def rename_account(account_id: int, data: RenameRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            try:
                return self.client.rename_account(db, member, account_id, data.name)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except AccountNotFoundError as exc:
                raise HTTPException(status_code=404, detail="Compte inconnu") from exc
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    def _register_accounting_routes(self) -> None:
        """Comptabilité (accounting.py, spec §8) : plan comptable, niveau,
        compte sur chaque ligne, caisse."""
        app, accounting = self.app, self.accounting
        db_dep = Depends(get_db)
        member_dep = Depends(self.current_member)

        def call(action, *args):
            try:
                return action(*args)
            except PermissionError as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
            except LookupError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            except (AccountingError, ValueError) as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

        @app.get("/finances/chart")
        def get_chart(db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(accounting.chart, db, member)

        @app.put("/finances/chart/level")
        def set_level(data: LevelRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return {"level": call(accounting.set_level, db, member, data.level)}

        @app.post("/finances/chart", status_code=201)
        def create_chart_account(data: ChartAccountRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(accounting.create_account, db, member, data.model_dump())

        @app.put("/finances/chart/{account_id}")
        def update_chart_account(
            account_id: int, data: ChartAccountRequest, db: Session = db_dep, member: Member = member_dep
        ) -> dict:
            return call(accounting.update_account, db, member, account_id, data.model_dump(exclude_none=True))

        @app.delete("/finances/chart/{account_id}", status_code=204)
        def delete_chart_account(account_id: int, db: Session = db_dep, member: Member = member_dep) -> Response:
            call(accounting.delete_account, db, member, account_id)
            return Response(status_code=204)

        @app.get("/finances/operations/{operation_id}")
        def get_operation(operation_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            """La fiche d'une opération (spec §8.4)."""
            return call(accounting.operation, db, member, operation_id)

        @app.put("/finances/operations/{operation_id}/accounts")
        def set_operation_accounts(
            operation_id: int, data: LinesRequest, db: Session = db_dep, member: Member = member_dep
        ) -> dict:
            return call(accounting.set_lines, db, member, operation_id, data.lines)

        @app.get("/finances/cash")
        def get_cash(db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(accounting.cash, db, member)

        @app.post("/finances/cash", status_code=201)
        def add_cash_line(data: CashLineRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(accounting.add_cash_line, db, member, data.model_dump())

        @app.delete("/finances/cash/{line_id}")
        def delete_cash_line(line_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            return call(accounting.delete_cash_line, db, member, line_id)

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

    def _register_ag_document_routes(self) -> None:
        """Documents de l'AG sous un bilan (ag_documents.py, spec §8.6)."""
        app, reports, documents = self.app, self.reports, self.ag_documents
        db_dep = Depends(get_db)
        member_dep = Depends(self.current_member)

        def season_of(db: Session, member: Member, report_id: int) -> Season:
            try:
                report = reports.get(db, member, report_id)
            except (ReportNotFoundError, PermissionError) as error:
                raise _http(error) from error
            season = next((s for s in self.seasons(db, member.org_id) if s.id == report["seasonId"]), None)
            if season is None:
                raise HTTPException(status_code=404, detail="Saison inconnue")
            return season

        @app.get("/finances/reports/{report_id}/documents")
        def list_documents(report_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Les documents possibles au niveau de l'organisation, et la
            Synthèse à l'écran."""
            season = season_of(db, member, report_id)
            level = documents.accounting.level(db, member.org_id)
            return {
                "level": level,
                "documents": documents.kinds(level),
                "synthese": documents.synthese(db, member, season),
                "closing": documents.closing_status(db, member.org_id, season),
            }

        def ag_call(action, *args):
            try:
                return action(*args)
            except (ValueError, PermissionError) as error:
                raise _http(error) from error

        @app.post("/finances/reports/{report_id}/close")
        def close_season(report_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Clôture de la saison du bilan (§8.7) : résultat dans 110, soldes
            reportés, saison verrouillée."""
            return {"closing": ag_call(documents.close, db, member, season_of(db, member, report_id))}

        @app.delete("/finances/reports/{report_id}/close")
        def reopen_season(report_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            return {"closing": ag_call(documents.reopen, db, member, season_of(db, member, report_id))}

        def season_by_id(db: Session, member: Member, season_id: int) -> Season:
            season = next((s for s in self.seasons(db, member.org_id) if s.id == season_id), None)
            if season is None:
                raise HTTPException(status_code=404, detail="Saison inconnue")
            return season

        @app.get("/finances/opening-balances/{season_id}")
        def get_opening(season_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Soldes de départ de la saison (§8.7) et vérification contre les relevés."""
            return ag_call(documents.opening, db, member, season_by_id(db, member, season_id))

        @app.put("/finances/opening-balances/{season_id}")
        def set_opening(season_id: int, data: OpeningRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
            return ag_call(documents.set_opening, db, member, season_by_id(db, member, season_id), data.accounts)

        @app.get("/finances/operations/{operation_id}/entries")
        def operation_entries(operation_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
            """Les écritures générées pour une opération (fiche, §8.4)."""
            try:
                sheet = documents.accounting.operation(db, member, operation_id)
            except (LookupError, PermissionError) as error:
                raise _http(error) from error
            return {"entries": documents.operation_entries(db, member, operation_id, sheet["date"])}

        written = self.written_reports

        if written is not None:

            @app.get("/finances/reports/{report_id}/rapport")
            def get_written(report_id: int, db: Session = db_dep, member: Member = member_dep) -> dict:
                """Le dernier rapport financier rédigé pour ce bilan (ou vide)."""
                season_of(db, member, report_id)
                return {"rapport": written.get(db, report_id), "models": reports.models()["models"], "defaultModel": reports.models()["defaultModel"]}

            @app.post("/finances/reports/{report_id}/rapport")
            async def write_report(report_id: int, data: WriteRequest, db: Session = db_dep, member: Member = member_dep) -> dict:
                """Fait rédiger le rapport (le modèle écrit le texte, l'appli
                place les chiffres)."""
                season = season_of(db, member, report_id)
                report = reports.get(db, member, report_id)
                analysis = (report.get("result") or {}).get("analysis", [])
                try:
                    return await run_in_threadpool(
                        written.write, db, member, report_id, season, data.prompt, data.model or reports.models()["defaultModel"], analysis
                    )
                except AnalysisError as exc:
                    raise HTTPException(status_code=502, detail=str(exc)) from exc

            @app.get("/finances/reports/{report_id}/rapport/download")
            def download_written(report_id: int, format: str = "docx", db: Session = db_dep, member: Member = member_dep) -> Response:
                season = season_of(db, member, report_id)
                try:
                    content, name, media = written.produce(db, member, report_id, season, format)
                except LookupError as exc:
                    raise HTTPException(status_code=404, detail=str(exc)) from exc
                except ValueError as exc:
                    raise HTTPException(status_code=400, detail=str(exc)) from exc
                return Response(content, media_type=media, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})

        @app.get("/finances/reports/{report_id}/documents/{kind}")
        def download_document(report_id: int, kind: str, db: Session = db_dep, member: Member = member_dep) -> Response:
            """Un document produit (xlsx ou pdf), aussi rangé dans Docs › Financier › AG."""
            season = season_of(db, member, report_id)
            try:
                content, name, media = documents.produce(db, member, season, kind)
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            return Response(content, media_type=media, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(name)}"})

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
