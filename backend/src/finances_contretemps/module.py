"""Déclaration du module Financier pour Contretemps (spec/core.md §9 bis,
spec/modules/financier.md) : le module `finances`, repris de Sambo Admin,
relié ici aux saisons et aux fiches de Contretemps."""

import os
from pathlib import Path

from db import SessionLocal
from finances import Accounting, Finances, FinancesReceiver, FinancialReports, Forecasts, GeneralAssemblies
from finances.bank import Bank
from finances.enablebanking import EnableBankingClient
from registry import Module, Right
from securite.chiffrement import chiffrer, dechiffrer

from .actions import actions
from .adapter import FINANCES_ACCESS, adresse_ecole, membre_appelant, pieces_des_operations, saisons_de_l_ecole


def _client_bancaire() -> EnableBankingClient | None:
    """Connexion bancaire (Enable Banking), si le serveur a l'identifiant de
    l'application, sa clé privée (fichier monté en lecture seule, jamais
    dans le dépôt ni dans une variable) et l'adresse de retour. Voir
    DEPLOY.md §4."""
    app_id = os.environ.get("ENABLE_BANKING_APP_ID", "").strip()
    cle = os.environ.get("ENABLE_BANKING_KEY_PATH", "/run/secrets/enable_banking.pem")
    retour = os.environ.get("ENABLE_BANKING_REDIRECT_URL", "").strip()
    if not app_id or not retour or not Path(cle).is_file():
        return None
    return EnableBankingClient(app_id=app_id, private_key_path=cle, redirect_url=retour)


def mount(app, core) -> None:
    ressources = core.ressources_client

    def note_cost(poste):
        return lambda db, ecole_id, cout, detail: ressources.noter_ia(db, ecole_id, poste, cout, detail)

    # Comptabilité (spec §8) : plan comptable, compte sur chaque ligne,
    # caisse ; la pièce d'une ligne vient des dépenses du module Notes de frais.
    finances_accounting = Accounting(pieces=pieces_des_operations)
    finances_client = Finances(accounting=finances_accounting)
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
    finances_bank = Bank(client=_client_bancaire(), finances=finances_client, encrypt=chiffrer, decrypt=dechiffrer)
    FinancesReceiver(
        client=finances_client,
        app=app,
        current_member=membre_appelant,
        seasons=saisons_de_l_ecole,
        reports=finances_reports,
        assemblies=finances_assemblies,
        forecasts=finances_forecasts,
        bank=finances_bank,
        org_url=adresse_ecole,
        accounting=finances_accounting,
    )
    core.finances_client = finances_client
    core.finances_accounting = finances_accounting
    core.finances_bank = finances_bank
    core.finances_reports = finances_reports
    core.finances_assemblies = finances_assemblies
    core.finances_forecasts = finances_forecasts


MODULE = Module(
    key="finances", label="Financier", mount=mount, requires=("seasons",),
    rights=(Right(FINANCES_ACCESS, "Accès au Financier"),),
    actions=lambda core: actions(
        core.finances_reports, core.finances_assemblies, core.finances_forecasts,
        core.finances_client, saisons_de_l_ecole,
    ),
)
