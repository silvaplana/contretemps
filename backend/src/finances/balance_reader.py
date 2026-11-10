"""Lecture d'une Balance en PDF (celle du logiciel de la trésorière, ou la
nôtre, §8.6) pour en reprendre les soldes de départ de la saison suivante
(financier.md §8.7, Seb 10 novembre 2026).

Chaque ligne de compte est : numéro, intitulé, Total Période débit / crédit,
Solde Période débit / crédit. Les montants sont lus par leur position : les
deux colonnes de droite de l'en-tête « Débit » / « Crédit » sont le solde. Ne
sont gardés que les comptes de bilan (classes 1 à 5) à solde non nul, hors
report à nouveau et résultat (110, 120, 129), que la clôture recalcule.
"""
from __future__ import annotations

import base64
import logging
import re
from collections.abc import Callable
from pathlib import Path

import anthropic
import pymupdf
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)
MODELE = "claude-opus-5-5"
CONSIGNE = (
    "Tu lis la Balance comptable d'une association (document d'un logiciel de comptabilité, photo ou PDF). "
    "Rends chaque compte de bilan (numéro commençant par 1, 2, 3, 4 ou 5) avec son numéro, son intitulé et son "
    "SOLDE de fin de période signé : positif si le solde est débiteur, négatif s'il est créditeur. Ignore les "
    "comptes de charges et de produits (6 et 7), les totaux, le report à nouveau (110) et le résultat (120, 129). "
    "Ne devine rien : un compte dont le solde n'est pas lisible est omis."
)

_MONTANT = re.compile(r"^\d{1,3}(?: \d{3})*,\d{2}$|^\d+,\d{2}$")
_EXCLUS = ("110", "12")  # report à nouveau, résultat de l'exercice


def read_balance(path: Path) -> list[tuple[str, str, int]]:
    """[(numéro, intitulé, solde signé en centimes)] : positif = débiteur."""
    out: list[tuple[str, str, int]] = []
    try:
        for page in pymupdf.open(path):
            out.extend(_read_page(page))
    except Exception:  # photo, scan, fichier abîmé : rien par les colonnes
        logger.info("Balance « %s » : colonnes illisibles", path.name)
        return []
    return out


def _read_page(page) -> list[tuple[str, str, int]]:
    words = page.get_text("words")
    rows: dict[int, list] = {}
    for w in words:
        rows.setdefault(round(w[1] / 3), []).append(w)
    colonnes: list[float] = []  # centres des quatre colonnes Débit / Crédit, de gauche à droite
    for row in rows.values():
        textes = [w[4] for w in row]
        if textes.count("Débit") >= 2 and textes.count("Crédit") >= 2:
            colonnes = sorted((w[0] + w[2]) / 2 for w in row if w[4] in ("Débit", "Crédit"))[-4:]
            break
    if len(colonnes) < 4:
        return []
    out = []
    for row in sorted(rows.values(), key=lambda r: r[0][1]):
        row = sorted(row, key=lambda w: w[0])
        numero = row[0][4]
        if not numero.isdigit() or numero[0] not in "12345" or numero.startswith(_EXCLUS):
            continue
        amounts = _amounts(row[1:])
        premier = min((x0 for x0, _, _ in amounts), default=10_000)
        label = " ".join(w[4] for w in row[1:] if w[2] <= premier)
        solde = 0
        for x0, x1, cents in amounts:
            colonne = min(range(4), key=lambda i: abs((x0 + x1) / 2 - colonnes[i]))
            if colonne == 2:
                solde += cents
            elif colonne == 3:
                solde -= cents
        if solde:
            out.append((numero, label.strip(), solde))
    return out


def _amounts(words) -> list[tuple[float, float, int]]:
    """Les montants d'une ligne (x de début, x de fin, centimes) : « 4 » et
    « 089,26 » côte à côte sont un seul montant."""
    out: list[tuple[float, float, int]] = []
    pending: tuple[str, float, float] | None = None
    for w in words:
        t = w[4]
        if t.isdigit() and pending is None and w[0] > 250:
            pending = (t, w[0], w[2])
            continue
        x0 = w[0]
        if pending is not None:
            if re.match(r"^\d{3},\d{2}$", t) and w[0] - pending[2] < 4:
                t, x0 = pending[0] + t, pending[1]
            pending = None
        if _MONTANT.match(t):
            out.append((x0, w[2], int(t.replace(" ", "").replace(",", ""))))
    return out


class _CompteLu(BaseModel):
    numero: str = Field(description="Numéro du compte, chiffres seulement")
    intitule: str = Field(description="Intitulé du compte tel qu'écrit")
    solde: float = Field(description="Solde de fin de période en euros, signé : positif débiteur, négatif créditeur")


class _BalanceLue(BaseModel):
    comptes: list[_CompteLu]


class BalanceModelReader:
    """Quand les colonnes ne se lisent pas (autre logiciel, scan, photo) : le
    même lecteur que les factures lit la Balance ; à l'écran c'est « lu par
    l'appli, à vérifier », le trésorier confirme (Seb, 10/11)."""

    def __init__(
        self,
        noter_cout: Callable[[Session, int, float, str], None] | None = None,
        plafond_atteint: Callable[[Session, int], bool] | None = None,
        client: anthropic.Anthropic | None = None,
    ) -> None:
        self.noter_cout, self.plafond_atteint, self._client = noter_cout, plafond_atteint, client

    def read(self, db: Session, org_id: int, path: Path, name: str) -> list[tuple[str, str, int]]:
        if self.plafond_atteint is not None and self.plafond_atteint(db, org_id):
            raise ValueError("Le plafond mensuel d'IA de l'association est atteint : saisissez les soldes à la main.")
        suffix = path.suffix.lower()
        media = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}.get(suffix)
        if media is None:
            raise ValueError(f"« {name} » n'est ni un PDF ni une photo : saisissez les soldes à la main.")
        source = {"type": "base64", "media_type": media, "data": base64.standard_b64encode(path.read_bytes()).decode("ascii")}
        bloc = {"type": "document" if media == "application/pdf" else "image", "source": source}
        try:
            client = self._client or anthropic.Anthropic()
            reponse = client.beta.messages.parse(
                model=MODELE, max_tokens=4000, system=CONSIGNE,
                messages=[{"role": "user", "content": [bloc, {"type": "text", "text": f"Fichier : {name}"}]}],
                output_config={"effort": "low"}, output_format=_BalanceLue,
                betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            )
        except anthropic.APIError as erreur:
            logger.exception("Lecture de la Balance impossible")
            raise ValueError("La Balance n'a pas pu être lue : saisissez les soldes à la main.") from erreur
        if self.noter_cout is not None:
            from notes_frais.lecture import cout_usd

            self.noter_cout(db, org_id, cout_usd(reponse.model, reponse.usage.input_tokens, reponse.usage.output_tokens), reponse.model)
        lue = reponse.parsed_output
        if reponse.stop_reason == "refusal" or lue is None:
            return []
        return [
            (c.numero.strip(), c.intitule.strip(), round(c.solde * 100))
            for c in lue.comptes
            if c.numero.strip().isdigit() and c.numero.strip()[0] in "12345" and not c.numero.strip().startswith(_EXCLUS) and round(c.solde * 100)
        ]
