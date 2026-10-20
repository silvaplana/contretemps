"""Module « finances » (spec/modules/financier.md), repris de Sambo Admin :
sous-modules Comptes (relevés bancaires, historique), Bilan, Assemblée
générale (PowerPoint), puis Prévisionnel.

Développé dans Contretemps pour devenir tel quel un module d'AppBase, comme
`notes_frais` : il ne connaît pas Contretemps, tout passe par les ports de
`ports.py`, branchés dans `finances_contretemps/adapter.py`.
"""

from .assemblies import AssemblyError, AssemblyNotFoundError, GeneralAssemblies
from .models import FinAccount, FinAssembly, FinAssemblyFile, FinOperation, FinReport, FinStatement
from .parser import StatementParseError, parse_statement
from .ports import Member, Season
from .receiver import FinancesReceiver
from .reports import FinancialReports, ReportError, ReportNotFoundError
from .service import AccountNotFoundError, Finances

__all__ = [
    "AccountNotFoundError",
    "AssemblyError",
    "AssemblyNotFoundError",
    "FinAccount",
    "FinAssembly",
    "FinAssemblyFile",
    "FinOperation",
    "FinReport",
    "FinancialReports",
    "FinStatement",
    "Finances",
    "GeneralAssemblies",
    "FinancesReceiver",
    "Member",
    "ReportError",
    "ReportNotFoundError",
    "Season",
    "StatementParseError",
    "parse_statement",
]
