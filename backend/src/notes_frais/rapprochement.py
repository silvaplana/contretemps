"""Rapprochement des pièces (notes-de-frais.md §7 sexies) : l'état des pièces
d'une période face aux lignes du compte, en PDF, à tout moment. Ce que le
validateur comptable demande : chaque pièce et la ligne qui la paie, ce
qui attend, et les débits sans pièce."""

from __future__ import annotations

import html
import io
from datetime import date

import pymupdf

_CSS = """
* { font-family: sans-serif; }
body { font-size: 9pt; color: #222; }
h1 { font-size: 15pt; margin: 0 0 2pt; }
h2 { font-size: 11pt; margin: 10pt 0 4pt; }
p { margin: 2pt 0; }
.muted { color: #666; }
table { border-collapse: collapse; width: 100%; margin-top: 4pt; }
th, td { border-bottom: 1px solid #ccc; padding: 2pt 4pt; text-align: left; vertical-align: top; }
th { background: #eef; }
td.n, th.n { text-align: right; white-space: nowrap; }
tr.total td { font-weight: bold; border-top: 1px solid #666; }
"""


def _fr(jour: date | None) -> str:
    return jour.strftime("%d/%m/%Y") if jour else ""


def _eur(centimes: int) -> str:
    signe = "-" if centimes < 0 else ""
    centimes = abs(centimes)
    return f"{signe}{centimes // 100:,}".replace(",", " ") + f",{centimes % 100:02d} €"


_REGLE = {"refund": "remboursement attendu", "pay_rest": "reste dû à payer", "write_off": "abandonné"}


def _ecart(p: dict) -> str:
    if not p["ecart_centimes"]:
        return ""
    regle = _REGLE.get(p.get("ecart_regle") or "")
    return _eur(p["ecart_centimes"]) + (f" · {regle}" if regle else "")


def pdf(donnees: dict) -> bytes:
    """Le PDF (A4 portrait) du dict rendu par `NotesDeFrais.rapprochement`."""
    e = html.escape
    debut, fin = donnees["debut"], donnees["fin"]
    rattachees, sans_piece = donnees["rattachees"], donnees["lignes_sans_piece"]
    # Les paires proposées attendent aussi un paiement rattaché : dans la même partie du PDF.
    sans_paiement = sorted(donnees.get("paires", []) + donnees["sans_paiement"], key=lambda p: p["date"])
    parts = [
        f"<h1>Rapprochement des pièces</h1>",
        f"<p class='muted'>Du {_fr(debut)} au {_fr(fin)}, fait le {_fr(date.today())}. "
        f"{len(rattachees)} pièce(s) rattachée(s) à une ligne du compte, {len(sans_paiement)} sans paiement rattaché, "
        f"{len(sans_piece)} ligne(s) de débit sans pièce.</p>",
        "<h2>Pièces payées, et la ligne du compte qui les paie</h2>",
    ]
    if rattachees:
        lignes = "".join(
            f"<tr><td>{_fr(p['date'])}</td><td>{e(p['nature'])}</td><td>{e(p['qui'])}</td><td class='n'>{_eur(p['montant_centimes'])}</td>"
            f"<td>{_fr(p['ligne']['date'])} · {e(p['ligne']['libelle'])}{' · ' + e(p['ligne']['compte']) if p['ligne']['compte'] else ''}</td>"
            f"<td class='n'>{_eur(-p['ligne']['montant_centimes'])}</td><td class='n'>{_ecart(p)}</td></tr>"
            for p in rattachees
        )
        parts.append(
            "<table><tr><th>Date</th><th>Nature</th><th>Qui</th><th class='n'>Montant</th><th>Ligne du compte</th><th class='n'>Payé</th><th class='n'>Écart</th></tr>"
            + lignes
            + f"<tr class='total'><td colspan='3'>Total</td><td class='n'>{_eur(sum(p['montant_centimes'] for p in rattachees))}</td><td></td><td></td><td></td></tr></table>"
        )
    else:
        parts.append("<p class='muted'>Aucune.</p>")
    parts.append("<h2>Pièces sans paiement rattaché</h2>")
    if sans_paiement:
        parts.append(
            "<table><tr><th>Date</th><th>Nature</th><th>Qui</th><th class='n'>Montant</th><th>État</th></tr>"
            + "".join(
                f"<tr><td>{_fr(p['date'])}</td><td>{e(p['nature'])}</td><td>{e(p['qui'])}</td><td class='n'>{_eur(p['montant_centimes'])}</td><td>{e(p['etat'])}</td></tr>"
                for p in sans_paiement
            )
            + "</table>"
        )
    else:
        parts.append("<p class='muted'>Aucune : toutes les pièces de la période sont payées et rattachées.</p>")
    parts.append("<h2>Lignes de débit du compte sans pièce</h2>")
    if sans_piece:
        parts.append(
            "<table><tr><th>Date</th><th>Libellé</th><th>Compte</th><th class='n'>Montant</th></tr>"
            + "".join(
                f"<tr><td>{_fr(l['date'])}</td><td>{e(l['libelle'])}</td><td>{e(l['compte'])}</td><td class='n'>{_eur(-l['montant_centimes'])}</td></tr>"
                for l in sans_piece
            )
            + "</table>"
        )
    else:
        parts.append("<p class='muted'>Aucune.</p>")
    return _html_to_pdf("".join(parts))


def _html_to_pdf(body: str) -> bytes:
    buffer = io.BytesIO()
    page = pymupdf.paper_rect("a4")
    where = page + (36, 36, -36, -36)
    story = pymupdf.Story(html=body, user_css=_CSS)
    writer = pymupdf.DocumentWriter(buffer)
    more = True
    while more:
        device = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    return buffer.getvalue()
