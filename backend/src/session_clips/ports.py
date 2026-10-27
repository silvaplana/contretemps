"""Ce que le module session_clips attend de l'appli hôte (branché dans
session_clips_contretemps/adapter.py pour Contretemps)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Member:
    """Qui appelle : sa personne (la même toutes saisons), son organisation,
    et s'il est coach (filme, voit tout, corrige)."""

    person_id: int
    org_id: int
    name: str
    is_coach: bool = False


@dataclass(frozen=True)
class Person:
    id: int
    name: str


class Directory(Protocol):
    def people(self, db: Session, org_id: int) -> list[Person]:
        """Les membres actuels de l'organisation, pour nommer un combattant."""

    def names(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, str]:
        """Le nom de chaque personne, même partie depuis."""
