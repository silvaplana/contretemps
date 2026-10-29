"""Tables du sous-module Comptes du module finances (spec/modules/
financier.md §3) : comptes bancaires, relevés importés, opérations.

Comme les autres modules : aucune clé étrangère vers l'appli hôte, `org_id`
est un simple entier fourni par le port (voir ports.py). Pas de `saison_id`,
un historique bancaire traverse les saisons.

Montants en centimes entiers (un relevé doit tomber juste au centime).
"""

from __future__ import annotations

import datetime as dt
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Origine d'une opération : un relevé importé, ou la connexion bancaire
# (bank.py), dont les opérations sont provisoires jusqu'au relevé.
SOURCE_STATEMENT = "releve"
SOURCE_BANK = "banque"


class FinAccount(Base):
    __tablename__ = "fin_accounts"
    __table_args__ = (UniqueConstraint("org_id", "number", name="uq_fin_accounts_org_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(34), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # "checking" (compte courant) ou "savings" (livret).
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    # Connexion bancaire (bank.py) : identifiant du compte chez Enable
    # Banking, et dernier solde lu à la banque (centimes) avec sa date. Ce
    # solde sert de point de départ tant que le compte n'a aucun relevé.
    bank_uid: Mapped[str | None] = mapped_column(String(100), nullable=True)
    bank_balance: Mapped[int | None] = mapped_column(Integer, nullable=True)
    bank_balance_date: Mapped[dt.date | None] = mapped_column(Date, nullable=True)


class FinBankConnection(Base):
    """La connexion bancaire d'une organisation (une seule par organisation) :
    banque choisie, session Enable Banking (chiffrée), comptes que la banque
    a autorisés et ceux qu'on suit, expiration du consentement (180 jours au
    plus), dernière lecture. `state` : la connexion en cours, le temps que la
    personne passe par sa banque."""

    __tablename__ = "fin_bank_connections"
    __table_args__ = (UniqueConstraint("org_id", name="uq_fin_bank_connections_org"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    bank: Mapped[str] = mapped_column(String(120), nullable=False)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="FR")
    # "personal" ou "business" (espace particuliers ou professionnels).
    psu_type: Mapped[str] = mapped_column(String(20), nullable=False, default="personal")
    session_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # [{"uid", "iban", "name", "product", "followed"}] : comptes autorisés.
    accounts: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    state: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    state_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # La banque demandée pendant la connexion en cours : {"bank", "psu_type",
    # "country"}, appliquée au retour (l'ancienne connexion vaut jusque-là).
    pending: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    connected_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    connected_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class FinStatement(Base):
    __tablename__ = "fin_statements"
    __table_args__ = (UniqueConstraint("account_id", "start_date", "end_date", name="uq_fin_statements_period"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("fin_accounts.id"), nullable=False, index=True)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    start_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_balance: Mapped[int] = mapped_column(Integer, nullable=False)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class FinOperation(Base):
    __tablename__ = "fin_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("fin_accounts.id"), nullable=False, index=True)
    statement_id: Mapped[int | None] = mapped_column(ForeignKey("fin_statements.id", ondelete="CASCADE"), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False, default=SOURCE_STATEMENT)
    # Rang dans le relevé : l'ordre de la banque pour un même jour.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    value_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    details: Mapped[str] = mapped_column(Text, nullable=False, default="")
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    # Opération jumelle d'un virement entre deux comptes de l'organisation.
    transfer_id: Mapped[int | None] = mapped_column(ForeignKey("fin_operations.id", ondelete="SET NULL"), nullable=True)


# États d'un bilan (un seul officiel par saison).
DRAFT = "brouillon"
VALIDATED = "valide"
OFFICIAL = "officiel"
STATES = {DRAFT: "Brouillon", VALIDATED: "Validé", OFFICIAL: "Officiel"}


class FinReport(Base):
    """Bilan financier d'une saison (sous-module Bilan, spec §4) : un calcul
    enregistré, avec son nom, son état, les consignes et le modèle du
    dernier calcul, son coût cumulé et son résultat (JSON : tableau +
    analyse). `season_id` est l'id d'une saison fournie par le port
    `seasons` (pas de clé étrangère : le module ne connaît pas la table)."""

    __tablename__ = "fin_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=DRAFT)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(40), nullable=False)
    # Coût cumulé des appels à l'IA, en dollars (affiché en euros, comme
    # l'assistant).
    ai_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    # "idle", "running" (calcul en cours depuis run_started_at) ou "error".
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="idle")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class FinAssembly(Base):
    """Assemblée générale d'une saison (sous-module Assemblée générale, spec
    §5) : la base du PowerPoint de l'AG, préparée à partir du bilan de la
    saison. Mêmes champs qu'un bilan (`FinReport`) ; ses PowerPoint sont dans
    `fin_assembly_files`, les fichiers sur le disque (voir assemblies.py)."""

    __tablename__ = "fin_assemblies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=DRAFT)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(40), nullable=False)
    ai_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Résultat du dernier calcul (JSON : bilan et modèle utilisés, diapos
    # écrites, résumé, montants à vérifier).
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="idle")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class FinAssemblyFile(Base):
    """Un PowerPoint d'une AG : `origin` "modele" (l'exemple dont on reprend
    la mise en page), "genere" (produit par le calcul) ou "envoye" (retouché
    par le trésorier et renvoyé). Un nouveau fichier remplace celui de la
    même origine ; `number` numérote les fichiers de l'AG (v<n>.pptx sur le
    disque). `source` : d'où vient le fichier, en clair."""

    __tablename__ = "fin_assembly_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    assembly_id: Mapped[int] = mapped_column(ForeignKey("fin_assemblies.id", ondelete="CASCADE"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    origin: Mapped[str] = mapped_column(String(10), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    source: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class FinForecast(Base):
    """Prévisionnel d'une saison (sous-module Prévisionnel, spec §6) : mêmes
    champs qu'un bilan (`FinReport`), plus la date de départ du calcul (vide :
    dernier jour connu des comptes) et la dernière position des curseurs
    (`params`, JSON). Le résultat (JSON) garde la formule, ses paramètres, ses
    données et la courbe (voir forecasts.py)."""

    __tablename__ = "fin_forecasts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default=DRAFT)
    start_date: Mapped[str | None] = mapped_column(String(10), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(40), nullable=False)
    ai_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    params: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="idle")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    run_started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


# ----- Comptabilité (spec §8) : plan comptable, compte sur chaque ligne,
# caisse, réglage Simple / Complet -----

# Natures d'un compte du plan.
EXPENSE = "depense"
INCOME = "recette"
THIRD_PARTY = "tiers"
SUSPENSE = "attente"
NATURES = (EXPENSE, INCOME, THIRD_PARTY, SUSPENSE)

# Niveaux du réglage (spec §8.1).
SIMPLE = "simple"
FULL = "complet"
LEVELS = (SIMPLE, FULL)


class FinSettings(Base):
    """Réglage du Financier par organisation : niveau Simple (trésorerie) ou
    Complet (partie double). Pas de ligne = Simple."""

    __tablename__ = "fin_settings"

    org_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    level: Mapped[str] = mapped_column(String(10), nullable=False, default=SIMPLE)


class FinChartAccount(Base):
    """Un compte du plan comptable de l'organisation (spec §8.2) : numéro du
    plan associatif, libellé de l'organisation, nature, événement (« gala »)
    pour le bloc de la Synthèse, mots-clés de proposition. Un compte utilisé
    ne se supprime pas : il passe inactif."""

    __tablename__ = "fin_chart_accounts"
    __table_args__ = (UniqueConstraint("org_id", "number", name="uq_fin_chart_accounts_org_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    number: Mapped[str] = mapped_column(String(10), nullable=False)
    label: Mapped[str] = mapped_column(String(80), nullable=False)
    nature: Mapped[str] = mapped_column(String(10), nullable=False)
    event: Mapped[str | None] = mapped_column(String(40), nullable=True)
    keywords: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class FinOperationAccount(Base):
    """Ventilation d'une opération bancaire sur les comptes du plan (spec
    §8.4) : une ligne par compte, les montants (centimes, signés comme
    l'opération) font le total de l'opération. Confirmée par le trésorier ;
    une proposition de l'appli n'est jamais écrite ici."""

    __tablename__ = "fin_operation_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    operation_id: Mapped[int] = mapped_column(ForeignKey("fin_operations.id", ondelete="CASCADE"), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("fin_chart_accounts.id"), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    confirmed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class FinCashLine(Base):
    """Une ligne de la caisse (spec §8.5), le seul compte saisi à la main :
    date, libellé, montant (centimes, négatif = sortie), compte du plan,
    pièce dans Docs. Un retrait au distributeur entre ici comme virement
    interne depuis l'opération bancaire `transfer_operation_id`."""

    __tablename__ = "fin_cash_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    date: Mapped[dt.date] = mapped_column(Date, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    account_id: Mapped[int | None] = mapped_column(ForeignKey("fin_chart_accounts.id"), nullable=True)
    transfer_operation_id: Mapped[int | None] = mapped_column(ForeignKey("fin_operations.id", ondelete="SET NULL"), nullable=True)
    doc_node_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)


class FinWrittenReport(Base):
    """Rapport financier rédigé pour un bilan (spec §8.6, written_report.py) :
    le texte final (JSON : introduction, recettes, dépenses, points,
    conclusion, alertes), les consignes et le modèle, le coût. Une ligne par
    rédaction ; la dernière fait foi."""

    __tablename__ = "fin_written_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("fin_reports.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model: Mapped[str] = mapped_column(String(40), nullable=False)
    served_by: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_now)
