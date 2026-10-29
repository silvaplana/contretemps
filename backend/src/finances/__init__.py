"""Module « finances » (spec/modules/financier.md), repris de Sambo Admin :
sous-modules Comptes (relevés bancaires, historique), Bilan, Assemblée
générale (PowerPoint) et Prévisionnel.

Développé dans Contretemps pour devenir tel quel un module d'AppBase, comme
`notes_frais` : il ne connaît pas Contretemps, tout passe par les ports de
`ports.py`, branchés dans `finances_contretemps/adapter.py`.
"""

from .accounting import Accounting, AccountingError
from .ag_documents import AgDocuments, AgPorts
from .assemblies import AssemblyError, AssemblyNotFoundError, GeneralAssemblies
from .forecasts import ForecastError, ForecastNotFoundError, Forecasts
from .models import FinAccount, FinAssembly, FinAssemblyFile, FinForecast, FinOperation, FinReport, FinStatement
from .parser import StatementParseError, parse_statement
from .ports import Member, Season
from .receiver import FinancesReceiver
from .reports import FinancialReports, ReportError, ReportNotFoundError
from .service import AccountNotFoundError, Finances

__all__ = [
    "Accounting",
    "AccountingError",
    "AgDocuments",
    "AgPorts",
    "AccountNotFoundError",
    "AssemblyError",
    "AssemblyNotFoundError",
    "FinAccount",
    "FinAssembly",
    "FinAssemblyFile",
    "FinForecast",
    "FinOperation",
    "FinReport",
    "FinancialReports",
    "FinStatement",
    "Finances",
    "ForecastError",
    "ForecastNotFoundError",
    "Forecasts",
    "GeneralAssemblies",
    "FinancesReceiver",
    "Member",
    "ReportError",
    "ReportNotFoundError",
    "Season",
    "StatementParseError",
    "parse_statement",
]
