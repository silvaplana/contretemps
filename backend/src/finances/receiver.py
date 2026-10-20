"""Routes REST du sous-module Comptes (/finances/...). Qui appelle est
fourni par l'appli hôte (`current_member`, une dépendance FastAPI qui
renvoie un `Member`) ; les droits sont vérifiés par le service."""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.orm import Session

from db import get_db

from .ports import Member, Season
from .service import AccountNotFoundError, Finances


class FinancesReceiver:
    def __init__(
        self,
        client: Finances,
        app: FastAPI,
        current_member: Callable[..., Member],
        seasons: Callable[[Session, int], list[Season]],
    ) -> None:
        """seasons(db, org_id) : les saisons de l'organisation (période
        « Saisons » du graphique)."""
        self.client = client
        self.app = app
        self.current_member = current_member
        self.seasons = seasons
        self._register_routes()

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
