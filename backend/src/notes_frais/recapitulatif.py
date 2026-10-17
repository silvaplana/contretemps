"""PDF d'une note de frais (décision de Seb, 17 octobre) : une page de
récapitulatif (qui, quoi, combien, statut, RIB), puis une page par photo de
ticket. Rangé dans l'enveloppe de la note avec les photos, et tenu à jour à
chaque étape : même si la base de données était perdue, le dossier du
serveur suffit à tout retrouver.

Fait avec Pillow seul (déjà là pour la personnalisation) : pas de
navigateur ni de dépendance en plus. Les PDF joints ne sont pas recopiés
dans ce PDF (Pillow ne les lit pas) : ils restent à côté, dans l'enveloppe.
"""

from __future__ import annotations

import io
import textwrap
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

NOM_FICHIER = "Note de frais.pdf"

# A4 à 150 points par pouce.
LARGEUR, HAUTEUR = 1240, 1754
MARGE = 100
_POLICES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans{}.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-{}.ttf",
)


def _police(taille: int, gras: bool = False):
    for modele in _POLICES:
        suffixe = ("-Bold" if gras else "") if "dejavu" in modele else ("Bold" if gras else "Regular")
        try:
            return ImageFont.truetype(modele.format(suffixe), taille)
        except OSError:
            continue
    return ImageFont.load_default(size=taille)


def _jour(valeur: date | datetime | None) -> str:
    if valeur is None:
        return ""
    if isinstance(valeur, datetime):
        valeur = valeur.date()
    return valeur.strftime("%d/%m/%Y")


def _euros(centimes: int) -> str:
    return f"{centimes / 100:,.2f} €".replace(",", " ").replace(".", ",")


@dataclass
class Piece:
    nom: str
    chemin: Path
    type_mime: str


class _Pages:
    """Écrit des lignes de haut en bas, en passant à une page neuve au bas."""

    def __init__(self) -> None:
        self.pages: list[Image.Image] = []
        self._nouvelle()

    def _nouvelle(self) -> None:
        self.page = Image.new("RGB", (LARGEUR, HAUTEUR), "white")
        self.dessin = ImageDraw.Draw(self.page)
        self.y = MARGE
        self.pages.append(self.page)

    def ligne(self, texte: str, taille: int = 26, gras: bool = False, couleur: str = "black", x: int = MARGE,
              droite: str | None = None, avance: bool = True) -> None:
        if self.y + taille * 1.6 > HAUTEUR - MARGE:
            self._nouvelle()
        police = _police(taille, gras)
        self.dessin.text((x, self.y), texte, font=police, fill=couleur)
        if droite:
            largeur = self.dessin.textlength(droite, font=police)
            self.dessin.text((LARGEUR - MARGE - largeur, self.y), droite, font=police, fill=couleur)
        if avance:
            self.y += int(taille * 1.5)

    def paragraphe(self, texte: str, taille: int = 26, couleur: str = "black", x: int = MARGE, largeur: int = 70) -> None:
        for morceau in textwrap.wrap(texte, largeur) or [""]:
            self.ligne(morceau, taille, couleur=couleur, x=x)

    def espace(self, hauteur: int = 20) -> None:
        self.y += hauteur

    def trait(self) -> None:
        self.dessin.line((MARGE, self.y, LARGEUR - MARGE, self.y), fill="#999999", width=2)
        self.y += 16


def generer(
    *,
    organisation: str,
    note,
    auteur: str,
    traitee_par: str | None,
    remboursee_par: str | None,
    statut: str,
    pieces_par_depense: dict[int, list[Piece]],
) -> bytes:
    """Le PDF de `note` (modèle NoteFrais, dépenses chargées)."""
    p = _Pages()
    p.ligne(organisation, 24, couleur="#555555")
    p.ligne(f"Note de frais n° {note.id}", 44, gras=True)
    p.paragraphe(note.titre, 30)
    p.espace()
    p.ligne(f"Personne : {auteur}")
    p.ligne(f"Envoyée le {_jour(note.envoyee_le)}")
    p.ligne(f"Statut : {statut}", gras=True)
    if note.traitee_le:
        mot = "Refusée" if note.statut == "refusee" else "Validée"
        p.ligne(f"{mot} le {_jour(note.traitee_le)}" + (f" par {traitee_par}" if traitee_par else ""))
    if note.motif_refus:
        p.paragraphe(f"Motif du refus : {note.motif_refus}")
    if note.remboursee_le:
        p.ligne(f"Remboursée le {_jour(note.remboursee_le)}" + (f" par {remboursee_par}" if remboursee_par else ""))
    if note.don:
        p.ligne("Don à l'association : la personne renonce au remboursement (abandon de frais).")
    elif note.rib_iban:
        p.ligne(f"RIB : {note.rib_titulaire or ''}  {note.rib_iban}  {note.rib_bic or ''}".strip())
    p.espace(30)

    p.ligne("Date", 24, gras=True, avance=False)
    p.ligne("Catégorie · description", 24, gras=True, x=MARGE + 190, droite="Montant")
    p.trait()
    joints = []
    for depense in sorted(note.depenses, key=lambda d: (d.date, d.id)):
        categorie = depense.categorie.libelle if depense.categorie else ""
        texte = " · ".join(t for t in (categorie, depense.description) if t)
        p.ligne(_jour(depense.date), 24, avance=False)
        morceaux = textwrap.wrap(texte, 52) or [""]
        p.ligne(morceaux[0], 24, x=MARGE + 190, droite=_euros(depense.montant_centimes))
        for suite in morceaux[1:]:
            p.ligne(suite, 24, x=MARGE + 190)
        pieces = pieces_par_depense.get(depense.id, [])
        if not pieces:
            p.ligne("sans justificatif", 20, couleur="#a05a00", x=MARGE + 190)
        for piece in pieces:
            p.ligne(f"justificatif : {piece.nom}", 20, couleur="#555555", x=MARGE + 190)
            joints.append(piece)
        p.espace(8)
    p.trait()
    total = sum(d.montant_centimes for d in note.depenses)
    p.ligne("Total", 30, gras=True, droite=_euros(total))
    p.espace(30)
    p.ligne(f"Document produit par l'appli le {_jour(datetime.now())}.", 20, couleur="#777777")

    for piece in joints:
        if not piece.type_mime.startswith("image/"):
            continue
        try:
            with Image.open(piece.chemin) as image:
                photo = ImageOps.exif_transpose(image).convert("RGB")
        except Exception:
            continue
        page = Image.new("RGB", (LARGEUR, HAUTEUR), "white")
        dessin = ImageDraw.Draw(page)
        dessin.text((MARGE, MARGE // 2), piece.nom, font=_police(22), fill="#555555")
        photo.thumbnail((LARGEUR - 2 * MARGE, HAUTEUR - 2 * MARGE))
        page.paste(photo, ((LARGEUR - photo.width) // 2, MARGE))
        p.pages.append(page)

    tampon = io.BytesIO()
    premiere, *suite = p.pages
    premiere.save(tampon, "PDF", save_all=True, append_images=suite, resolution=150.0)
    return tampon.getvalue()
