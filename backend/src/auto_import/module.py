"""Déclaration du sous-module Import auto pièces du Financier
(spec/modules/import-auto-pieces.md). Éteint par défaut : allumé pour les
écoles de nature « combat » (ASC) par la migration. Contretemps ne change pas."""

import logging
import threading
import time

from registry import Module, guide_file

from .receiver import AutoImportReceiver
from .service import AutoImport

logger = logging.getLogger(__name__)


def _places(core):
    """Ce qu'on peut choisir comme source ou destination dans l'école."""

    def places(db, org_id: int) -> dict:
        from saisons.models import Saison
        from saisons.portee import toutes_saisons
        from sqlalchemy import select

        with toutes_saisons(db):
            saisons = list(db.scalars(select(Saison).where(Saison.ecole_id == org_id).order_by(Saison.date_debut.desc())))
        drives = getattr(core, "drives", None)
        mail = getattr(core, "mail_connection", None)
        return {
            "org_id": org_id,
            "seasons": [{"id": s.id, "name": s.nom} for s in saisons],
            "drives": [{"id": d.id, "name": d.name, "provider": d.provider} for d in drives.accounts(db, org_id)] if drives else [],
            "mail_boxes": [{"id": b.id, "name": b.name} for b in mail.accounts(db, org_id)] if mail else [],
        }

    return places


def mount(app, core) -> None:
    from notes_frais_contretemps.adapter import membre_appelant

    core.auto_import = AutoImport(
        notes=core.notes_frais_client, documents=core.documents_client, drives=getattr(core, "drives", None),
    )
    AutoImportReceiver(client=core.auto_import, app=app, membre_courant=membre_appelant, places=_places(core))


def start_loop(core, every_seconds: int = 300) -> None:
    """Regarde les imports dont l'heure est venue, toutes les 5 minutes.
    Lancé par `app.main.main()` seulement (jamais sous pytest)."""
    from db import SessionLocal

    def boucle():
        while True:
            try:
                with SessionLocal() as db:
                    core.auto_import.run_due(db)
            except Exception:
                logger.exception("Import auto pièces : passage impossible")
            time.sleep(every_seconds)

    threading.Thread(target=boucle, name="auto-import", daemon=True).start()


MODULE = Module(
    key="auto_import", label="Import auto pièces", mount=mount, requires=("expense_notes",),
    guide=guide_file(__file__), enabled_by_default=False,
)
