"""Module « finances » (spec/modules/financier.md), repris de Sambo Admin :
sous-module Comptes (relevés bancaires, historique), puis Bilan, Assemblée
générale et Prévisionnel.

Développé dans Contretemps pour devenir tel quel un module d'AppBase, comme
`notes_frais` : il ne connaît pas Contretemps, tout passe par les ports de
`ports.py`, branchés dans `finances_contretemps/adapter.py`.
"""

from .models import FinAccount, FinOperation, FinStatement
from .parser import StatementParseError, parse_statement
from .ports import Member, Season
from .receiver import FinancesReceiver
from .service import AccountNotFoundError, Finances

__all__ = [
    "AccountNotFoundError",
    "FinAccount",
    "FinOperation",
    "FinStatement",
    "Finances",
    "FinancesReceiver",
    "Member",
    "Season",
    "StatementParseError",
    "parse_statement",
]
