"""Module FFST (spec/modules/ffst.md): a school affiliated to the FFST
requests its members' licences from the app. Step 1: the club login, the
reading of the three lists of the FFST site, the FFST tab and the « Statut
FFST » column."""

from .models import FfstConnection, FfstSnapshot

__all__ = ["FfstConnection", "FfstSnapshot"]
