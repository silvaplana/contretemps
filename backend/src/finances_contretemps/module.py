"""Déclaration du module Financier pour Contretemps (spec/core.md §9 bis,
spec/modules/financier.md) : le module `finances`, repris de Sambo Admin,
relié ici aux saisons et aux fiches de Contretemps."""

import os
from pathlib import Path

from db import SessionLocal
from finances import Finances, FinancesReceiver, FinancialReports, Forecasts, GeneralAssemblies
from registry import Module, Right

from .actions import actions
from .adapter import FINANCES_ACCESS, membre_appelant, saisons_de_l_ecole


def mount(app, core) -> None:
    ressources = core.ressources_client

    def note_cost(poste):
        return lambda db, ecole_id, cout, detail: ressources.noter_ia(db, ecole_id, poste, cout, detail)

    finances_client = Finances()
    # Bilan : tableau calculé depuis l'historique des comptes, analyse par
    # l'API Claude (ANTHROPIC_API_KEY), coût noté à l'école comme celui de
    # l'assistant.
    finances_reports = FinancialReports(
        ledger=finances_client.get_ledger,
        seasons=saisons_de_l_ecole,
        session_factory=SessionLocal,
        note_cost=note_cost("bilan_financier"),
    )
    # Assemblée générale : base du PowerPoint de l'AG écrite à partir du
    # bilan, PowerPoint gardés sur le disque (volume Docker), images des
    # diapos par LibreOffice Impress s'il est installé.
    finances_assemblies = GeneralAssemblies(
        storage_dir=Path(os.environ.get("FINANCES_DIR", "./data/finances")) / "assemblies",
        seasons=saisons_de_l_ecole,
        reports=finances_reports.list,
        report=finances_reports.get,
        session_factory=SessionLocal,
        note_cost=note_cost("assemblee_generale"),
    )
    # Prévisionnel : formule écrite par l'API Claude d'après l'historique
    # des comptes, exécutée à part (sandbox.py), rejouée à chaque curseur.
    finances_forecasts = Forecasts(
        ledger=finances_client.get_ledger,
        seasons=saisons_de_l_ecole,
        session_factory=SessionLocal,
        note_cost=note_cost("previsionnel"),
    )
    FinancesReceiver(
        client=finances_client,
        app=app,
        current_member=membre_appelant,
        seasons=saisons_de_l_ecole,
        reports=finances_reports,
        assemblies=finances_assemblies,
        forecasts=finances_forecasts,
    )
    core.finances_client = finances_client
    core.finances_reports = finances_reports
    core.finances_assemblies = finances_assemblies
    core.finances_forecasts = finances_forecasts


MODULE = Module(
    key="finances", label="Financier", mount=mount,
    rights=(Right(FINANCES_ACCESS, "Accès au Financier"),),
    actions=lambda core: actions(
        core.finances_reports, core.finances_assemblies, core.finances_forecasts,
        core.finances_client, saisons_de_l_ecole,
    ),
)
