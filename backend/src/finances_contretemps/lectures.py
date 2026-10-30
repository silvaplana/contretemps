"""Le Financier ouvert à l'assistant (Seb, 30 octobre) : tout ce que les
écrans montrent, en lecture (sans carte), et les gestes du trésorier en
écriture (carte Faire / Annuler) : confirmer le compte de lignes, recalculer
un bilan, rédiger le rapport financier, ranger un document de l'AG dans Docs,
tenir le plan comptable (ajouter, renommer, mots-clés, désactiver, supprimer)
et passer en Complet. Seb compte sur l'assistant pour lui expliquer le plan
comptable et le guider dans les écrans : les lectures donnent tout (natures,
écritures d'une ligne) et le guide du module (guide.md) dit où est chaque bouton.

Les lectures rendent du JSON compact : l'assistant lit, l'appli a calculé
(l'IA n'écrit jamais un chiffre). Laissés aux écrans : clôture, soldes de
départ, import de relevés (gestes rares, voir financier.md §7).
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from collections.abc import Callable

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from finances import (
    Accounting,
    AccountingError,
    AgDocuments,
    Finances,
    FinancialReports,
    Forecasts,
    GeneralAssemblies,
    ReportError,
    WrittenReports,
)
from finances.ag_documents import KINDS as AG_KINDS
from finances.ports import Season
from finances.slides import texts

from .actions import SEASON, _member, _season

LIMIT_MAX = 300
DOCUMENTS = {"synthese": "synthese", "balance": "balance", "grand_livre": "grand-livre", "honoraires": "honoraires"}




def _json(data) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str)


class NoParams(BaseModel):
    pass


class SeasonOnly(BaseModel):
    season: str | None = SEASON


class Operations(BaseModel):
    season: str | None = Field(default=None, description="Nom de la saison pour en prendre les dates, ou null (toutes les dates).")
    date_from: dt.date | None = Field(default=None, description="Première date AAAA-MM-JJ, ou null.")
    date_to: dt.date | None = Field(default=None, description="Dernière date AAAA-MM-JJ, ou null.")
    text: str | None = Field(default=None, description="Bout de libellé (ex. « GALLI »), ou null.")
    plan_account: str | None = Field(default=None, description="Numéro du compte du plan confirmé (ex. « 613 »), ou null.")
    missing: str | None = Field(default=None, description="« account » : lignes sans compte du plan ; « piece » : sans pièce ; ou null.")
    limit: int = Field(default=100, ge=1, le=LIMIT_MAX, description="Nombre de lignes au plus (les plus récentes d'abord).")


class OperationId(BaseModel):
    operation_id: int = Field(description="Numéro de la ligne de banque (voir finance_operations).")


class ChartNumber(BaseModel):
    number: str = Field(description="Numéro du compte du plan.")


class Level(BaseModel):
    level: str = Field(description="complet (partie double). On ne revient pas de complet à simple.")


class ReportId(BaseModel):
    report_id: int = Field(description="Numéro du bilan (voir finance_reports).")


class AgDocument(BaseModel):
    season: str | None = SEASON
    document: str = Field(description="synthese, balance, grand_livre ou honoraires.")
    account_number: str | None = Field(default=None, description="Grand livre : numéro d'un compte pour n'avoir que ses lignes, ou null pour tous.")


class AssemblySlides(BaseModel):
    assembly_id: int = Field(description="Numéro de l'AG (voir finance_assemblies).")
    version: str | None = Field(default=None, description="modele, genere, modifie, ou null pour le PowerPoint final (modifié sinon produit).")


class SetAccounts(BaseModel):
    operation_ids: list[int] | None = Field(default=None, max_length=LIMIT_MAX, description="Numéros des lignes (voir finance_operations), ou null pour les choisir par libellé.")
    text: str | None = Field(default=None, description="Bout de libellé : toutes les lignes sans compte qui le contiennent, ou null.")
    season: str | None = Field(default=None, description="Avec text : saison dont on prend les lignes, ou null pour toutes.")
    plan_account: str | None = Field(default=None, description="Numéro du compte du plan à mettre, ou null pour confirmer la proposition de l'appli sur chaque ligne.")


class Recalculate(BaseModel):
    report_id: int = Field(description="Numéro du bilan à recalculer.")


class WriteStatement(BaseModel):
    report_id: int = Field(description="Numéro du bilan dont on rédige le rapport financier.")
    instructions: str = Field(default="", max_length=4000, description="Consignes du trésorier, ou vide.")
    model: str | None = Field(default=None, description="Modèle de langage (identifiant), ou null pour celui par défaut.")


class StoreDocument(BaseModel):
    season: str | None = SEASON
    document: str = Field(description="synthese, balance, grand_livre ou honoraires.")


class ChartAccount(BaseModel):
    number: str = Field(description="Numéro du compte (3 à 10 chiffres). S'il existe, il est renommé ; sinon il est créé.")
    label: str = Field(min_length=1, max_length=80, description="Libellé du compte.")
    nature: str | None = Field(default=None, description="Pour un nouveau compte : depense, recette, banque, caisse, tiers, attente, report ; null pour garder.")
    keywords: list[str] | None = Field(default=None, description="Mots du libellé de banque qui font proposer ce compte, ou null pour garder.")
    active: bool | None = Field(default=None, description="false pour désactiver (plus proposé), true pour réactiver, null pour garder.")


def _euros(amount: float) -> str:
    return f"{amount:,.2f}".replace(",", " ").replace(".", ",") + " €"


def _in_season(rows: list[dict], season: Season | None, start: dt.date | None, end: dt.date | None) -> list[dict]:
    low = start.isoformat() if start else (season.start_date if season else None)
    high = end.isoformat() if end else (season.end_date if season else None)
    return [r for r in rows if (low is None or r["date"] >= low) and (high is None or r["date"] <= high)]


def financier(
    finances: Finances,
    accounting: Accounting,
    reports: FinancialReports,
    assemblies: GeneralAssemblies,
    forecasts: Forecasts,
    documents: AgDocuments,
    written: WrittenReports,
    seasons: Callable[[Session, int], list[Season]],
) -> list[Action]:
    def season_of(db: Session, org_id: int, name: str | None) -> Season:
        return _season(seasons(db, org_id), name)

    def report_season(db: Session, org_id: int, report: dict) -> Season:
        found = [s for s in seasons(db, org_id) if s.id == report["seasonId"]]
        if not found:
            raise Refus("saison du bilan introuvable")
        return found[0]

    def report(db: Session, member, report_id: int) -> dict:
        try:
            return reports.get(db, member, report_id)
        except LookupError as erreur:
            raise Refus(f"bilan {report_id} introuvable (voir finance_reports)") from erreur

    def plan(db: Session, org_id: int, number: str):
        found = [a for a in accounting.accounts(db, org_id) if a.number == number.strip()]
        if not found:
            raise Refus(f"compte {number} absent du plan comptable (voir finance_chart)")
        return found[0]

    # ----- lectures -----

    def read_bank_accounts(db, compte, org_id, p: NoParams) -> str:
        member = _member(db, compte, org_id)
        ledger = finances.get_ledger(db, member)
        cash = accounting.cash(db, member)
        return _json({
            "accounts": [{"name": a["name"], "kind": a["kind"], "balance": a["balance"], "asOf": a["asOf"]} for a in ledger["accounts"]],
            "total": ledger["total"],
            "cash": {k: v for k, v in cash.items() if k != "lines"},
            "withoutAccount": (ledger.get("counts") or {}).get("withoutAccount"),
            "withoutPiece": (ledger.get("counts") or {}).get("withoutPiece"),
            "level": accounting.level(db, org_id),
        })

    def read_operations(db, compte, org_id, p: Operations) -> str:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season) if p.season else None
        ledger = finances.get_ledger(db, member)
        names = {a["id"]: a["name"] for a in ledger["allAccounts"]}
        rows = _in_season(ledger["rows"], season, p.date_from, p.date_to)
        if p.text:
            wanted = p.text.casefold()
            rows = [r for r in rows if wanted in f"{r['label']} {r.get('details') or ''}".casefold()]
        if p.plan_account:
            rows = [r for r in rows if r["account"] and r["account"]["number"] == p.plan_account.strip()]
        if p.missing == "account":
            rows = [r for r in rows if not r.get("transfer") and r["account"] is None]
        elif p.missing == "piece":
            rows = [r for r in rows if not r.get("transfer") and r["piece"] is None]
        lines = [
            {
                "id": r["id"], "date": r["date"], "label": r["label"], "details": r.get("details") or None, "amount": r["amount"],
                "bank": f"{r['transfer']['from']} → {r['transfer']['to']}" if r.get("transfer") else names.get(r["accountId"]),
                "planAccount": r["account"] and f"{r['account']['number']} {r['account']['label']}",
                "proposal": r["proposal"] and f"{r['proposal']['number']} {r['proposal']['label']} ({r['proposal']['reason']})",
                "piece": bool(r["piece"]),
            }
            for r in rows[: p.limit]
        ]
        total = round(sum(r["amount"] for r in rows if not r.get("transfer")), 2)
        return _json({"count": len(rows), "shown": len(lines), "total": total, "lines": lines})

    def read_chart(db, compte, org_id, p: NoParams) -> str:
        member = _member(db, compte, org_id)
        chart = accounting.chart(db, member)
        return _json({
            "level": chart["level"],
            "natures": {n["id"]: n["label"] for n in chart["natures"]},
            "accounts": [
                {"number": a["number"], "label": a["label"], "nature": a["nature"], "event": a["event"],
                 "keywords": a["keywords"], "active": a["active"], "confirmedLines": a["used"]}
                for a in chart["accounts"]
            ],
        })

    def read_operation(db, compte, org_id, p: OperationId) -> str:
        member = _member(db, compte, org_id)
        try:
            sheet = accounting.operation(db, member, p.operation_id)
        except LookupError as erreur:
            raise Refus(f"ligne {p.operation_id} introuvable") from erreur
        entries = documents.operation_entries(db, member, p.operation_id, sheet["date"])
        return _json({**{k: v for k, v in sheet.items() if k != "bankAccount"}, "bank": sheet["bankAccount"]["name"], "entries": entries})

    def read_reports(db, compte, org_id, p: SeasonOnly) -> str:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        return _json({"season": season.name, "reports": [
            {k: r[k] for k in ("id", "name", "state", "status", "error", "hasResult", "updatedAt")} for r in reports.list(db, member, season.id)
        ]})

    def read_report(db, compte, org_id, p: ReportId) -> str:
        member = _member(db, compte, org_id)
        r = report(db, member, p.report_id)
        result = r["result"] or {}
        statement = written.get(db, p.report_id)
        return _json({
            "name": r["name"], "state": r["state"], "status": r["status"], "prompt": r["prompt"] or None,
            "result": {k: result.get(k) for k in (
                "start", "end", "cutoff", "opening", "closing", "income", "expense", "totalIncome", "totalExpense",
                "result", "verification", "analysis", "issues",
            )} if result else None,
            "previousSeason": result.get("previous") and {
                k: result["previous"].get(k) for k in ("season", "totalIncome", "totalExpense", "result", "net")
            },
            "financialStatement": statement and {k: v for k, v in statement.items() if k not in ("id", "costUsd")},
        })

    def read_ag_document(db, compte, org_id, p: AgDocument) -> str:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        kind = DOCUMENTS.get(p.document)
        if kind is None:
            raise Refus("document inconnu : synthese, balance, grand_livre ou honoraires")
        if AG_KINDS[kind][2] == "complet" and accounting.level(db, org_id) != "complet":
            raise Refus(f"{AG_KINDS[kind][0]} : niveau Complet seulement (Comptes › ⋯ › Plan comptable)")
        if kind == "synthese":
            return _json(documents.synthese(db, member, season))
        if kind == "honoraires":
            fees = documents.ports.fees(db, org_id, season.start_date, season.end_date) if documents.ports.fees else []
            by_person: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
            for f in fees:
                by_person[f["person"]][f["month"]] += f["amount"]
            return _json({"season": season.name, "fees": {
                person: {"months": {m: round(a, 2) for m, a in sorted(months.items())}, "total": round(sum(months.values()), 2)}
                for person, months in sorted(by_person.items())
            }})
        books = documents.books(db, member, season)
        cutoff = books.pop("_cutoff")
        accounts = sorted(books.values(), key=lambda a: a.number)
        if kind == "balance":
            return _json({"season": season.name, "cutoff": cutoff, "accounts": [
                {"number": a.number, "label": a.label, "debit": a.debit / 100, "credit": a.credit / 100, "balance": a.balance / 100}
                for a in accounts
            ]})
        if p.account_number:
            accounts = [a for a in accounts if a.number == p.account_number.strip()]
        lines = [
            {"account": a.number, "date": l.date, "journal": l.journal, "label": l.label, "piece": l.piece or None,
             "debit": l.debit / 100, "credit": l.credit / 100, "letter": l.letter or None}
            for a in accounts for l in a.lines
        ]
        return _json({"season": season.name, "cutoff": cutoff, "count": len(lines), "lines": lines[:LIMIT_MAX],
                      "note": "tronqué : demander un compte (account_number)" if len(lines) > LIMIT_MAX else None})

    def read_assemblies(db, compte, org_id, p: SeasonOnly) -> str:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        return _json({"season": season.name, "assemblies": [
            {k: a[k] for k in ("id", "name", "state", "status", "error", "hasPpt", "updatedAt")} for a in assemblies.list(db, member, season.id)
        ]})

    def read_slides(db, compte, org_id, p: AssemblySlides) -> str:
        member = _member(db, compte, org_id)
        try:
            path, filename = assemblies.file_path(db, member, p.assembly_id, p.version)
        except LookupError as erreur:
            raise Refus("pas de PowerPoint pour cette AG (ou version inconnue : modele, genere, modifie)") from erreur
        slides = [
            {"number": s["number"], "hidden": s["hidden"] or None, "title": s["title"], "text": [l["text"] for l in s["lines"]]}
            for s in texts(path)
        ]
        return _json({"file": filename, "slides": slides})

    def read_forecasts(db, compte, org_id, p: SeasonOnly) -> str:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        found = []
        for f in forecasts.list(db, member, season.id):
            detail = forecasts.get(db, member, f["id"])
            result = detail["result"] or {}
            found.append({
                **{k: f[k] for k in ("id", "name", "state", "status", "error", "updatedAt")},
                "prompt": detail["prompt"] or None,
                "result": {k: v for k, v in result.items() if k not in ("code", "formula", "points", "series")} or None,
            })
        return _json({"season": season.name, "forecasts": found})

    # ----- écritures (carte Faire / Annuler) -----

    def prepare_accounts(db, compte, org_id, p: SetAccounts) -> Ligne:
        member = _member(db, compte, org_id)
        rows = [r for r in finances.get_ledger(db, member)["rows"] if not r.get("transfer")]
        if p.operation_ids:
            wanted = set(p.operation_ids)
            rows = [r for r in rows if r["id"] in wanted]
            if len(rows) != len(wanted):
                raise Refus("lignes inconnues ou virements entre vos comptes (voir finance_operations)")
        elif p.text:
            season = season_of(db, org_id, p.season) if p.season else None
            needle = p.text.casefold()
            rows = [r for r in _in_season(rows, season, None, None)
                    if r["account"] is None and needle in f"{r['label']} {r.get('details') or ''}".casefold()]
        else:
            raise Refus("donner operation_ids ou text")
        target = plan(db, org_id, p.plan_account) if p.plan_account else None
        if target is not None and not target.active:
            raise Refus(f"compte {target.number} inactif")
        chosen = []
        for r in rows[:LIMIT_MAX]:
            account_id = target.id if target else (r["proposal"] or {}).get("id")
            if account_id is not None:
                chosen.append((r, account_id))
        if not chosen:
            raise Refus("aucune ligne à classer (ou aucune proposition de l'appli : donner plan_account)")
        by_id = {a.id: a for a in accounting.accounts(db, org_id)}

        def faire(db: Session) -> None:
            for r, account_id in chosen:
                try:
                    accounting.set_lines(db, member, r["id"], [{"accountId": account_id}])
                except AccountingError as erreur:
                    raise Refus(f"{r['date']} {r['label']} : {erreur}") from erreur

        targets = sorted({f"{by_id[a].number} {by_id[a].label}" for _, a in chosen})
        sample = " ; ".join(f"{r['date'][8:10]}/{r['date'][5:7]}/{r['date'][:4]} {r['label']} {_euros(r['amount'])}" for r, _ in chosen[:5])
        more = f" et {len(chosen) - 5} autres" if len(chosen) > 5 else ""
        return Ligne(
            f"Mettre {len(chosen)} ligne(s) de banque sur {', '.join(targets)} : {sample}{more}. "
            "Visible dans Financier › Comptes et dans les documents de l'AG.",
            faire,
        )

    def prepare_recalculate(db, compte, org_id, p: Recalculate) -> Ligne:
        member = _member(db, compte, org_id)
        r = report(db, member, p.report_id)

        def faire(db: Session) -> None:
            try:
                reports.run(db, member, p.report_id, {})
            except ReportError as erreur:
                raise Refus(str(erreur)) from erreur

        return Ligne(f"Recalculer le bilan « {r['name']} » depuis les lignes de banque, puis refaire l'analyse. Résultat dans Financier › Bilan.", faire)

    def prepare_statement(db, compte, org_id, p: WriteStatement) -> Ligne:
        member = _member(db, compte, org_id)
        r = report(db, member, p.report_id)
        season = report_season(db, org_id, r)
        options = reports.models()
        model = p.model or options["defaultModel"]
        labels = {m["id"]: m["label"] for m in options["models"]}
        if model not in labels:
            raise Refus(f"modèle « {model} » inconnu : " + ", ".join(labels))
        analysis = (r["result"] or {}).get("analysis", [])

        def faire(db: Session) -> None:
            try:
                written.write(db, member, p.report_id, season, p.instructions, model, analysis)
            except Exception as erreur:  # AnalysisError, réseau : message à la personne
                raise Refus(f"rédaction impossible : {erreur}") from erreur

        return Ligne(
            f"Rédiger le rapport financier du bilan « {r['name']} » ({labels[model]}) : texte par le modèle, chaque montant "
            "placé par l'appli. À relire dans Financier › Bilan › Documents de l'AG.",
            faire,
        )

    def prepare_store(db, compte, org_id, p: StoreDocument) -> Ligne:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        kind = DOCUMENTS.get(p.document)
        if kind is None:
            raise Refus("document inconnu : synthese, balance, grand_livre ou honoraires")
        if AG_KINDS[kind][2] == "complet" and accounting.level(db, org_id) != "complet":
            raise Refus(f"{AG_KINDS[kind][0]} : niveau Complet seulement")
        title, extension, _ = AG_KINDS[kind]

        def faire(db: Session) -> None:
            documents.in_docs(db, member, season, kind)

        return Ligne(f"Produire « {title} {season.name}.{extension} » et le ranger dans Docs › Financier › AG.", faire)

    def prepare_chart_account(db, compte, org_id, p: ChartAccount) -> Ligne:
        member = _member(db, compte, org_id)
        number = p.number.strip()
        existing = next((a for a in accounting.accounts(db, org_id) if a.number == number), None)
        data = {"number": number, "label": p.label.strip()}
        if existing is None:
            if p.nature is None:
                raise Refus("nouveau compte : donner sa nature (depense, recette…)")
            data |= {"nature": p.nature, "keywords": p.keywords or []}
        else:
            data |= {"nature": existing.nature, "keywords": p.keywords if p.keywords is not None else list(existing.keywords or []),
                     "event": existing.event}
        if p.active is not None:
            data["active"] = p.active
        try:
            accounting._validate(db, org_id, data, existing)
        except AccountingError as erreur:
            raise Refus(str(erreur)) from erreur

        def faire(db: Session) -> None:
            try:
                if existing is None:
                    accounting.create_account(db, member, data)
                else:
                    accounting.update_account(db, member, existing.id, data)
            except AccountingError as erreur:
                raise Refus(str(erreur)) from erreur

        words = f" (mots du libellé : {', '.join(data['keywords'])})" if data["keywords"] else ""
        state = {True: ", réactivé", False: ", désactivé (plus proposé)"}.get(p.active, "")
        if existing is None:
            return Ligne(f"Ajouter au plan comptable le compte {number} « {data['label']} »{words}{state}.", faire)
        renamed = f" en « {data['label']} »" if existing.label != data["label"] else ""
        verb = "Renommer" if renamed else "Modifier"
        return Ligne(f"{verb} le compte {number} « {existing.label} »{renamed}{words}{state}.", faire)

    def prepare_delete_account(db, compte, org_id, p: ChartNumber) -> Ligne:
        member = _member(db, compte, org_id)
        account = plan(db, org_id, p.number)
        used = next(a["used"] for a in accounting.chart(db, member)["accounts"] if a["id"] == account.id)

        def faire(db: Session) -> None:
            accounting.delete_account(db, member, account.id)

        if used:
            return Ligne(f"Désactiver le compte {account.number} « {account.label} » : {used} ligne(s) y sont rangées, il est gardé "
                         "mais n'est plus proposé.", faire)
        return Ligne(f"Supprimer du plan comptable le compte {account.number} « {account.label} » (aucune ligne dessus).", faire)

    def prepare_level(db, compte, org_id, p: Level) -> Ligne:
        member = _member(db, compte, org_id)
        if p.level != "complet":
            raise Refus("seul le passage en complet est possible (on ne revient pas en simple)")
        if accounting.level(db, org_id) == "complet":
            raise Refus("déjà au niveau complet")

        def faire(db: Session) -> None:
            accounting.set_level(db, member, "complet")

        return Ligne("Passer la comptabilité au niveau Complet (partie double : comptes de tiers, lettrage, soldes de départ, "
                     "clôture ; Balance, Grand livre et Honoraires). On ne revient pas en Simple.", faire)

    def read(name: str, module: str, description: str, params: type[BaseModel], fn) -> Action:
        return Action(name, module, description, params, None, admin_only=False, read=fn)

    return [
        read("finance_bank_accounts", "Financier",
             "Financier › Comptes : solde de chaque compte en banque et de la caisse, total, nombre de lignes sans compte du plan "
             "et sans pièce, niveau comptable (simple ou complet).", NoParams, read_bank_accounts),
        read("finance_operations", "Financier",
             "Financier › Comptes : lignes de banque (date, libellé, montant, compte du plan confirmé ou proposé, pièce), "
             "filtrées par saison ou dates, libellé, compte du plan, ou ce qui manque (sans compte, sans pièce).",
             Operations, read_operations),
        read("finance_chart", "Financier",
             "Plan comptable de l'association : niveau (simple ou complet), natures, et pour chaque compte numéro, libellé, "
             "nature, mots-clés qui le font proposer, actif ou non, nombre de lignes confirmées. Sert aussi à expliquer le plan.",
             NoParams, read_chart),
        read("finance_operation", "Financier",
             "Le détail d'une ligne de banque : compte(s) du plan confirmé(s) ou proposé (avec la raison), pièce, et les écritures "
             "comptables qu'elle produit (journal, débit, crédit, lettrage).", OperationId, read_operation),
        read("finance_reports", "Financier", "Financier › Bilan : les bilans d'une saison (numéro, nom, état, calculé ou non).",
             SeasonOnly, read_reports),
        read("finance_report", "Financier",
             "Le contenu d'un bilan : recettes et dépenses par compte, totaux, résultat, vérification des soldes, analyse écrite, "
             "saison précédente, et le rapport financier rédigé s'il existe.", ReportId, read_report),
        read("finance_ag_document", "Financier",
             "Le contenu d'un document de l'AG d'une saison (Financier › Bilan › Documents de l'AG) : synthese (charges et produits "
             "par compte, trésorerie, fournisseurs à payer, événements, à classer), balance, grand_livre ou honoraires (par "
             "professeur et par mois). Balance, grand livre et honoraires : niveau Complet.", AgDocument, read_ag_document),
        read("finance_assemblies", "Financier", "Financier › AG : les assemblées générales d'une saison et leur PowerPoint.",
             SeasonOnly, read_assemblies),
        read("finance_assembly_slides", "Financier", "Le texte de chaque diapo du PowerPoint d'une AG (final, produit, modifié ou modèle).",
             AssemblySlides, read_slides),
        read("finance_forecasts", "Financier", "Financier › Prévisionnel : les prévisionnels d'une saison, consignes et résultat.",
             SeasonOnly, read_forecasts),
        Action("set_operation_accounts", "Financier",
               "Confirme le compte du plan de lignes de banque (Financier › Comptes) : des lignes choisies par numéro, ou toutes les "
               "lignes sans compte dont le libellé contient un texte (ex. GALLI → 613). Sans plan_account, la proposition de "
               "l'appli est confirmée ligne par ligne. Vide le « à classer » des documents de l'AG.",
               SetAccounts, prepare_accounts, admin_only=False),
        Action("recalculate_financial_report", "Bilan", "Recalcule un bilan existant (après avoir classé des lignes) et refait son analyse.",
               Recalculate, prepare_recalculate, admin_only=False),
        Action("write_financial_statement", "Bilan",
               "Fait rédiger le rapport financier d'un bilan (Word et PDF) : texte par le modèle, chaque montant placé par l'appli.",
               WriteStatement, prepare_statement, admin_only=False),
        Action("store_ag_document", "Bilan", "Produit un document de l'AG d'une saison et le range dans Docs › Financier › AG.",
               StoreDocument, prepare_store, admin_only=False),
        Action("edit_chart_account", "Financier",
               "Ajoute un compte au plan comptable, ou modifie un compte existant (même numéro) : libellé, mots-clés, actif ou non.",
               ChartAccount, prepare_chart_account, admin_only=False),
        Action("delete_chart_account", "Financier",
               "Supprime un compte du plan comptable jamais utilisé ; s'il a des lignes, il est désactivé.",
               ChartNumber, prepare_delete_account, admin_only=False),
        Action("set_accounting_level", "Financier",
               "Passe la comptabilité au niveau Complet (partie double). Sans retour en Simple.", Level, prepare_level, admin_only=False),
    ]
