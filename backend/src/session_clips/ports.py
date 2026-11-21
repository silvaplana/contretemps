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


class Notifier(Protocol):
    def notify(self, db: Session, org_id: int, person_ids: list[int], title: str, body: str) -> None:
        """Une notification sur le téléphone de chaque personne (Seb, 17/11 :
        un nouveau combat validé). Ne fait jamais échouer l'appelant."""


class Directory(Protocol):
    def people(self, db: Session, org_id: int) -> list[Person]:
        """Les membres actuels de l'organisation, pour nommer un combattant."""

    def names(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, str]:
        """Le nom de chaque personne, même partie depuis."""

    def full_name(self, db: Session, org_id: int, person_id: int) -> str | None:
        """Prénom et nom en entier, pour l'annonce du vainqueur ; rien si la
        personne n'est pas de l'organisation."""
