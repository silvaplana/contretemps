"""« Comme l'an dernier » avec la présentation de l'an dernier (financier.md
§8.10, étape 6, Seb 20/11) : le fichier Excel de la saison précédente sert de
gabarit.

Le modèle regarde le fichier **une fois** et dit, pour chaque case qui porte
un montant tapé à la main, quels chiffres de l'appli elle additionne (clés de
`figures`). Ce repérage est gardé (`fin_document_templates`). Ensuite l'appli
seule produit le document : elle recopie le fichier, avance les années dans
les textes et **pose elle-même chaque montant**. Les formules du fichier sont
gardées. Une case sans source est vidée et signalée ; un compte de l'appli
qui n'apparaît nulle part aussi.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import tempfile
import unicodedata
from pathlib import Path

import anthropic
from openpyxl import load_workbook

from .ai import AnalysisError, cost_usd
from .slides import soffice

MODEL = "claude-opus-5-5"
INSTRUCTIONS = """Tu lis le tableau Excel qu'une trésorière d'association a fait l'an dernier pour présenter \
ses comptes (recettes, dépenses, trésorerie). L'application doit refaire le même tableau cette année en \
posant elle-même les montants. Pour chaque case qui contient un montant tapé à la main (pas une formule), \
dis quels chiffres de l'application elle représente.

Tu reçois les cases du tableau (« case | contenu ») et la liste des chiffres disponibles (« clé | libellé »). \
Pour chaque case à montant, rends :
- « cell » : la case (ex. C14) ;
- « label » : le libellé de la ligne tel qu'écrit dans le tableau ;
- « keys » : les clés à additionner pour cette case. Plusieurs clés si la ligne regroupe plusieurs comptes. \
Une liste vide si aucun chiffre disponible ne correspond (détail tenu à la main, par exemple) : ne force jamais.
Chaque clé ne sert qu'une fois, sauf si le tableau répète visiblement le même montant ailleurs. \
N'invente aucune clé. Ne rends pas les cases à formule ni les cases de texte."""

SCHEMA = {
    "type": "object",
    "properties": {
        "cells": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "cell": {"type": "string"},
                    "label": {"type": "string"},
                    "keys": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["cell", "label", "keys"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["cells"],
    "additionalProperties": False,
}

_SEASON = re.compile(r"(?<!\d)(20\d{2})(\s?[/\-–]\s?)(20\d{2}|\d{2})(?!\d)")
_DATE = re.compile(r"(?<!\d)(\d{2}/\d{2}/)(\d{2}|20\d{2})(?!\d)")


def _slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def next_year(text: str) -> str:
    """« 2024/2025 » → « 2025/2026 », « 31/08/25 » → « 31/08/26 »."""

    def season(m: re.Match) -> str:
        end = m.group(3)
        return f"{int(m.group(1)) + 1}{m.group(2)}{int(end) + 1:0{len(end)}d}"

    def date(m: re.Match) -> str:
        year = m.group(2)
        return f"{m.group(1)}{(int(year) + 1) % (100 if len(year) == 2 else 10000):0{len(year)}d}"

    return _DATE.sub(date, _SEASON.sub(season, text))


def to_xlsx(path: Path, name: str) -> bytes | None:
    """Le fichier en .xlsx : tel quel, ou converti par LibreOffice (.xls, .ods).
    None s'il n'est pas un tableur ou si la conversion échoue."""
    suffix = Path(name).suffix.lower()
    if suffix in (".xlsx", ".xlsm"):
        return path.read_bytes()
    if suffix not in (".xls", ".ods"):
        return None
    program = soffice()
    if program is None:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / f"source{suffix}"
        source.write_bytes(path.read_bytes())
        try:
            subprocess.run(
                [program, f"-env:UserInstallation=file://{tmp}/profile", "--headless", "--convert-to", "xlsx", "--outdir", tmp, str(source)],
                check=True, capture_output=True, timeout=120,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        out = Path(tmp) / "source.xlsx"
        return out.read_bytes() if out.exists() else None


def figures(synthese: dict, fees: list[dict]) -> dict[str, dict]:
    """Les chiffres que l'appli sait poser, par clé : {clé: {"label", "value"}}.
    Comptes de charges et de produits, honoraires par professeur, trésorerie,
    totaux, événements."""
    out: dict[str, dict] = {}
    for side, word in (("charges", "Charge"), ("produits", "Produit")):
        for group in synthese[side]:
            for line in group["lines"]:
                out[f"compte.{line['number']}"] = {"label": f"{word} {line['number']} {line['label']}", "value": line["amount"], "account": True}
    by_person: dict[str, float] = {}
    for f in fees:
        by_person[f["person"]] = by_person.get(f["person"], 0.0) + f["amount"]
    for person, amount in by_person.items():
        out[f"honoraires.{_slug(person)}"] = {"label": f"Honoraires versés à {person}", "value": round(amount, 2)}
    for t in synthese["treasury"]:
        out[f"tresorerie.{_slug(t['label'])}"] = {"label": f"Trésorerie : {t['label']}", "value": t["amount"]}
    out["tresorerie.total"] = {"label": "Trésorerie, total", "value": synthese["treasuryTotal"]}
    out["fournisseurs-a-payer"] = {"label": "Fournisseurs à payer", "value": synthese["unpaidTotal"]}
    out["total.charges"] = {"label": "Total des charges", "value": synthese["totalCharges"]}
    out["total.produits"] = {"label": "Total des produits", "value": synthese["totalProduits"]}
    out["resultat"] = {"label": "Résultat (produits moins charges)", "value": synthese["result"]}
    for e in synthese["events"]:
        slug = _slug(e["event"])
        out[f"evenement.{slug}.ressources"] = {"label": f"Ressources {e['event']}", "value": e["resources"]}
        out[f"evenement.{slug}.cout"] = {"label": f"Coût {e['event']}", "value": e["cost"]}
        out[f"evenement.{slug}.benefice"] = {"label": f"Bénéfice {e['event']}", "value": e["profit"]}
    return out


def _typed_amounts(wb) -> dict[str, float]:
    """Les cases à montant tapé (pas une formule) de la première feuille."""
    return {
        c.coordinate: c.value
        for row in wb.worksheets[0].iter_rows()
        for c in row
        if isinstance(c.value, (int, float)) and not isinstance(c.value, bool)
    }


def listing(xlsx: bytes) -> str:
    """Les cases de la première feuille, « case | contenu », pour le modèle."""
    ws = load_workbook(io.BytesIO(xlsx)).worksheets[0]
    return "\n".join(f"{c.coordinate} | {c.value}" for row in ws.iter_rows() for c in row if c.value is not None)


def fill(xlsx: bytes, mapping: list[dict], available: dict[str, dict]) -> tuple[bytes, list[str]]:
    """Le fichier de l'an dernier, années avancées et montants posés par l'appli.
    Rend (fichier, à vérifier) : cases sans source (vidées), comptes de
    l'appli qui ne sont posés nulle part."""
    wb = load_workbook(io.BytesIO(xlsx))
    ws = wb.worksheets[0]
    by_cell = {m["cell"].upper(): m for m in mapping}
    warnings: list[str] = []
    used: set[str] = set()
    for coordinate in _typed_amounts(wb):
        entry = by_cell.get(coordinate)
        keys = [k for k in (entry or {}).get("keys", []) if k in available]
        if keys:
            ws[coordinate].value = round(sum(available[k]["value"] for k in keys), 2)
            used.update(keys)
        else:
            ws[coordinate].value = None
            label = (entry or {}).get("label") or coordinate
            warnings.append(f"« {label} » (case {coordinate}) : pas de chiffre dans l'appli, à compléter à la main.")
    for row in ws.iter_rows():
        for c in row:
            if isinstance(c.value, str) and not c.value.startswith("="):
                c.value = next_year(c.value)
    # Un compte qui a un montant et n'est posé nulle part fausserait les totaux du fichier.
    for key, f in available.items():
        if f.get("account") and f["value"] and key not in used:
            amount = f"{f['value']:,.2f}".replace(",", " ").replace(".", ",")
            warnings.append(f"{f['label']} ({amount} €) n'a pas de ligne dans ce tableau : à ajouter à la main.")
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue(), warnings


class PresentationReader:
    """Le repérage, fait une fois par fichier, par le modèle."""

    def __init__(self, note_cost=None, limit_reached=None, client: anthropic.Anthropic | None = None) -> None:
        """note_cost(db, org_id, dollars, détail) ; limit_reached(db, org_id)."""
        self.note_cost, self.limit_reached, self._client = note_cost, limit_reached, client

    def read(self, db, org_id: int, xlsx: bytes, name: str, available: dict[str, dict]) -> tuple[list[dict], float]:
        """[{cell, label, keys}] pour les cases à montant du fichier, et le coût."""
        if self.limit_reached is not None and self.limit_reached(db, org_id):
            raise AnalysisError("Le plafond mensuel de l'association est atteint : choisissez « Nouveau » pour ce document.")
        text = (
            f"Tableau « {name} » :\n{listing(xlsx)}\n\nChiffres disponibles (clé | libellé) :\n"
            + "\n".join(f"{key} | {f['label']}" for key, f in available.items())
        )
        try:
            client = self._client or anthropic.Anthropic()
            with client.beta.messages.stream(
                model=MODEL, max_tokens=8000, system=INSTRUCTIONS, messages=[{"role": "user", "content": text}],
                output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            ) as stream:
                response = stream.get_final_message()
        except Exception as exc:  # noqa: BLE001 - toute erreur de l'appel en message clair
            raise AnalysisError(f"La présentation n'a pas pu être préparée : {exc}") from exc
        cost = cost_usd(response.model or MODEL, response.usage)
        if cost and self.note_cost is not None:
            self.note_cost(db, org_id, cost, f"Présentation de « {name} »")
        block = next((b.text for b in response.content if b.type == "text"), None)
        try:
            cells = json.loads(block or "")["cells"]
        except (ValueError, KeyError, TypeError) as exc:
            raise AnalysisError("La présentation n'a pas pu être préparée.", cost) from exc
        typed = _typed_amounts(load_workbook(io.BytesIO(xlsx)))
        return [c for c in cells if str(c.get("cell", "")).upper() in typed], cost
