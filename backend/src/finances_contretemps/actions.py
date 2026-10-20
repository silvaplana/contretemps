"""Actions du Financier ouvertes à l'assistant (spec/modules/assistant-ia.md
§3, financier.md §7) : produire un bilan, une assemblée générale (PowerPoint)
ou un prévisionnel d'une saison, comme les boutons « Produire… » des
sous-onglets. Ici et pas dans `finances/` : il faut passer du compte de
Contretemps au `Member` du module.

Pas d'action pour Comptes : importer des relevés demande un fichier, que
l'assistant ne transmet pas aux actions.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from comptes import roles
from documents_contretemps.adapter import nom_affiche, personne_id
from finances import (
    AssemblyError,
    Finances,
    FinancialReports,
    ForecastError,
    Forecasts,
    GeneralAssemblies,
    ReportError,
)
from finances.models import STATES
from finances.ports import Member, Season

SEASON = Field(default=None, description="Nom de la saison (voir lister_saisons), ou null pour la saison en cours.")
STATE = Field(default="brouillon", description="État : brouillon, valide ou officiel.")
MODEL = Field(default=None, description="Modèle de langage (identifiant), ou null pour celui par défaut.")
INSTRUCTIONS = Field(default="", max_length=4000, description="Consignes du trésorier pour ce calcul, ou vide.")


class FinancialReport(BaseModel):
    season: str | None = SEASON
    title: str | None = Field(default=None, max_length=120, description="Nom du bilan, ou null pour « Bilan <saison> ».")
    instructions: str = INSTRUCTIONS
    state: str = STATE
    model: str | None = MODEL


class GeneralAssembly(BaseModel):
    season: str | None = SEASON
    title: str | None = Field(default=None, max_length=120, description="Nom de l'AG, ou null pour « AG <saison> ».")
    instructions: str = INSTRUCTIONS
    state: str = STATE
    model: str | None = MODEL
    template: str | None = Field(
        default=None,
        description="PowerPoint modèle : nom (ou saison) d'une AG déjà enregistrée dont on reprend le PowerPoint, "
        "« modèle général », ou null pour le choix par défaut (PowerPoint final de l'AG officielle de la saison "
        "précédente, sinon le modèle général).",
    )


class Forecast(BaseModel):
    season: str | None = SEASON
    title: str | None = Field(default=None, max_length=120, description="Nom du prévisionnel, ou null pour « Prévision <saison> ».")
    instructions: str = INSTRUCTIONS
    start_date: dt.date | None = Field(default=None, description="Date de départ AAAA-MM-JJ, ou null pour le dernier jour connu des comptes.")
    state: str = STATE
    model: str | None = MODEL


def _member(db: Session, compte, org_id: int) -> Member:
    member = Member(
        person_id=personne_id(db, compte), org_id=org_id, name=nom_affiche(compte),
        is_treasurer=roles.is_tresorier(compte), is_superuser=roles.is_superuser(compte),
    )
    if not member.keeps_accounts:
        raise PermissionError("réservé aux trésoriers")
    return member


def _season(seasons: list[Season], name: str | None) -> Season:
    if name is None:
        current = [s for s in seasons if s.current] or seasons[-1:]
        if not current:
            raise Refus("aucune saison : créez-la d'abord dans Admin › École")
        return current[0]
    wanted = " ".join(name.split()).casefold()
    found = [s for s in seasons if s.name.casefold() == wanted] or [s for s in seasons if wanted in s.name.casefold()]
    if len(found) != 1:
        raise Refus(f"saison « {name} » " + ("introuvable" if not found else "ambiguë") + ". Saisons : " + ", ".join(s.name for s in seasons))
    return found[0]


def _checked(options: dict, state: str, model: str | None) -> str:
    """État et modèle vérifiés ; rend le libellé du modèle."""
    if state not in STATES:
        raise Refus(f"état « {state} » inconnu : brouillon, valide ou officiel")
    model = model or options["defaultModel"]
    labels = {m["id"]: m["label"] for m in options["models"]}
    if model not in labels:
        raise Refus(f"modèle « {model} » inconnu : " + ", ".join(labels))
    return labels[model]


def actions(
    reports: FinancialReports,
    assemblies: GeneralAssemblies,
    forecasts: Forecasts,
    finances: Finances,
    seasons: Callable[[Session, int], list[Season]],
) -> list[Action]:
    def prepare_report(db: Session, compte, org_id: int, p: FinancialReport) -> Ligne:
        member = _member(db, compte, org_id)
        season = _season(seasons(db, org_id), p.season)
        label = _checked(reports.models(), p.state, p.model)
        data = {"seasonId": season.id, "name": p.title or f"Bilan {season.name}", "state": p.state, "prompt": p.instructions, "model": p.model}

        def faire(db: Session) -> None:
            try:
                created = reports.create(db, member, data)
                reports.run(db, member, created["id"], {})
            except ReportError as erreur:
                raise Refus(str(erreur)) from erreur

        return Ligne(
            f"Produire le bilan « {data['name']} » de la saison {season.name} ({STATES[p.state].lower()}, {label}) : "
            "tableau au centime depuis les relevés, puis analyse. Résultat dans Financier › Bilan.",
            faire,
        )

    def prepare_assembly(db: Session, compte, org_id: int, p: GeneralAssembly) -> Ligne:
        member = _member(db, compte, org_id)
        season = _season(seasons(db, org_id), p.season)
        options = assemblies.options(db, member, season.id)
        label = _checked(options, p.state, p.model)
        if options["report"] is None:
            raise Refus(f"aucun bilan calculé pour {season.name} : produisez-le d'abord (produce_financial_report)")
        source = None
        if p.template is not None:
            wanted = " ".join(p.template.split()).casefold()
            candidates = assemblies.model_sources(db, member)
            found = [s for s in candidates if wanted in s["label"].casefold()]
            if not found:
                raise Refus(f"PowerPoint « {p.template} » introuvable. Disponibles : " + (", ".join(s["label"] for s in candidates) or "aucun"))
            source = found[0]  # le plus récent d'abord (voir model_sources)
        elif options["template"] is None:
            raise Refus(
                f"pas de PowerPoint modèle pour {season.name} : indiquez l'AG dont reprendre le PowerPoint (template), "
                "ou envoyez un modèle général depuis Financier › AG › ⋯"
            )
        data = {"seasonId": season.id, "name": p.title or f"AG {season.name}", "state": p.state, "prompt": p.instructions, "model": p.model}

        def faire(db: Session) -> None:
            try:
                created = assemblies.create(db, member, data)
                if source is not None:
                    assemblies.copy_model(db, member, created["id"], source["assemblyId"], source["kind"])
                assemblies.run(db, member, created["id"], {})
            except AssemblyError as erreur:
                raise Refus(str(erreur)) from erreur

        template = source["label"] if source else options["template"]["name"]
        return Ligne(
            f"Produire le PowerPoint de l'AG « {data['name']} » de la saison {season.name} ({STATES[p.state].lower()}, {label}) "
            f"à partir du bilan « {options['report']['name']} » et de : {template}. Résultat dans Financier › AG.",
            faire,
        )

    def prepare_forecast(db: Session, compte, org_id: int, p: Forecast) -> Ligne:
        member = _member(db, compte, org_id)
        season = _season(seasons(db, org_id), p.season)
        label = _checked(forecasts.models(), p.state, p.model)
        start = p.start_date.isoformat() if p.start_date else None
        data = {
            "seasonId": season.id, "name": p.title or f"Prévision {season.name}", "state": p.state,
            "prompt": p.instructions, "model": p.model, "startDate": start,
        }
        try:
            forecasts._validate(data, season)
            effective = forecasts.start_date(finances.get_ledger(db, member), season, start)
        except ForecastError as erreur:
            raise Refus(str(erreur)) from erreur

        def faire(db: Session) -> None:
            try:
                created = forecasts.create(db, member, data)
                forecasts.run(db, member, created["id"], {})
            except ForecastError as erreur:
                raise Refus(str(erreur)) from erreur

        day = dt.date.fromisoformat(effective).strftime("%d/%m/%Y")
        return Ligne(
            f"Produire le prévisionnel « {data['name']} » de la saison {season.name} à partir du {day} "
            f"({STATES[p.state].lower()}, {label}) : formule et curseurs, solde prévu jusqu'à la fin de saison. "
            "Résultat dans Financier › Prévisionnel.",
            faire,
        )

    return [
        Action("produce_financial_report", "Bilan",
               "Produit le bilan financier d'une saison (Financier › Bilan) : compte d'exploitation calculé au centime "
               "depuis les relevés importés, puis analyse. Le calcul tourne en arrière-plan ; le résultat se lit dans l'appli.",
               FinancialReport, prepare_report, admin_only=False),
        Action("produce_general_assembly", "Assemblée générale",
               "Produit le PowerPoint de l'assemblée générale d'une saison (Financier › AG) à partir du bilan calculé de la "
               "saison et d'un PowerPoint modèle (par défaut celui de l'AG officielle de la saison précédente). "
               "Il faut un bilan calculé : sinon, produire d'abord le bilan.",
               GeneralAssembly, prepare_assembly, admin_only=False),
        Action("produce_forecast", "Prévisionnel",
               "Produit un prévisionnel d'une saison (Financier › Prévisionnel) : solde de tous les comptes prévu chaque "
               "semaine jusqu'à la fin de saison, avec des curseurs, d'après l'historique des comptes et les consignes.",
               Forecast, prepare_forecast, admin_only=False),
    ]
