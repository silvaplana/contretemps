"""Prévisionnels d'une saison (sous-module Prévisionnel, spec/modules/
financier.md §6), repris de Sambo Admin (forecasts/).

Un prévisionnel est un calcul enregistré (table fin_forecasts) : nom,
saison, état (brouillon, validé, officiel ; plusieurs par saison), date de
départ (vide : dernier jour connu des comptes), consignes données au
modèle, dernier modèle utilisé, coût cumulé, résultat du dernier calcul et
dernière position des curseurs.

Exécuter un calcul (voir run) :
1. l'appli prépare les données (voir forecast_data.py) : solde réel à la
   date de départ, moyennes mensuelles par catégorie ;
2. le modèle (voir forecast_ai.py) écrit une formule Python
   prevoir(donnees, p) et déclare ses paramètres (curseurs) ;
3. l'appli vérifie et exécute la formule à part (voir sandbox.py).
Ensuite, bouger un curseur rejoue la formule (voir set_params), sans
rappeler le modèle. Le calcul tourne en arrière-plan ; son coût est noté à
l'organisation (port `note_cost`, comme le bilan).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import forecast_data, forecast_exports
from .ai import DEFAULT_MODEL, MODELS, AnalysisError
from .forecast_ai import Coder, Formula, defaults
from .models import STATES, FinForecast
from .ports import Member, Season
from .sandbox import FormulaError
from .sandbox import run as run_formula

# Calcul « en cours » depuis plus longtemps : le serveur a redémarré entre-temps.
RUN_TIMEOUT = timedelta(minutes=20)


class ForecastError(ValueError):
    """Données de prévisionnel invalides (message affichable tel quel)."""


class ForecastNotFoundError(LookupError):
    pass


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _check(member: Member) -> None:
    if not member.keeps_accounts:
        raise PermissionError("Réservé aux trésoriers")


def _season_dict(season: Season) -> dict:
    """Fiche de saison attendue par forecast_data et forecast_exports."""
    return {"id": season.id, "name": season.name, "startDate": season.start_date, "endDate": season.end_date}


class Forecasts:
    def __init__(
        self,
        ledger: Callable[[Session, Member], dict],
        seasons: Callable[[Session, int], list[Season]],
        session_factory: Callable[[], Session] | None = None,
        note_cost: Callable[[Session, int, float, str], None] | None = None,
        today: Callable[[], date] = date.today,
        coder: Coder | None = None,
        background: bool = True,
    ) -> None:
        """ledger(db, member) : historique des comptes (Finances.get_ledger) ;
        seasons(db, org_id) : les saisons, la plus ancienne en premier ;
        session_factory : session de base pour le calcul en arrière-plan ;
        note_cost(db, org_id, dollars, detail) : coût noté à l'organisation.
        background=False : calcul exécuté directement (tests)."""
        self.ledger = ledger
        self.seasons = seasons
        self.session_factory = session_factory
        self.note_cost = note_cost
        self.today = today
        self.coder = coder or Coder()
        self.background = background

    # ----- lecture -----

    @staticmethod
    def models() -> dict:
        return {
            "models": [{"id": key, "label": spec["label"]} for key, spec in MODELS.items()],
            "defaultModel": DEFAULT_MODEL,
            "states": [{"id": key, "label": label} for key, label in STATES.items()],
        }

    @staticmethod
    def counts(db: Session, member: Member) -> dict[int, int]:
        """Nombre de prévisionnels par saison (affiché dans le choix de la saison)."""
        _check(member)
        rows = db.execute(
            select(FinForecast.season_id, func.count()).where(FinForecast.org_id == member.org_id).group_by(FinForecast.season_id)
        ).all()
        return {season_id: count for season_id, count in rows}

    def list(self, db: Session, member: Member, season_id: int) -> list[dict]:
        _check(member)
        rows = db.scalars(
            select(FinForecast)
            .where(FinForecast.org_id == member.org_id, FinForecast.season_id == season_id)
            .order_by(FinForecast.id.desc())
        )
        return [self._summary(row) for row in rows]

    def get(self, db: Session, member: Member, forecast_id: int) -> dict:
        row = self._row(db, member, forecast_id)
        return {
            **self._summary(row),
            "prompt": row.prompt,
            "result": json.loads(row.result) if row.result else None,
            # Dernière position des curseurs.
            "params": json.loads(row.params) if row.params else {},
        }

    @staticmethod
    def _row(db: Session, member: Member, forecast_id: int) -> FinForecast:
        _check(member)
        row = db.get(FinForecast, forecast_id)
        if row is None or row.org_id != member.org_id:
            raise ForecastNotFoundError(forecast_id)
        return row

    @staticmethod
    def _summary(row: FinForecast) -> dict:
        status, error = row.status, row.error
        if status == "running" and row.run_started_at is not None and row.run_started_at < _now() - RUN_TIMEOUT:
            status, error = "error", "Calcul interrompu (serveur redémarré) : relancez-le."
        result = json.loads(row.result) if row.result else None
        return {
            "id": row.id,
            "seasonId": row.season_id,
            "name": row.name,
            "state": row.state,
            "startDate": row.start_date,
            "model": row.model,
            "modelLabel": MODELS.get(row.model, {}).get("label", row.model),
            "aiCostUsd": row.ai_cost_usd,
            "status": status,
            "error": error,
            "hasResult": result is not None,
            # Solde prévu en fin de saison, avec les curseurs enregistrés.
            "endBalance": result["points"][-1]["solde"] if result and result.get("points") else None,
            "updatedAt": row.updated_at.isoformat(timespec="seconds"),
        }

    # ----- écriture -----

    def create(self, db: Session, member: Member, data: dict) -> dict:
        _check(member)
        season = self._season(db, member.org_id, data.get("seasonId"))
        name, state, prompt, model, start = self._validate(data, season)
        row = FinForecast(
            org_id=member.org_id, season_id=season.id, name=name, state=state, prompt=prompt, model=model, start_date=start
        )
        db.add(row)
        db.commit()
        return self.get(db, member, row.id)

    def update(self, db: Session, member: Member, forecast_id: int, data: dict) -> dict:
        row = self._row(db, member, forecast_id)
        season = self._season(db, member.org_id, row.season_id)
        row.name, row.state, row.prompt, row.model, row.start_date = self._validate(data, season)
        row.updated_at = _now()
        db.commit()
        return self.get(db, member, forecast_id)

    def delete(self, db: Session, member: Member, forecast_id: int) -> None:
        db.delete(self._row(db, member, forecast_id))
        db.commit()

    def _season(self, db: Session, org_id: int, season_id) -> Season:
        season = next((s for s in self.seasons(db, org_id) if s.id == season_id), None)
        if season is None:
            raise ForecastError("Saison inconnue")
        return season

    @staticmethod
    def _validate(data: dict, season: Season) -> tuple[str, str, str, str, str | None]:
        name = (data.get("name") or "").strip()
        if not name:
            raise ForecastError("Le nom du prévisionnel est obligatoire")
        state = data.get("state") or "brouillon"
        if state not in STATES:
            raise ForecastError(f"État inconnu : {state}")
        model = data.get("model") or DEFAULT_MODEL
        if model not in MODELS:
            raise ForecastError(f"Modèle inconnu : {model}")
        start = data.get("startDate") or None
        if start is not None:
            try:
                date.fromisoformat(start)
            except ValueError as exc:
                raise ForecastError(f"Date de départ invalide : {start}") from exc
            if not season.start_date <= start < season.end_date:
                raise ForecastError("La date de départ doit être dans la saison, avant son dernier jour")
        return name, state, (data.get("prompt") or "").strip(), model, start

    # ----- calcul -----

    def start_date(self, ledger: dict, season: Season, start: str | None) -> str:
        """Date de départ effective : celle du prévisionnel, sinon le dernier
        jour connu des comptes (au plus aujourd'hui), ramenée dans la saison."""
        if start:
            return start
        known = forecast_data.last_known_day(ledger) or self.today().isoformat()
        day = min(known, self.today().isoformat())
        if day >= season.end_date:
            raise ForecastError("Saison terminée : choisissez une date de départ pour tester le prévisionnel")
        return max(day, season.start_date)

    def run(self, db: Session, member: Member, forecast_id: int, data: dict) -> dict:
        """Enregistre le formulaire, puis lance le calcul (en arrière-plan).
        Retourne le prévisionnel, "status": "running"."""
        row = self._row(db, member, forecast_id)
        if self._summary(row)["status"] == "running":
            raise ForecastError("Un calcul est déjà en cours pour ce prévisionnel")
        season = self._season(db, member.org_id, row.season_id)
        current = {"name": row.name, "state": row.state, "prompt": row.prompt, "model": row.model, "startDate": row.start_date}
        name, state, prompt, model, start = self._validate({**current, **{k: v for k, v in data.items() if v is not None}}, season)
        self.start_date(self.ledger(db, member), season, start)  # saison terminée sans date : refusé tout de suite
        row.name, row.state, row.prompt, row.model, row.start_date = name, state, prompt, model, start
        row.status, row.error, row.run_started_at, row.updated_at = "running", None, _now(), _now()
        db.commit()
        if self.background and self.session_factory is not None:
            threading.Thread(target=self._execute_in_own_session, args=(member, forecast_id), daemon=True).start()
        else:
            self._execute(db, member, forecast_id)
        return self.get(db, member, forecast_id)

    def _execute_in_own_session(self, member: Member, forecast_id: int) -> None:
        db = self.session_factory()
        try:
            self._execute(db, member, forecast_id)
        finally:
            db.close()

    def _execute(self, db: Session, member: Member, forecast_id: int) -> None:
        row = db.get(FinForecast, forecast_id)
        cost = 0.0
        try:
            season = self._season(db, member.org_id, row.season_id)
            ledger = self.ledger(db, member)
            start = self.start_date(ledger, season, row.start_date)
            # Pas d'inscrits ni d'échéances de paiement : l'appli hôte ne les
            # fournit pas (adherents null, le modèle fait sans).
            data = forecast_data.build(ledger, _season_dict(season), start, None)
            if not data["semaines"]:
                raise ForecastError("Rien à prévoir : la date de départ est le dernier jour de la saison")
            formula: Formula = self.coder.write(row.model, data, row.prompt)
            cost = formula.cost
            # Curseurs : position enregistrée si le paramètre existe toujours
            # (et reste dans ses bornes), sinon sa valeur par défaut.
            saved = json.loads(row.params) if row.params else {}
            params = {
                p["name"]: min(p["max"], max(p["min"], float(saved[p["name"]]))) if p["name"] in saved else p["default"]
                for p in formula.parameters
            }
            balances = formula.balances if params == defaults(formula.parameters) else run_formula(formula.code, data, params)
            result = {
                "code": formula.code,
                "explanation": formula.explanation,
                "parameters": formula.parameters,
                "data": data,
                "points": self._points(data, balances),
                "seasonName": season.name,
                "model": formula.model,
                "modelLabel": MODELS[formula.model]["label"],
                "servedBy": formula.served_by,
                "costUsd": cost,
                "generatedAt": _now().isoformat(timespec="seconds"),
            }
            row.result, row.params = json.dumps(result, ensure_ascii=False), json.dumps(params)
            row.status, row.error = "idle", None
        except Exception as exc:  # noqa: BLE001 - tout échec doit sortir le prévisionnel de l'état « en cours »
            cost = exc.cost if isinstance(exc, AnalysisError) else cost
            known = isinstance(exc, (AnalysisError, ForecastError, FormulaError, ValueError))
            row.status = "error"
            row.error = str(exc) if known else f"Le calcul a échoué : {exc}"
        row.ai_cost_usd += cost
        row.updated_at = _now()
        db.commit()
        if cost and self.note_cost is not None:
            self.note_cost(db, member.org_id, cost, f"Prévisionnel {row.name}")

    @staticmethod
    def _points(data: dict, balances: list[float]) -> list[dict]:
        """Courbe prévue : le solde réel à la date de départ puis une valeur
        par semaine."""
        return [{"date": data["dateDepart"], "solde": data["soldeDepart"]}] + [
            {"date": week["date"], "solde": value} for week, value in zip(data["semaines"], balances)
        ]

    def set_params(self, db: Session, member: Member, forecast_id: int, values: dict) -> dict:
        """Rejoue la formule avec de nouvelles positions des curseurs et les
        enregistre. Retourne le prévisionnel complet."""
        row = self._row(db, member, forecast_id)
        if not row.result:
            raise ForecastError("Ce prévisionnel n'a pas encore été calculé")
        result = json.loads(row.result)
        params = {}
        for p in result["parameters"]:
            value = values.get(p["name"], p["default"])
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ForecastError(f"Valeur invalide pour {p['label']}")
            params[p["name"]] = min(p["max"], max(p["min"], float(value)))
        balances = run_formula(result["code"], result["data"], params)
        result["points"] = self._points(result["data"], balances)
        row.result, row.params, row.updated_at = json.dumps(result, ensure_ascii=False), json.dumps(params), _now()
        db.commit()
        return self.get(db, member, forecast_id)

    def export(
        self, db: Session, member: Member, forecast_id: int, file_format: str, season_ids: list[int] | None = None
    ) -> tuple[bytes, str, str]:
        """Résultat en image (png) ou PDF : (contenu, type, nom du fichier).
        season_ids : saisons superposées pour comparer, celles choisies à
        l'écran (None : la saison précédente)."""
        forecast = self.get(db, member, forecast_id)
        if forecast["result"] is None:
            raise ForecastError("Ce prévisionnel n'a pas encore été calculé")
        if file_format not in ("png", "pdf"):
            raise ForecastError("Format inconnu (png ou pdf)")
        seasons = self.seasons(db, member.org_id)
        index = next((i for i, s in enumerate(seasons) if s.id == forecast["seasonId"]), None)
        earlier = seasons[:index] if index else []
        if season_ids is None:
            season_ids = [s.id for s in earlier[-1:]]
        # Seules les saisons d'avant se comparent ; couleur selon le rang de
        # la saison, comme à l'écran.
        compared = [
            {**_season_dict(s), "color": forecast_exports.SEASON_COLORS[i % len(forecast_exports.SEASON_COLORS)]}
            for i, s in enumerate(earlier)
            if s.id in season_ids
        ]
        ledger = self.ledger(db, member)
        name = f"previsionnel-{forecast['result']['seasonName']}-{forecast['id']}.{file_format}"
        if file_format == "png":
            return forecast_exports.to_png(forecast_exports.chart_svg(forecast, ledger, compared)), "image/png", name
        chart = forecast_exports.to_png(forecast_exports.chart_svg(forecast, ledger, compared, header=False))
        return forecast_exports.to_pdf(forecast, chart), "application/pdf", name
