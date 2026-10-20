"""Bilans financiers d'une saison (sous-module Bilan, spec/modules/
financier.md §4), repris de Sambo Admin (financialreports/).

Un bilan est un calcul enregistré (table fin_reports) : nom, saison, état
(brouillon, validé, officiel : un seul officiel par saison), consignes
données à l'IA, dernier modèle utilisé, coût cumulé et résultat du dernier
calcul.

Exécuter un calcul (voir run) :
1. l'appli calcule le compte d'exploitation de la saison au centime (voir
   report.py) et celui des saisons précédentes ;
2. l'IA (voir ai.py) classe les opérations « Autres » et écrit l'analyse ;
3. l'appli recalcule le tableau avec ce classement et vérifie que solde au
   début + recettes − dépenses = solde réel à la fin.
Le calcul tourne en arrière-plan (jusqu'à quelques minutes selon le
modèle) : l'écran relit le bilan jusqu'à ce qu'il soit terminé. Son coût
est noté à l'organisation (port `note_cost`, comme l'assistant).
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ai import DEFAULT_MODEL, MODELS, Analysis, AnalysisError, Analyst
from .categories import CATEGORY_NAMES, INTERNAL_TRANSFER, OTHER
from .models import OFFICIAL, STATES, VALIDATED, FinReport
from .ports import Member, Season
from .report import compute_report, unclassified

# Nombre de saisons précédentes comparées par l'IA.
PREVIOUS_SEASONS = 3
# Calcul « en cours » depuis plus longtemps : le serveur a redémarré entre-temps.
RUN_TIMEOUT = timedelta(minutes=20)


class ReportError(ValueError):
    """Données de bilan invalides (message affichable tel quel)."""


class ReportNotFoundError(LookupError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _check(member: Member) -> None:
    if not member.keeps_accounts:
        raise PermissionError("Réservé aux trésoriers")


class FinancialReports:
    def __init__(
        self,
        ledger: Callable[[Session, Member], dict],
        seasons: Callable[[Session, int], list[Season]],
        session_factory: Callable[[], Session] | None = None,
        note_cost: Callable[[Session, int, float, str], None] | None = None,
        analyst: Analyst | None = None,
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
        self.analyst = analyst or Analyst()
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
        """Nombre de bilans par saison (affiché dans le choix de la saison)."""
        _check(member)
        rows = db.execute(
            select(FinReport.season_id, func.count()).where(FinReport.org_id == member.org_id).group_by(FinReport.season_id)
        ).all()
        return {season_id: count for season_id, count in rows}

    def list(self, db: Session, member: Member, season_id: int) -> list[dict]:
        _check(member)
        rows = db.scalars(
            select(FinReport)
            .where(FinReport.org_id == member.org_id, FinReport.season_id == season_id)
            .order_by(FinReport.id.desc())
        )
        return [self._summary(row) for row in rows]

    def get(self, db: Session, member: Member, report_id: int) -> dict:
        row = self._row(db, member, report_id)
        return {**self._summary(row), "prompt": row.prompt, "result": json.loads(row.result) if row.result else None}

    @staticmethod
    def _row(db: Session, member: Member, report_id: int) -> FinReport:
        _check(member)
        row = db.get(FinReport, report_id)
        if row is None or row.org_id != member.org_id:
            raise ReportNotFoundError(report_id)
        return row

    @staticmethod
    def _summary(row: FinReport) -> dict:
        status, error = row.status, row.error
        if status == "running" and row.run_started_at is not None and row.run_started_at < _now() - RUN_TIMEOUT:
            status, error = "error", "Calcul interrompu (serveur redémarré) : relancez-le."
        return {
            "id": row.id,
            "seasonId": row.season_id,
            "name": row.name,
            "state": row.state,
            "model": row.model,
            "modelLabel": MODELS.get(row.model, {}).get("label", row.model),
            "aiCostUsd": row.ai_cost_usd,
            "status": status,
            "error": error,
            "hasResult": row.result is not None,
            "updatedAt": row.updated_at.isoformat(timespec="seconds"),
        }

    # ----- écriture -----

    def create(self, db: Session, member: Member, data: dict) -> dict:
        _check(member)
        season_id = data.get("seasonId")
        if not any(s.id == season_id for s in self.seasons(db, member.org_id)):
            raise ReportError("Saison inconnue")
        name, state, prompt, model = self._validate(data)
        if state == OFFICIAL:
            self._demote_official(db, member.org_id, season_id)
        row = FinReport(org_id=member.org_id, season_id=season_id, name=name, state=state, prompt=prompt, model=model)
        db.add(row)
        db.commit()
        return self.get(db, member, row.id)

    def update(self, db: Session, member: Member, report_id: int, data: dict) -> dict:
        row = self._row(db, member, report_id)
        name, state, prompt, model = self._validate(data)
        if state == OFFICIAL:
            self._demote_official(db, member.org_id, row.season_id, report_id)
        row.name, row.state, row.prompt, row.model, row.updated_at = name, state, prompt, model, _now()
        db.commit()
        return self.get(db, member, report_id)

    def delete(self, db: Session, member: Member, report_id: int) -> None:
        db.delete(self._row(db, member, report_id))
        db.commit()

    @staticmethod
    def _demote_official(db: Session, org_id: int, season_id: int, keep: int | None = None) -> None:
        """Un seul bilan officiel par saison : l'ancien repasse en validé."""
        for other in db.scalars(
            select(FinReport).where(FinReport.org_id == org_id, FinReport.season_id == season_id, FinReport.state == OFFICIAL)
        ):
            if other.id != keep:
                other.state = VALIDATED

    @staticmethod
    def _validate(data: dict) -> tuple[str, str, str, str]:
        name = (data.get("name") or "").strip()
        if not name:
            raise ReportError("Le nom du bilan est obligatoire")
        state = data.get("state") or "brouillon"
        if state not in STATES:
            raise ReportError(f"État inconnu : {state}")
        model = data.get("model") or DEFAULT_MODEL
        if model not in MODELS:
            raise ReportError(f"Modèle inconnu : {model}")
        return name, state, (data.get("prompt") or "").strip(), model

    # ----- calcul -----

    def run(self, db: Session, member: Member, report_id: int, data: dict) -> dict:
        """Enregistre les consignes et le modèle, puis lance le calcul (en
        arrière-plan). Retourne le bilan, "status": "running"."""
        row = self._row(db, member, report_id)
        if self._summary(row)["status"] == "running":
            raise ReportError("Un calcul est déjà en cours pour ce bilan")
        current = {"name": row.name, "state": row.state, "prompt": row.prompt, "model": row.model}
        name, state, prompt, model = self._validate({**current, **{k: v for k, v in data.items() if v is not None}})
        row.name, row.state, row.prompt, row.model = name, state, prompt, model
        row.status, row.error, row.run_started_at, row.updated_at = "running", None, _now(), _now()
        db.commit()
        if self.background and self.session_factory is not None:
            threading.Thread(target=self._execute_in_own_session, args=(member, report_id), daemon=True).start()
        else:
            self._execute(db, member, report_id)
        return self.get(db, member, report_id)

    def _execute_in_own_session(self, member: Member, report_id: int) -> None:
        db = self.session_factory()
        try:
            self._execute(db, member, report_id)
        finally:
            db.close()

    def _execute(self, db: Session, member: Member, report_id: int) -> None:
        row = db.get(FinReport, report_id)
        cost = 0.0
        try:
            seasons = self.seasons(db, member.org_id)
            index = next(i for i, s in enumerate(seasons) if s.id == row.season_id)
            season = seasons[index]
            previous = seasons[max(0, index - PREVIOUS_SEASONS) : index]
            ledger = self.ledger(db, member)
            base = compute_report(ledger, season.start_date, season.end_date)
            history = [self._season_summary(db, member.org_id, ledger, s) for s in previous]
            analysis: Analysis = self.analyst.analyze(row.model, self._ai_data(season, base, history), row.prompt)
            cost = analysis.cost
            # Seules les opérations « Autres » peuvent changer de catégorie.
            allowed = {op["id"] for op in unclassified(base)}
            classifications = {i: c for i, c in analysis.classifications.items() if i in allowed and c != INTERNAL_TRANSFER}
            table = compute_report(ledger, season.start_date, season.end_date, classifications)
            result = {
                **table,
                "seasonName": season.name,
                "previous": history[-1] if history else None,
                "analysis": analysis.analysis,
                "classifications": {str(i): c for i, c in classifications.items()},
                "model": analysis.model,
                "modelLabel": MODELS[analysis.model]["label"],
                "servedBy": analysis.served_by,
                "costUsd": cost,
                "generatedAt": _now().isoformat(timespec="seconds"),
            }
            row.result, row.status, row.error = json.dumps(result, ensure_ascii=False), "idle", None
        except Exception as exc:  # noqa: BLE001 - tout échec doit sortir le bilan de l'état « en cours »
            cost = exc.cost if isinstance(exc, AnalysisError) else cost
            row.status = "error"
            row.error = str(exc) if isinstance(exc, AnalysisError) else f"Le calcul a échoué : {exc}"
        row.ai_cost_usd += cost
        row.updated_at = _now()
        db.commit()
        if cost and self.note_cost is not None:
            self.note_cost(db, member.org_id, cost, f"Bilan {row.name}")

    @staticmethod
    def _official_classifications(db: Session, org_id: int, season_id: int) -> dict[int, str]:
        """Classement des opérations « Autres » du bilan officiel de la
        saison, s'il y en a un (pour comparer avec les mêmes catégories)."""
        result = db.scalar(
            select(FinReport.result).where(
                FinReport.org_id == org_id,
                FinReport.season_id == season_id,
                FinReport.state == OFFICIAL,
                FinReport.result.is_not(None),
            )
        )
        if result is None:
            return {}
        return {int(i): c for i, c in json.loads(result).get("classifications", {}).items()}

    def _season_summary(self, db: Session, org_id: int, ledger: dict, season: Season) -> dict:
        """Chiffres d'une saison précédente, pour la comparaison."""
        table = compute_report(ledger, season.start_date, season.end_date, self._official_classifications(db, org_id, season.id))
        return {
            "season": season.name,
            "opening": table["opening"],
            "closing": table["closing"],
            "totalIncome": table["totalIncome"],
            "totalExpense": table["totalExpense"],
            "result": table["result"],
            "net": table["net"],
            "complete": table["opening"] is not None and table["cutoff"] == season.end_date,
        }

    @staticmethod
    def _ai_data(season: Season, table: dict, history: list[dict]) -> dict:
        """Chiffres envoyés à l'IA (noms de champs en français : ils sont lus
        par l'IA, pas par du code)."""
        return {
            "saison": season.name,
            "debutSaison": season.start_date,
            "finSaison": season.end_date,
            "dateArret": table["cutoff"],
            "saisonTerminee": table["cutoff"] >= season.end_date,
            "soldeDebut": table["opening"],
            "soldeFin": table["closing"],
            "recettes": {r["category"]: r["amount"] for r in table["income"]},
            "depenses": {r["category"]: r["amount"] for r in table["expense"]},
            "totalRecettes": table["totalIncome"],
            "totalDepenses": table["totalExpense"],
            "resultat": table["result"],
            "parMois": [
                {
                    "mois": m["month"],
                    "recettes": round(sum(v for v in m["amounts"].values() if v > 0), 2),
                    "depenses": round(-sum(v for v in m["amounts"].values() if v < 0), 2),
                    "soldeFinDeMois": m["closing"],
                }
                for m in table["months"]
            ],
            "saisonsPrecedentes": [
                {
                    "saison": h["season"],
                    "soldeDebut": h["opening"],
                    "soldeFin": h["closing"],
                    "recettesEtDepensesNettesParCategorie": h["net"],
                    "resultat": h["result"],
                    "releveComplet": h["complete"],
                }
                for h in history
            ],
            "categoriesExistantes": [c for c in CATEGORY_NAMES if c not in (OTHER, INTERNAL_TRANSFER)],
            "operationsAClasser": [
                {"operationId": op["id"], "date": op["date"], "libelle": op["label"], "details": op["details"], "montant": op["amount"]}
                for op in unclassified(table)
            ],
        }
