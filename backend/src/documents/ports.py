"""Ce dont le module a besoin de l'appli hôte, sans la connaître (plan §1
règle 2). Contretemps les branche dans documents_contretemps/adapter.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from sqlalchemy.orm import Session


@dataclass(frozen=True)
class Member:
    """La personne qui appelle, vue par le module.

    `person_id` reste le même d'une saison à l'autre (dans Contretemps, les
    comptes sont recopiés à chaque saison : c'est l'id du premier compte de
    la chaîne, plan §1 règle 6). `groups` contient toutes les clés de
    groupe dont elle fait partie, rôles compris ("role:admin", "course:12").
    """

    person_id: int
    org_id: int
    display_name: str
    is_admin: bool = False
    is_superuser: bool = False
    # Peut avoir un espace Personnel (pas les élèves, Seb 15 octobre).
    has_personal_space: bool = False
    groups: frozenset[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class Principal:
    """Une personne ou un groupe, tel qu'affiché dans « Qui a accès ? »."""

    type: str  # "member" | "group"
    id: str
    label: str
    detail: str = ""


@dataclass(frozen=True)
class Period:
    id: int
    name: str
    is_current: bool


class Directory(Protocol):
    """Personnes et groupes de l'organisation."""

    def describe(self, db: Session, org_id: int, principals: list[tuple[str, str]]) -> dict[tuple[str, str], Principal]:
        """Libellés des personnes et groupes donnés (type, id)."""

    def search(self, db: Session, org_id: int, query: str, limit: int = 20) -> list[Principal]:
        """Groupes puis personnes dont le nom contient `query` (tous si vide)."""

    def person_names(self, db: Session, org_id: int, person_ids: set[int]) -> dict[int, str]:
        """Nom affiché de chaque personne (auteurs, historique)."""


class Periods(Protocol):
    """Saisons (ou exercices) de l'organisation."""

    def list(self, db: Session, org_id: int) -> list[Period]:
        """Toutes les périodes, de la plus ancienne à la plus récente."""


# Rôles qui ont l'Écriture dans l'espace Privé par défaut (§4.4 règle 4 :
# admins et professeurs, Seb 15 octobre). L'appli hôte peut en donner
# d'autres : ce sont des clés de groupe.
DEFAULT_PRIVATE_EDITORS = ("role:admin", "role:professeur")
