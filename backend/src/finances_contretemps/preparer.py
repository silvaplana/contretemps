"""Le reste du Financier ouvert à l'assistant (Seb, 20/11 : « tout le
Financier ») : Comptes › Balance (Balance, Grand-livre, Compte de résultat
sur une période), la caisse, les comptes proposés, et Bilan › Préparer
(étapes, relevés, soldes de départ, écritures de fin d'année, écritures à la
main, budget prévisionnel, documents de la saison). Lectures sans carte,
écritures par carte Faire / Annuler ; chaque outil appelle le service de la
route de l'écran, avec les mêmes droits (trésoriers et Super User).

Restent à la personne : clôturer ou rouvrir une saison, « Repartir à zéro »,
la banque, l'import de relevés, les suppressions, et « Produire » un
document de l'étape 6 (un téléchargement : rien n'est rangé dans Docs).
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from assistant.actions import Action
from assistant.modifications import Ligne, Refus
from finances import Accounting, AccountingError, AgDocuments, Finances, FinancialReports, WrittenReports
from finances.ports import Season
from finances.season_documents import LABELS

from .actions import SEASON, _member, _season
from .lectures import LIMIT_MAX, _euros, _json

SHOWN = 50  # lignes au plus dans une liste d'une lecture de Préparer
VIEWS = ("balance", "grand_livre", "compte_de_resultat")
PARTS = ("etapes", "releves", "soldes_depart", "fin_annee", "ecritures_main", "budget", "documents")
CHOICES = {"same": "Comme l'an dernier", "new": "Nouveau", "none": "Non"}


class Period(BaseModel):
    view: str = Field(description="balance, grand_livre ou compte_de_resultat (avec la saison d'avant, mêmes dates).")
    season: str | None = Field(default=None, description="Nom de la saison, ou null pour celle de l'écran (la dernière saison terminée si elle n'est pas clôturée, sinon celle en cours).")
    date_from: dt.date | None = Field(default=None, description="Première date AAAA-MM-JJ dans la saison, ou null.")
    date_to: dt.date | None = Field(default=None, description="Dernière date AAAA-MM-JJ dans la saison, ou null.")
    account_number: str | None = Field(default=None, description="grand_livre : numéro d'un compte pour n'avoir que ses écritures, ou null.")


class Part(BaseModel):
    season: str | None = SEASON
    part: str = Field(description="etapes (ce qui reste à faire), releves, soldes_depart, fin_annee, ecritures_main, budget ou documents.")


class Limit(BaseModel):
    limit: int = Field(default=SHOWN, ge=1, le=LIMIT_MAX, description="Nombre de lignes au plus (les plus récentes d'abord).")


class NoParams(BaseModel):
    pass


class Budget(BaseModel):
    season: str | None = Field(default=None, description="Saison du bilan (le budget est celui de la saison suivante), ou null pour la saison en cours.")
    take_realised: bool = Field(default=False, description="true : « Reprendre le réalisé » (chaque ligne prend le chiffre de la saison) avant les montants donnés.")
    lines: dict[str, float | None] = Field(default_factory=dict, description="Montant prévu par numéro de compte (euros, positif), null pour effacer.")


class YearEndChoice(BaseModel):
    key: str = Field(description="Clé de la ligne (voir finance_preparation, part fin_annee).")
    keep: bool | None = Field(default=None, description="true : passer l'écriture (compter dans l'autre saison, étaler) ; false : laisser ; null : le choix conseillé.")
    years: int | None = Field(default=None, description="Amortissement : 3, 5 ou 10 ans, ou null (5).")


class YearEnd(BaseModel):
    season: str | None = SEASON
    choices: list[YearEndChoice] = Field(default_factory=list, max_length=LIMIT_MAX, description="Les choix qui changent ; les autres lignes prennent le choix conseillé.")


class Proposals(BaseModel):
    numbers: list[str] | None = Field(default=None, max_length=LIMIT_MAX, description="Numéros des comptes proposés à créer (voir finance_chart_proposals), ou null pour tous.")
    labels: dict[str, str] = Field(default_factory=dict, description="Nom à donner, par numéro, si on change celui proposé.")


class Correction(BaseModel):
    report_id: int = Field(description="Numéro du bilan dont le rapport financier est rédigé (voir finance_reports).")
    instruction: str = Field(min_length=1, max_length=4000, description="Ce qu'il faut changer dans le texte.")


class CashLine(BaseModel):
    date: dt.date = Field(description="Date AAAA-MM-JJ.")
    label: str = Field(min_length=1, max_length=120, description="Libellé.")
    amount: float = Field(description="Montant en euros : positif = entrée dans la caisse, négatif = sortie.")
    plan_account: str | None = Field(default=None, description="Numéro du compte du plan, ou null.")
    withdrawal_operation_id: int | None = Field(default=None, description="Retrait au distributeur : numéro de la transaction bancaire (voir finance_operations) ; alors pas de compte.")


class ManualEntry(BaseModel):
    season: str | None = SEASON
    date: dt.date = Field(description="Date AAAA-MM-JJ dans la saison.")
    label: str = Field(min_length=1, max_length=120, description="Libellé.")
    debit_account: str = Field(description="Numéro du compte débité.")
    credit_account: str = Field(description="Numéro du compte crédité.")
    amount: float = Field(gt=0, description="Montant positif en euros.")


class OpeningLine(BaseModel):
    number: str = Field(description="Numéro du compte.")
    balance: float = Field(description="Solde en euros : positif = débiteur (banque, caisse, créances), négatif = dû (fournisseurs, fonds).")
    label: str | None = Field(default=None, description="Libellé, pour un compte absent de la liste.")


class Opening(BaseModel):
    season: str | None = SEASON
    from_previous_balance: bool = Field(default=False, description="true : partir des soldes lus dans la Balance de la saison précédente déposée dans Docs › Financier.")
    balances: list[OpeningLine] = Field(default_factory=list, max_length=LIMIT_MAX, description="Soldes à mettre (les autres comptes gardent le leur).")


class DocumentChoice(BaseModel):
    document: str = Field(description="Nature : " + ", ".join(k for k in LABELS if k not in ("autre", "budget")) + ".")
    choice: Literal["same", "new", "none"] = Field(description="same = Comme l'an dernier, new = Nouveau, none = Non.")


class SeasonDocuments(BaseModel):
    season: str | None = SEASON
    choices: list[DocumentChoice] = Field(min_length=1, max_length=20)


def _value_errors(call, *args):
    """Une ValueError du service (message pour la personne) devient un refus."""
    try:
        return call(*args)
    except (ValueError, AccountingError) as erreur:
        raise Refus(str(erreur)) from erreur


def _capped(rows: list, n: int = SHOWN) -> dict:
    return {"count": len(rows), "lines": rows[:n]} if len(rows) > n else {"count": len(rows), "lines": rows}


def preparer(
    finances: Finances,
    accounting: Accounting,
    reports: FinancialReports,
    documents: AgDocuments,
    written: WrittenReports,
    seasons: Callable[[Session, int], list[Season]],
) -> list[Action]:
    def season_of(db: Session, org_id: int, name: str | None) -> Season:
        return _season(seasons(db, org_id), name)

    def plan(db: Session, org_id: int, number: str, active: bool = True):
        found = [a for a in accounting.accounts(db, org_id, active_only=active) if a.number == number.strip()]
        if not found:
            raise Refus(f"compte {number} absent du plan comptable" + (" ou inactif" if active else "") + " (voir finance_chart)")
        return found[0]

    # ----- lectures -----

    def read_period(db, compte, org_id, p: Period) -> str:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season) if p.season else documents.balance_season(db, org_id)
        if season is None:
            raise Refus("aucune saison")
        start, end = (d.isoformat() if d else None for d in (p.date_from, p.date_to))
        if p.view == "compte_de_resultat":
            return _json(_value_errors(documents.income_statement, db, member, season, start, end))
        if p.view not in VIEWS:
            raise Refus("view : balance, grand_livre ou compte_de_resultat")
        data = _value_errors(documents.balance, db, member, season, start, end)
        head = {k: data[k] for k in ("seasonName", "start", "end", "knownUntil", "closed", "openingMissing")}
        if p.view == "balance":
            return _json({**head, "accounts": [
                {"number": a["number"], "label": a["label"], "debit": a["debit"], "credit": a["credit"],
                 "balance": round(a["debit"] - a["credit"], 2)}
                for a in data["accounts"]
            ]})
        accounts = data["accounts"]
        if p.account_number:
            accounts = [a for a in accounts if a["number"] == p.account_number.strip()]
        lines = [{"account": a["number"], **{k: l[k] or None for k in ("date", "journal", "label", "piece")}, "debit": l["debit"], "credit": l["credit"]}
                 for a in accounts for l in a["lines"]]
        return _json({**head, "count": len(lines), "lines": lines[:LIMIT_MAX],
                      "note": "tronqué : demander un compte (account_number) ou des dates" if len(lines) > LIMIT_MAX else None})

    def read_part(db, compte, org_id, p: Part) -> str:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        head = {"season": season.name}
        if p.part == "releves":
            calendar = finances.statement_calendar(db, member, season.start_date, season.end_date)
            return _json({**head, "accounts": [
                {"name": a["name"], "months": {m["month"]: m["state"] for m in a["months"]}} for a in calendar["accounts"]
            ], "states": "ok importé, quiet aucun mouvement, missing manquant, before avant le premier relevé, bank à importer, waiting en attente, future"})
        if p.part == "etapes":
            calendar = finances.statement_calendar(db, member, season.start_date, season.end_date)
            data = _value_errors(documents.preparation, db, member, season, calendar)
            classify = data["classify"]
            return _json({
                **head, "level": data["level"], "closed": data["closed"],
                "1_statements": data["statements"], "2_opening": data["opening"],
                "3_classify": {
                    "withoutAccount": classify["withoutAccount"],
                    "oneByOne": _capped([{k: o[k] for k in ("id", "date", "label", "amount", "chequeDeposit")} for o in classify["unsure"]]),
                    "byProposedAccount": [
                        {"account": f"{g['account']['number']} {g['account']['label']}", "accountId": g["account"]["id"],
                         "operationIds": [o["id"] for o in g["operations"]][:LIMIT_MAX], "count": len(g["operations"])}
                        for g in classify["sure"]
                    ],
                    "pieceVsTransaction": _capped([
                        {"id": m["id"], "date": m["date"], "label": m["label"], "amount": m["amount"],
                         "piece": f"{m['piece']['account']} ({m['piece']['title']})", "transaction": m["account"]["number"]}
                        for m in classify["mismatches"]
                    ]),
                },
                "4_offBank": {
                    "cash": data["offBank"]["cash"], "cashLines": data["offBank"]["cashLines"],
                    "unpaidTotal": data["offBank"]["unpaidTotal"], "unpaid": _capped(data["offBank"]["unpaid"]),
                    "manualEntries": len(data["offBank"]["entries"]),
                },
                "5_controls": data["controls"],
                "6_comparison": {
                    "previousSeason": data["comparison"]["previousSeason"], "unexplained": data["comparison"]["unexplained"],
                    "lines": [l for l in data["comparison"]["lines"] if l["flag"] or l["note"]],
                },
            })
        if p.part == "soldes_depart":
            data = _value_errors(documents.opening, db, member, season)
            return _json({
                **{k: data[k] for k in ("season", "source", "closed", "bankCheck")},
                "accounts": [a for a in data["accounts"] if a["balance"]] or data["accounts"],
                "earlyTransactions": _capped(data["earlyTransactions"]), "unpaidBefore": _capped(data["unpaidBefore"]),
            })
        if p.part == "fin_annee":
            return _json(_value_errors(documents.year_end, db, member, season))
        if p.part == "ecritures_main":
            entries = _value_errors(documents.manual_entries, db, member, season)
            return _json({**head, "entries": [
                {"id": e["id"], "date": e["date"], "label": e["label"], "amount": e["amount"],
                 "debit": f"{e['debit']['number']} {e['debit']['label']}", "credit": f"{e['credit']['number']} {e['credit']['label']}"}
                for e in entries
            ]})
        if p.part == "budget":
            return _json(_value_errors(documents.budget, db, member, season))
        if p.part == "documents":
            data = _value_errors(documents.season_documents, db, member, season)
            return _json({
                **head, **{k: data[k] for k in ("level", "previousSeason", "provisional", "rows", "fecCheck", "closing")},
                "addable": [{"document": k, "label": LABELS[k]} for k in data["addable"]],
                "lastYearFiles": [{"name": m["name"], "document": m["kind"]} for m in data["models"]],
                "budget": next((d for d in data["documents"] if d["kind"] == "budget"), None),
            })
        raise Refus("part : " + ", ".join(PARTS))

    def read_cash(db, compte, org_id, p: Limit) -> str:
        member = _member(db, compte, org_id)
        cash = accounting.cash(db, member)
        return _json({"balance": cash["balance"], "asOf": cash["asOf"], "count": len(cash["lines"]), "lines": [
            {"date": l["date"], "label": l["label"], "amount": l["amount"],
             "planAccount": l["account"] and f"{l['account']['number']} {l['account']['label']}",
             "withdrawal": l["transferOperationId"] is not None or None}
            for l in cash["lines"][: p.limit]
        ]})

    def read_proposals(db, compte, org_id, p: NoParams) -> str:
        member = _member(db, compte, org_id)
        return _json({"proposals": [
            {k: g[k] for k in ("number", "label", "parent", "count", "sameAmount")} for g in accounting.propose_accounts(db, member)
        ]})

    # ----- écritures (carte Faire / Annuler) -----

    def prepare_budget(db, compte, org_id, p: Budget) -> Ligne:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        current = documents.budget(db, member, season)
        known = {l["number"]: l for side in ("charges", "produits") for l in current[side]["lines"]}
        unknown = [n for n in p.lines if n.strip() not in known]
        if unknown:
            raise Refus(f"compte(s) {', '.join(unknown)} absent(s) du budget (voir finance_preparation, part budget)")
        if any(v is not None and v < 0 for v in p.lines.values()):
            raise Refus("un montant prévu est positif")
        if not p.take_realised and not p.lines:
            raise Refus("donner lines ou take_realised")
        lines = {n.strip(): v for n, v in p.lines.items()}

        def faire(db: Session) -> None:
            if p.take_realised:
                documents.take_realised(db, member, season)
            if lines:
                documents.set_budget(db, member, season, lines)

        what = ["reprendre le réalisé de " + season.name] if p.take_realised else []
        what += [f"{n} {known[n]['label']} : " + ("effacé" if v is None else _euros(v)) for n, v in list(lines.items())[:8]]
        more = f" et {len(lines) - 8} autres" if len(lines) > 8 else ""
        return Ligne(f"Budget prévisionnel {current['nextName']} : {' ; '.join(what)}{more}. "
                     "Financier › Bilan › Préparer, étape 6.", faire)

    def prepare_year_end(db, compte, org_id, p: YearEnd) -> Ligne:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        data = _value_errors(documents.year_end, db, member, season)
        if data["closed"]:
            raise Refus("saison clôturée : à rouvrir d'abord (par la personne, étape 7)")
        if not data["items"]:
            raise Refus("aucune écriture de fin d'année proposée pour cette saison")
        items = {i["key"]: i for i in data["items"]}
        unknown = [c.key for c in p.choices if c.key not in items]
        if unknown:
            raise Refus(f"ligne(s) inconnue(s) : {', '.join(unknown)} (voir finance_preparation, part fin_annee)")
        if any(c.years is not None and c.years not in (3, 5, 10) for c in p.choices):
            raise Refus("durée d'amortissement : 3, 5 ou 10 ans")
        chosen = {c.key: c for c in p.choices}
        payload = [{"key": c.key, "keep": c.keep, "years": c.years} for c in p.choices]

        def faire(db: Session) -> None:
            documents.set_year_end(db, member, season, payload)

        def said(i: dict) -> str:
            c = chosen.get(i["key"])
            keep = c.keep if c and c.keep is not None else i["advised"]
            years = (c.years if c else None) or i.get("years") or 5
            what = (f"étaler sur {years} ans" if i["kind"] == "depreciation" else "passer l'écriture") if keep else "laisser"
            return f"{i['title']} « {i['text'][:60]} » : {what}"

        listed = [said(i) for i in data["items"]]
        more = f" et {len(listed) - 6} autres" if len(listed) > 6 else ""
        return Ligne(f"Valider les écritures de fin d'année {season.name} : {' ; '.join(listed[:6])}{more}. "
                     "Financier › Bilan › Préparer, étape 4 (« Annuler » y défait).", faire)

    def prepare_proposals(db, compte, org_id, p: Proposals) -> Ligne:
        member = _member(db, compte, org_id)
        proposals = accounting.propose_accounts(db, member)
        if p.numbers is not None:
            wanted = {n.strip() for n in p.numbers}
            missing = wanted - {g["number"] for g in proposals}
            if missing:
                raise Refus(f"pas de proposition {', '.join(sorted(missing))} (voir finance_chart_proposals)")
            proposals = [g for g in proposals if g["number"] in wanted]
        if not proposals:
            raise Refus("aucun compte proposé")
        items = [{"parentId": g["parentId"], "key": g["key"], "label": p.labels.get(g["number"], g["label"]).strip()[:80]} for g in proposals]

        def faire(db: Session) -> None:
            try:
                accounting.create_proposed(db, member, items)
            except AccountingError as erreur:
                raise Refus(str(erreur)) from erreur

        said = [f"{g['number']} « {i['label']} » ({g['count']} transaction(s) de {g['parent']})" for g, i in zip(proposals, items)]
        more = f" et {len(said) - 8} autres" if len(said) > 8 else ""
        return Ligne(f"Créer au plan comptable : {' ; '.join(said[:8])}{more}. Leurs transactions y passent.", faire)

    def prepare_correction(db, compte, org_id, p: Correction) -> Ligne:
        member = _member(db, compte, org_id)
        try:
            r = reports.get(db, member, p.report_id)
        except LookupError as erreur:
            raise Refus(f"bilan {p.report_id} introuvable (voir finance_reports)") from erreur
        if not written.get(db, p.report_id):
            raise Refus("pas encore de rapport financier pour ce bilan : le faire rédiger d'abord (write_financial_statement)")
        season = next((s for s in seasons(db, org_id) if s.id == r["seasonId"]), None)
        if season is None:
            raise Refus("saison du bilan introuvable")
        instruction = p.instruction.strip()

        def faire(db: Session) -> None:
            try:
                written.correct(db, member, p.report_id, season, instruction)
            except Exception as erreur:  # AnalysisError, réseau : message à la personne
                raise Refus(f"correction impossible : {erreur}") from erreur

        return Ligne(f"Corriger le rapport financier du bilan « {r['name']} » : « {instruction[:200]} ». Le reste du texte ne bouge "
                     "pas, les chiffres restent ceux de l'appli ; « Annuler la dernière correction » dans Bilan › Préparer, étape 6.", faire)

    def prepare_cash(db, compte, org_id, p: CashLine) -> Ligne:
        member = _member(db, compte, org_id)
        data = {"date": p.date.isoformat(), "label": p.label.strip(), "amount": p.amount}
        target = ""
        if p.withdrawal_operation_id is not None:
            data["transferOperationId"] = p.withdrawal_operation_id
            target = " (retrait de la banque)"
        elif p.plan_account:
            account = plan(db, org_id, p.plan_account)
            data["accountId"] = account.id
            target = f" sur {account.number} {account.label}"
        if not data["label"] or round(p.amount * 100) == 0:
            raise Refus("donner un libellé et un montant qui n'est pas zéro")

        def faire(db: Session) -> None:
            try:
                accounting.add_cash_line(db, member, data)
            except AccountingError as erreur:
                raise Refus(str(erreur)) from erreur

        sens = "Entrée" if p.amount > 0 else "Sortie"
        return Ligne(f"Caisse : {sens.lower()} de {_euros(abs(p.amount))} le {p.date:%d/%m/%Y}, « {data['label']} »{target}. "
                     "Financier › Comptes › Caisse.", faire)

    def prepare_manual(db, compte, org_id, p: ManualEntry) -> Ligne:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        debit, credit = plan(db, org_id, p.debit_account), plan(db, org_id, p.credit_account)
        if not season.start_date <= p.date.isoformat() <= season.end_date:
            raise Refus(f"la date doit être dans la saison {season.name}")
        data = {"date": p.date.isoformat(), "label": p.label, "debitAccountId": debit.id, "creditAccountId": credit.id, "amount": p.amount}

        def faire(db: Session) -> None:
            documents.add_manual_entry(db, member, season, data)

        return Ligne(f"Écriture à la main {season.name}, le {p.date:%d/%m/%Y} « {p.label.strip()} » : {_euros(p.amount)} au débit de "
                     f"{debit.number} {debit.label}, au crédit de {credit.number} {credit.label}. Bilan › Préparer, étape 4.", faire)

    def prepare_opening(db, compte, org_id, p: Opening) -> Ligne:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        current = _value_errors(documents.opening, db, member, season)
        if current["closed"]:
            raise Refus("saison clôturée : à rouvrir d'abord (par la personne, étape 7)")
        lines = {a["number"]: {"number": a["number"], "label": a["label"], "balance": a["balance"]} for a in current["accounts"]}
        source = ""
        if p.from_previous_balance:
            read = _value_errors(documents.previous_opening, db, member, season)
            lines = {n: {**l, "balance": 0} for n, l in lines.items()}
            for a in read["accounts"]:
                lines[a["number"]] = {"number": a["number"], "label": lines.get(a["number"], a)["label"], "balance": a["balance"]}
            source = f"lus dans « {read['file']} » ({read['previousSeason']})"
        elif not p.balances:
            raise Refus("donner balances ou from_previous_balance")
        for b in p.balances:
            number = b.number.strip()
            if number not in lines and not b.label:
                raise Refus(f"compte {number} absent des soldes de départ : donner son libellé")
            lines[number] = {"number": number, "label": b.label or lines[number]["label"], "balance": b.balance}
        accounts = sorted(lines.values(), key=lambda a: a["number"])
        total = round(sum(a["balance"] for a in accounts if a["number"] != "110"), 2)

        def faire(db: Session) -> None:
            documents.set_opening(db, member, season, accounts)

        shown = [f"{a['number']} {a['label']} {_euros(a['balance'])}" for a in accounts if a["balance"]]
        more = f" et {len(shown) - 10} autres" if len(shown) > 10 else ""
        return Ligne(f"Soldes de départ {season.name}{' ' + source if source else ''} : {' ; '.join(shown[:10]) or 'tous à zéro'}{more}. "
                     f"La différence ({_euros(-total)}) va dans 110 Report à nouveau. Comptes › ⋯ › Soldes de départ.", faire)

    def prepare_documents(db, compte, org_id, p: SeasonDocuments) -> Ligne:
        member = _member(db, compte, org_id)
        season = season_of(db, org_id, p.season)
        data = documents.season_documents(db, member, season)
        rows = {r["kind"]: r for r in data["rows"]}
        wanted: dict[str, str] = {}
        for c in p.choices:
            kind = c.document.strip().replace("_", "-")
            if kind not in rows and kind not in data["addable"]:
                raise Refus(f"document « {c.document} » pas proposé pour cette saison : " + ", ".join([*rows, *data["addable"]]))
            if c.choice == "same" and not (rows.get(kind) or {}).get("lastYear"):
                raise Refus(f"{LABELS[kind]} : pas de fichier l'an dernier, choisir new ou none")
            wanted[kind] = c.choice
        # Comme l'écran (DocumentsSaison.jsx) : un fichier de l'an dernier coché =
        # « Comme l'an dernier », un document ajouté coché = « Nouveau ».
        items = [
            {"nodeId": m["nodeId"], "name": m["name"], "kind": m["kind"],
             "selected": wanted[m["kind"]] == "same" if m["kind"] in wanted else m["selected"]}
            for m in data["models"]
        ]
        items += [
            {"nodeId": None, "name": "", "kind": kind, "selected": wanted.get(kind, (rows.get(kind) or {}).get("choice")) == "new"}
            for kind in [*rows, *(k for k in wanted if k not in rows)]
        ]

        def faire(db: Session) -> None:
            documents.set_document_choices(db, member, season, items)

        said = [f"{LABELS[k]} : {CHOICES[v]}" for k, v in wanted.items()]
        return Ligne(f"Documents {season.name} : {' ; '.join(said)}. Bilan › Préparer, étape 6 (« Produire » reste à l'écran).", faire)

    def read(name: str, description: str, params: type[BaseModel], fn) -> Action:
        return Action(name, "Financier", description, params, None, admin_only=False, read=fn)

    def write(name: str, module: str, description: str, params: type[BaseModel], fn) -> Action:
        return Action(name, module, description, params, fn, admin_only=False)

    return [
        read("finance_balance",
             "Financier › Comptes › Balance, avec ses puces Balance | Grand-livre | Compte de résultat, sur une saison et des "
             "dates choisies (Du, Au). view=compte_de_resultat : charges et produits par classe et par compte à côté de la saison "
             "d'avant sur les mêmes dates, résultat. Balance et Grand-livre : en direct, à toute date (finance_ag_document donne la "
             "saison entière).", Period, read_period),
        read("finance_preparation",
             "Financier › Bilan › Préparer, une partie pour une saison : etapes (les sept étapes et ce qui reste à faire : "
             "relevés, soldes de départ, transactions sans compte, hors banque, contrôles, écarts avec la saison d'avant), "
             "releves (grille des relevés par compte et par mois), soldes_depart, fin_annee (écritures de fin d'année proposées "
             "ou validées, choix conseillé et raison), ecritures_main, budget (budget prévisionnel de la saison suivante, réalisé "
             "en face) ou documents (étape 6 : chaque document, Comme l'an dernier / Nouveau / Non, nom du fichier).",
             Part, read_part),
        read("finance_cash", "Financier › Comptes › Caisse : solde et lignes de la caisse (la plus récente d'abord).", Limit, read_cash),
        read("finance_chart_proposals",
             "Financier › Comptes › ⋯ › Plan comptable › Proposer des comptes : les sous-comptes que l'appli propose d'après "
             "les transactions qui reviennent (numéro, nom, compte d'origine, nombre de transactions).", NoParams, read_proposals),
        write("set_season_budget", "Bilan",
              "Prépare ou modifie le budget prévisionnel de la saison suivante (Bilan › Préparer, étape 6) : montants prévus par "
              "compte, et/ou « Reprendre le réalisé ».", Budget, prepare_budget),
        write("validate_year_end_entries", "Bilan",
              "Valide les écritures de fin d'année d'une saison (Bilan › Préparer, étape 4, Engagement) : chaque ligne proposée "
              "prend le choix donné, sinon le choix conseillé (« Valider mes choix »).", YearEnd, prepare_year_end),
        write("create_proposed_accounts", "Financier",
              "Crée des comptes proposés par l'appli (Plan comptable › Proposer des comptes, « Créer les comptes cochés ») : "
              "leurs transactions y passent.", Proposals, prepare_proposals),
        write("correct_financial_statement", "Bilan",
              "Corrige le rapport financier déjà rédigé d'un bilan selon une consigne (« Ce qu'il faut changer », « Corriger ») : "
              "le modèle change le passage, le reste ne bouge pas, les chiffres restent ceux de l'appli.", Correction, prepare_correction),
        write("add_cash_line", "Financier",
              "Ajoute une ligne de caisse (Comptes › Caisse) : entrée ou sortie, compte du plan, ou retrait au distributeur.",
              CashLine, prepare_cash),
        write("add_manual_entry", "Bilan",
              "Ajoute une écriture à la main (Bilan › Préparer, étape 4, Engagement) : date dans la saison, libellé, compte débité, "
              "compte crédité (ni banque ni caisse), montant.", ManualEntry, prepare_manual),
        write("set_opening_balances", "Financier",
              "Saisit les soldes de départ d'une saison (Comptes › ⋯ › Soldes de départ, Engagement) : soldes donnés, ou lus dans "
              "la Balance de l'an dernier déposée dans Docs › Financier ; la différence va dans 110.", Opening, prepare_opening),
        write("set_season_documents", "Bilan",
              "Choisit pour des documents de la saison (Bilan › Préparer, étape 6) : Comme l'an dernier, Nouveau ou Non. "
              "Un document « Ajouter un document » (honoraires, fec) se prend avec new.", SeasonDocuments, prepare_documents),
    ]
