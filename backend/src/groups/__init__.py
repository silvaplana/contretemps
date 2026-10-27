"""Groupes du core (spec/core.md §5). Pour l'instant, seulement le bureau."""

from . import board
from .models import Group, GroupMember

__all__ = ["Group", "GroupMember", "board"]
