"""Les documents du bilan d'une saison d'après ceux de l'an dernier (spec
financier.md §8.10, étape 6, Seb 10/11/2026).

Chaque fichier du Bilan financier de la saison précédente est reconnu d'après
son contenu d'abord (titre d'une Balance, d'un Grand livre…), son nom ensuite :
quelqu'un peut avoir pris des libertés avec les noms. Règles fixes, pas de
modèle : l'appli propose, la trésorière corrige. Le document de cette saison
prend le nom de celui de l'an dernier, les années avancées d'un an.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# Natures que l'appli sait produire (ag_documents.KINDS, plus le Rapport
# financier rédigé), et « autre » : à faire à la main.
RAPPORT = "rapport"
OTHER = "autre"
LABELS = {
    "synthese": "Synthèse Dépenses-Recettes",
    "balance": "Balance",
    "grand-livre": "Grand livre",
    "bilan": "Bilan actif-passif",
    "honoraires": "Honoraires par professeur",
    "fec": "FEC",
    RAPPORT: "Rapport financier",
    OTHER: "Autre : à faire à la main",
}
FORMATS = {"synthese": "xlsx", "balance": "pdf", "grand-livre": "pdf", "bilan": "pdf", "honoraires": "xlsx", "fec": "txt", RAPPORT: "docx"}
# La première année, sans rien dans Docs.
BASE = ["synthese", "balance", RAPPORT]

# Dans l'ordre : un Grand livre contient souvent le mot « balance », un
# rapport parle de recettes et de dépenses.
_RULES = [
    ("grand-livre", ("grand-livre", "grand livre", "grandlivre")),
    ("fec", ("fichier des ecritures", "fec")),
    ("balance", ("balance",)),
    ("bilan", ("actif", "passif")),
    ("honoraires", ("honoraires", "das-2", "das2")),
    (RAPPORT, ("rapport",)),
    ("synthese", ("recettes", "depenses", "synthese", "compte de resultat")),
]


def _plain(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _content(path: Path, name: str) -> str:
    """Le début du fichier en texte (première page, premières lignes), ou ""."""
    suffix = Path(name).suffix.lower()
    try:
        if suffix == ".pdf":
            import pymupdf

            with pymupdf.open(path) as doc:
                return doc[0].get_text()[:1500] if doc.page_count else ""
        if suffix in (".xlsx", ".xlsm"):
            from openpyxl import load_workbook

            sheet = load_workbook(path, read_only=True, data_only=True).worksheets[0]
            cells = [str(c) for row in sheet.iter_rows(max_row=8, values_only=True) for c in row if c is not None]
            return " ".join(cells)[:1500]
        if suffix == ".docx":
            import docx

            return " ".join(p.text for p in docx.Document(str(path)).paragraphs[:15])[:1500]
        if suffix == ".txt":
            return path.read_text(encoding="latin-1", errors="ignore")[:300]
    except Exception:  # fichier abîmé ou illisible : le nom seul décide
        return ""
    return ""


def _match(text: str) -> str | None:
    for kind, words in _RULES:
        if kind == "bilan":
            if all(w in text for w in words):
                return kind
        elif kind == "fec":
            if words[0] in text or re.search(r"\bfec\b", text):
                return kind
        elif any(w in text for w in words):
            return kind
    return None


def recognize(name: str, path: Path | None) -> str:
    """La nature d'un document de l'an dernier : contenu d'abord, nom ensuite."""
    content = _plain(_content(path, name)) if path is not None else ""
    # Le titre (le haut de la première page) d'abord : un rapport parle aussi de la Balance.
    return _match(content[:300]) or _match(content) or _match(_plain(Path(name).stem)) or OTHER


def next_name(previous: str, kind: str) -> str:
    """Le nom de l'an dernier, chaque année avancée d'un an, au format produit
    par l'appli : « Balance 2024-2025.pdf » → « Balance 2025-2026.pdf »,
    « Rapport financier AG2025.doc » → « Rapport financier AG2026.docx »."""
    stem = Path(previous).stem
    stem = re.sub(r"(?<!\d)(19|20)(\d{2})(?!\d)", lambda m: str(int(m.group(0)) + 1), stem)
    return f"{stem}.{FORMATS.get(kind, Path(previous).suffix.lstrip('.') or 'pdf')}"


def default_name(kind: str, season_name: str) -> str:
    """Nom d'un document sans modèle de l'an dernier."""
    return f"{LABELS[kind]} {season_name}.{FORMATS[kind]}"
