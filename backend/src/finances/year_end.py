"""Écritures de fin d'année (financier.md §8.14, Seb 20/11 ; Engagement) :
ce qui ne tombe pas sur la bonne saison. L'appli repère, par règles fixes
(pas de modèle), quatre natures d'écriture :

- charge payée d'avance : une dépense payée une fois par an, dont une partie
  des douze mois tombe après la fin de la saison (486) ;
- produit reçu d'avance : les cotisations encaissées les deux derniers mois
  de la saison, en général celles de la saison suivante (487) ;
- facture pas encore reçue : une dépense payée chaque mois de la saison sauf
  le dernier (408) ;
- amortissement : un achat de matériel de 500 € ou plus (2154, 28154, 6811).

La trésorière choisit ligne par ligne, puis valide : seuls ses choix sont
écrits (`fin_year_end_entries`). Les écritures elles-mêmes ne sont pas
stockées : `lines` les recalcule pour une saison, comme le reste du grand
livre (§8.7). Montants en centimes.
"""

from __future__ import annotations

import datetime as dt
from statistics import median

from .chart import label_key
from .models import EXPENSE, INCOME, SUSPENSE

PREPAID_EXPENSE, PREPAID_INCOME, INVOICE_DUE, DEPRECIATION = "prepaid_expense", "prepaid_income", "invoice_due", "depreciation"
TITLES = {
    PREPAID_EXPENSE: "Charge payée d'avance",
    PREPAID_INCOME: "Produit reçu d'avance",
    INVOICE_DUE: "Facture pas encore reçue",
    DEPRECIATION: "Amortissement",
}
# Les comptes que ces écritures mouvementent : (libellé, nature de calcul, rubrique du plan).
ACCOUNTS = {
    "486": ("Charges constatées d'avance", SUSPENSE, "48 Charges et produits constatés d'avance"),
    "487": ("Produits constatés d'avance", SUSPENSE, "48 Charges et produits constatés d'avance"),
    "408": ("Fournisseurs, factures non parvenues", SUSPENSE, "40 Fournisseurs"),
    "2154": ("Matériel", SUSPENSE, "21 Immobilisations corporelles"),
    "28154": ("Amortissements du matériel", SUSPENSE, "28 Amortissements des immobilisations"),
    "6811": ("Dotations aux amortissements", EXPENSE, "68 Dotations aux amortissements et provisions"),
}
COUNTERPART = {PREPAID_EXPENSE: "486", PREPAID_INCOME: "487", INVOICE_DUE: "408"}
ASSET, DEPRECIATED, ALLOWANCE = "2154", "28154", "6811"
YEARS = (3, 5, 10)
DEFAULT_YEARS = 5
SMALL = 100_00  # en dessous, « Laisser » est conseillé : cela ne change presque rien au résultat
DEPRECIATION_FROM = 500_00
EQUIPMENT_PREFIX = "606"  # fournitures et petit équipement : là où un achat de matériel est classé
SUBSCRIPTION_PREFIX = "756"  # cotisations
BANK_WORDS = {"VIR", "VIREMENT", "SEPA", "INST", "PRLV", "PRELEVEMENT", "CARTE", "CB", "PAIEMENT", "ACHAT", "FACT", "FACTURE", "RECU", "EMIS"}
MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def month_index(day: dt.date) -> int:
    return day.year * 12 + day.month - 1


def month_name(index: int) -> str:
    """« sept. 2026 »."""
    return f"{MONTHS[index % 12]} {index // 12}"


def needed_accounts(kind: str) -> tuple[str, ...]:
    return (ASSET, DEPRECIATED, ALLOWANCE) if kind == DEPRECIATION else (COUNTERPART[kind],)


def advised(kind: str, amount: int) -> bool:
    """Le choix conseillé : compter (ou étaler), sauf les petits montants."""
    return kind == DEPRECIATION or amount >= SMALL


def allowance(amount: int, bought: dt.date, years: int, start: dt.date, end: dt.date) -> int:
    """La dotation de la période pour un bien acheté `amount`, amorti en
    linéaire sur `years` ans à partir du mois d'achat. La somme des saisons
    fait exactement le prix d'achat."""
    total = years * 12
    first = month_index(bought)

    def cumulated(months: int) -> int:
        return round(amount * min(max(months, 0), total) / total)

    return cumulated(month_index(end) - first + 1) - cumulated(month_index(start) - first)


def effect(kind: str, amount: int, dotation: int = 0) -> int:
    """Ce que l'écriture fait au résultat de la saison (positif = l'améliore)."""
    if kind == PREPAID_EXPENSE:
        return amount
    if kind == DEPRECIATION:
        return amount - dotation
    return -amount


def lines(entries, numbers: dict[int, str], season_id: int, start: dt.date, end: dt.date, previous_id: int | None) -> list[tuple[dt.date, str, str, str, int]]:
    """Les écritures d'une saison, (date, libellé, compte débité, compte
    crédité, montant), depuis les choix gardés : celles de la saison au
    dernier jour, leur reprise au premier jour de la saison suivante
    (`previous_id` : la saison d'avant, donnée seulement si elle est clôturée,
    donc si ses soldes sont reportés), la dotation de chaque saison de la vie
    d'un bien. `numbers` : numéro de chaque compte du plan par id."""
    out = []
    for e in entries:
        account = numbers.get(e.account_id)
        if not e.keep or account is None:
            continue
        if e.kind == DEPRECIATION:
            if e.season_id == season_id:
                out.append((e.date, f"Immobilisation : {e.label}", ASSET, account, e.amount))
            dotation = allowance(e.amount, e.date, e.years or DEFAULT_YEARS, start, end) if e.date <= end else 0
            if dotation:
                out.append((end, f"Amortissement : {e.label}", ALLOWANCE, DEPRECIATED, dotation))
            continue
        other = COUNTERPART[e.kind]
        debit, credit = (other, account) if e.kind == PREPAID_EXPENSE else (account, other)
        if e.season_id == season_id:
            out.append((end, f"{TITLES[e.kind]} : {e.label}", debit, credit, e.amount))
        elif e.season_id == previous_id:
            out.append((start, f"Reprise : {e.label}", credit, debit, e.amount))
    return out


def _name(label: str) -> str:
    return " ".join(w for w in label_key(label).split() if w not in BANK_WORDS)


def _fr(day: dt.date) -> str:
    return day.strftime("%d/%m/%Y")


def _eur(cents: int) -> str:
    return f"{cents / 100:,.2f}".replace(",", " ").replace(".", ",") + " €"


def candidates(operations: list[dict], start: dt.date, end: dt.date, next_name: str) -> list[dict]:
    """Ce que l'appli propose pour la saison. `operations` : les transactions
    bancaires classées dans un seul compte de dépenses ou de recettes, toutes
    saisons confondues : {id, date, label, amount (centimes, signé), accountId,
    number, accountLabel, nature}. Rend {key, kind, label, text, reason, date,
    amount, accountId}."""
    last = month_index(end)
    season_months = list(range(month_index(start), last + 1))
    expenses = [o for o in operations if o["nature"] == EXPENSE and o["amount"] < 0]
    in_season = [o for o in expenses if start <= o["date"] <= end]
    by_name: dict[str, list[dict]] = {}
    for o in expenses:
        name = _name(o["label"])
        if name:
            by_name.setdefault(name, []).append(o)
    out = []
    for name, same in by_name.items():
        here = [o for o in same if start <= o["date"] <= end]
        title = name.title()
        # Payée une fois par an (une seule fois dans la saison, et une fois un an plus tôt).
        if len(here) == 1:
            o = here[0]
            days = [(o["date"] - p["date"]).days for p in same if p["date"] < o["date"]]
            after = month_index(o["date"]) + 11 - last
            if any(330 <= d <= 400 for d in days) and not any(d < 330 for d in days) and 0 < after < 12:
                part = round(-o["amount"] * after / 12)
                out.append({
                    "key": f"{PREPAID_EXPENSE}:{o['id']}", "kind": PREPAID_EXPENSE, "label": title, "date": o["date"], "amount": part, "accountId": o["accountId"],
                    "text": f"{title}, {_eur(-o['amount'])} payés le {_fr(o['date'])} pour un an. {after} mois sur 12 concernent {next_name}.",
                    "reason": f"Concerne {month_name(last + 1)} à {month_name(month_index(o['date']) + 11)}.",
                })
        # Payée chaque mois de la saison, sauf le dernier.
        paid = {month_index(o["date"]) for o in here}
        if len(season_months) >= 6 and paid == set(season_months[:-1]):
            latest = max(here, key=lambda o: o["date"])
            out.append({
                "key": f"{INVOICE_DUE}:{name}"[:80], "kind": INVOICE_DUE, "label": title, "date": end,
                "amount": round(median(-o["amount"] for o in here)), "accountId": latest["accountId"],
                "text": f"{title} : payé chaque mois de la saison, rien en {month_name(last)}.",
                "reason": f"Concerne {month_name(last)}.",
            })
    # Les cotisations encaissées les deux derniers mois de la saison.
    late: dict[int, list[dict]] = {}
    for o in operations:
        if o["nature"] == INCOME and o["amount"] > 0 and o["number"].startswith(SUBSCRIPTION_PREFIX) and start <= o["date"] <= end and month_index(o["date"]) >= last - 1:
            late.setdefault(o["accountId"], []).append(o)
    for account_id, ops in late.items():
        total = sum(o["amount"] for o in ops)
        out.append({
            "key": f"{PREPAID_INCOME}:{account_id}", "kind": PREPAID_INCOME, "label": ops[0]["accountLabel"], "date": end, "amount": total, "accountId": account_id,
            "text": f"{ops[0]['accountLabel']} : {_eur(total)} encaissés en {month_name(last - 1)} et {month_name(last)} ({len(ops)} transaction{'s' if len(ops) > 1 else ''}).",
            "reason": f"En fin de saison, ce sont en général les cotisations de {next_name}.",
        })
    # Un achat de matériel de 500 € ou plus.
    for o in in_season:
        if -o["amount"] >= DEPRECIATION_FROM and o["number"].startswith(EQUIPMENT_PREFIX):
            title = _name(o["label"]).title() or o["label"]
            out.append({
                "key": f"{DEPRECIATION}:{o['id']}", "kind": DEPRECIATION, "label": title, "date": o["date"], "amount": -o["amount"], "accountId": o["accountId"],
                "text": f"{title}, {_eur(-o['amount'])} achetés le {_fr(o['date'])}. Un achat de plus de 500 € qui sert plusieurs années se répartit sur sa durée.",
                "reason": "Plus de 500 € et sert plusieurs saisons.",
            })
    for c in out:
        if not advised(c["kind"], c["amount"]):
            c["reason"] = "Moins de 100 € : cela ne change presque rien au résultat."
    order = [PREPAID_EXPENSE, PREPAID_INCOME, INVOICE_DUE, DEPRECIATION]
    return sorted(out, key=lambda c: (order.index(c["kind"]), -c["amount"]))
