"""Déclaration du module Financier pour Contretemps (spec/core.md §9 bis,
spec/modules/financier.md) : le module `finances`, repris de Sambo Admin,
relié ici aux saisons et aux fiches de Contretemps."""

import os
from pathlib import Path

from db import SessionLocal
from finances import (
    Accounting,
    AgDocuments,
    AgPorts,
    Finances,
    FinancesReceiver,
    FinancialReports,
    Forecasts,
    GeneralAssemblies,
    WrittenReports,
)
from finances.bank import Bank
from finances.enablebanking import EnableBankingClient
from registry import Module, Right
from securite.chiffrement import chiffrer, dechiffrer

from .actions import actions
from .adapter import (
    FINANCES_ACCESS,
    adresse_ecole,
    honoraires_payes,
    membre_appelant,
    nom_ecole,
    pieces_des_operations,
    pieces_a_payer,
    dossier_ag,
    ranger_dans_docs,
    saisons_de_l_ecole,
)


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
    # Documents de l'AG (spec §8.6) : calculés depuis les lignes, rangés dans
    # Docs › Financier › AG par le module documents.
    finances_ag_documents = AgDocuments(
        ledger=finances_client.get_ledger,
        accounting=finances_accounting,
        seasons=saisons_de_l_ecole,
        ports=AgPorts(
            unpaid=pieces_a_payer,
            fees=honoraires_payes,
            store=ranger_dans_docs(core.documents_client),
            folder=dossier_ag(core.documents_client),
            org_name=nom_ecole,
        ),
    )
    # Rapport financier (spec §8.6) : le modèle rédige, l'appli place les chiffres.
    finances_written = WrittenReports(
        synthese=finances_ag_documents.synthese,
        seasons=saisons_de_l_ecole,
        note_cost=note_cost("rapport_financier"),
        org_name=nom_ecole,
        store=ranger_dans_docs(core.documents_client),
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
        ag_documents=finances_ag_documents,
        written_reports=finances_written,
    )
    core.finances_client = finances_client
    core.finances_ag_documents = finances_ag_documents
    core.finances_accounting = finances_accounting
    core.finances_bank = finances_bank
    core.finances_reports = finances_reports
    core.finances_assemblies = finances_assemblies
    core.finances_forecasts = finances_forecasts


MODULE = Module(
    key="finances", label="Financier", mount=mount, requires=("seasons", "documents", "expense_notes"),
    rights=(Right(FINANCES_ACCESS, "Accès au Financier"),),
    actions=lambda core: actions(
        core.finances_reports, core.finances_assemblies, core.finances_forecasts,
        core.finances_client, saisons_de_l_ecole,
    ),
)
