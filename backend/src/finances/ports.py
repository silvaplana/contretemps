"""Ce que le module finances attend de l'appli hôte (branché dans
finances_contretemps/adapter.py pour Contretemps)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Member:
    """Qui appelle : sa personne, son organisation, et s'il tient les comptes
    (trésorier, ou Super User qui a choisi une organisation)."""

    person_id: int
    org_id: int
    name: str
    is_treasurer: bool = False
    is_superuser: bool = False

    @property
    def keeps_accounts(self) -> bool:
        return self.is_treasurer or self.is_superuser


@dataclass(frozen=True)
class Season:
    """Une saison de l'organisation, pour la période « Saisons » du
    graphique (dates ISO)."""

    id: int
    name: str
    start_date: str
    end_date: str
    current: bool = False
