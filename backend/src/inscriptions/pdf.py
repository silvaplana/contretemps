"""Génère les 2 PDF d'une inscription (dossier rempli + facture) — via
reportlab (voir pyproject.toml). Fonctions PURES (prennent l'objet déjà
en base, ou tout objet portant les mêmes attributs) : pas de dépendance
DB/FastAPI ici, testables isolément.

Pas un rendu pixel-perfect du vrai "dossier d'inscription.pdf" papier —
juste un document propre reprenant les mêmes sections (voir
spec/SPEC-inscription.md).
"""

from __future__ import annotations

import io
import logging
import re
import unicodedata
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_STYLES = getSampleStyleSheet()
logger = logging.getLogger(__name__)


def _translitere(texte: str) -> str:
    """"Julie" / "Dupont-Martin" -> "julie" / "dupont_martin" — accents
    retirés et caractères non alphanumériques réduits à "_", pour un nom
    de fichier sûr partout (disque, en-tête HTTP Content-Disposition,
    pièce jointe email)."""
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^A-Za-z0-9]+", "_", sans_accents).strip("_").lower()


def nom_fichier_dossier(inscription) -> str:
    """Nom de fichier proposé au téléchargement/à la pièce jointe email —
    voir receiver.py et inscriptions.py:_envoyer_email."""
    return (
        f"dossier_{_translitere(inscription.eleve_prenom)}_"
        f"{_translitere(inscription.eleve_nom)}_{inscription.saison.replace('-', '')}.pdf"
    )


def nom_fichier_facture(inscription) -> str:
    return (
        f"facture_{_translitere(inscription.eleve_prenom)}_"
        f"{_translitere(inscription.eleve_nom)}_{inscription.saison.replace('-', '')}.pdf"
    )


def _photo_flowable(chemin_photo: Path, max_largeur: float, max_hauteur: float) -> Image | None:
    """Image proportionnée (jamais déformée), bornée par une boîte
    max_largeur x max_hauteur — voir generer_dossier_pdf. `None` si le
    fichier est illisible/corrompu : la photo ne doit jamais faire
    échouer la génération du reste du dossier (même philosophie que
    inscriptions.py : PDF/Excel/email jamais bloquants)."""
    try:
        from PIL import Image as PILImage

        with PILImage.open(chemin_photo) as image:
            largeur_px, hauteur_px = image.size
        echelle = min(max_largeur / largeur_px, max_hauteur / hauteur_px)
        return Image(str(chemin_photo), width=largeur_px * echelle, height=hauteur_px * echelle)
    except Exception:
        logger.warning("Photo illisible, ignorée dans le PDF : %s", chemin_photo)
        return None


def _titre(texte: str) -> Paragraph:
    return Paragraph(texte, _STYLES["Heading1"])


def _sous_titre(texte: str) -> Paragraph:
    return Paragraph(texte, _STYLES["Heading2"])


def _texte(texte: str) -> Paragraph:
    return Paragraph(texte, _STYLES["Normal"])


def _oui_non(valeur: bool) -> str:
    return "Oui" if valeur else "Non"


def generer_dossier_pdf(inscription, noms_cours: list[str], chemin_photo: Path | None = None) -> bytes:
    """Reprend les sections du vrai dossier papier : fiche d'inscription
    (élève + contact urgence + cours + infos médicales), autorisations
    (droit à l'image, règlement intérieur signé). `chemin_photo` :
    optionnelle (voir inscriptions.py:enregistrer_photo — uploadée après
    la création, régénère ce PDF une fois reçue)."""
    style_tableau = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )

    # Largeur réduite si une photo l'accompagne (voir bloc_eleve
    # ci-dessous) : une table imbriquée dans reportlab garde SES colWidths
    # propres, sans jamais se réduire à la largeur de sa cellule parente —
    # il faut donc lui donner d'emblée la bonne largeur totale (11cm,
    # comme la 1ère colonne de bloc_eleve), pas 16cm, sous peine de
    # chevaucher la colonne photo.
    colonnes_eleve = [4 * cm, 7 * cm] if chemin_photo else [5 * cm, 11 * cm]
    tableau_eleve = Table(
        [
            ["Nom", inscription.eleve_nom],
            ["Prénom", inscription.eleve_prenom],
            ["Date de naissance", inscription.eleve_date_naissance.strftime("%d/%m/%Y")],
            ["Adresse", inscription.eleve_adresse or "—"],
            ["Téléphone", inscription.eleve_telephone or "—"],
            ["Email", inscription.eleve_email or "—"],
        ],
        colWidths=colonnes_eleve,
    )
    tableau_contact = Table(
        [
            ["Nom", inscription.contact_urgence_nom or "—"],
            ["Prénom", inscription.contact_urgence_prenom or "—"],
            ["Lien", inscription.contact_urgence_lien or "—"],
            ["Téléphone", inscription.contact_urgence_telephone or "—"],
        ],
        colWidths=[5 * cm, 11 * cm],
    )
    tableau_medical = Table(
        [
            ["Allergies", inscription.allergies or "—"],
            ["Traitement médical", inscription.traitement_medical or "—"],
            ["Informations importantes", inscription.informations_importantes or "—"],
        ],
        colWidths=[5 * cm, 11 * cm],
    )
    for tableau in (tableau_eleve, tableau_contact, tableau_medical):
        tableau.setStyle(style_tableau)

    # Photo à côté du tableau élève (voir "documents à apporter" du vrai
    # dossier papier — 2 photos d'identité) — absente : juste le tableau
    # seul, pas de case vide disgracieuse.
    bloc_eleve = tableau_eleve
    photo = _photo_flowable(chemin_photo, 3.5 * cm, 4.5 * cm) if chemin_photo else None
    if photo is not None:
        bloc_eleve = Table(
            [[tableau_eleve, photo]],
            colWidths=[11 * cm, 5 * cm],
        )
        bloc_eleve.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))

    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    elements = [
        _titre("Dossier d'inscription"),
        _texte(f"Saison {inscription.saison}"),
        Spacer(1, 0.5 * cm),
        _sous_titre("Élève"),
        bloc_eleve,
        Spacer(1, 0.5 * cm),
        _sous_titre("Contact d'urgence"),
        tableau_contact,
        Spacer(1, 0.5 * cm),
        _sous_titre("Cours choisis"),
        _texte(", ".join(noms_cours) if noms_cours else "Aucun"),
        Spacer(1, 0.5 * cm),
        _sous_titre("Informations médicales"),
        tableau_medical,
        Spacer(1, 0.5 * cm),
        _sous_titre("Droit à l'image"),
        _texte(f"Autorisation : {_oui_non(inscription.droit_image_autorise)}"),
        _texte(
            f"Site internet : {_oui_non(inscription.droit_image_site)} — "
            f"Réseaux sociaux : {_oui_non(inscription.droit_image_reseaux)} — "
            f"Affiches : {_oui_non(inscription.droit_image_affiches)}"
        ),
        Spacer(1, 0.5 * cm),
        _sous_titre("Règlement intérieur"),
        _texte("Lu et approuvé" if inscription.reglement_lu_approuve else "Non approuvé"),
        _texte(f"Signataire : {inscription.signataire_nom or '—'}"),
        _texte(
            f"Soumis le {inscription.created_at.strftime('%d/%m/%Y à %H:%M')}"
            + (f" depuis {inscription.ip_soumission}" if inscription.ip_soumission else "")
        ),
    ]
    doc.build(elements)
    return tampon.getvalue()


# generer_facture_pdf (facture) a déménagé dans facture_html.py — rendu
# HTML/CSS + headless Chromium (gabarit fourni par l'utilisateur),
# beaucoup plus proche d'une vraie facture que reportlab. Cette version
# reportlab est restée assez longtemps pour être remplacée proprement,
# voir git log si besoin de la retrouver.
