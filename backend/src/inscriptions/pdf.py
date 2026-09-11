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
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_STYLES = getSampleStyleSheet()
logger = logging.getLogger(__name__)


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


def generer_facture_pdf(inscription) -> bytes:
    """Facture correspondant au tarif figé à la soumission (voir
    tarifs.py) — ne recalcule jamais rien, lit uniquement les montants
    déjà enregistrés sur l'inscription. Toujours 3 trimestres par an
    (voir tarifs.py:NB_TRIMESTRES), jamais de mensualité affichée ici."""
    from .tarifs import LIBELLE_PALIER, NB_TRIMESTRES, REDUCTION_FAMILLE

    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)

    montant_trois_trimestres = inscription.montant_trimestriel * NB_TRIMESTRES
    total_annee = inscription.montant_adhesion + montant_trois_trimestres
    libelle_palier = LIBELLE_PALIER.get(inscription.palier_tarifaire, inscription.palier_tarifaire)
    reduction = " — famille : -5 €" if inscription.reduction_famille_appliquee else ""
    # `inscription.montant_trimestriel` est DÉJÀ réduit (voir
    # inscriptions.py) — reconstruit le prix brut du palier pour
    # l'affichage (voir tarifs.js:montantTrimestrielBrut côté frontend,
    # même logique), sans changer le montant réellement dû ci-dessus.
    montant_trimestriel_brut = inscription.montant_trimestriel + (
        REDUCTION_FAMILLE if inscription.reduction_famille_appliquee else 0.0
    )

    lignes = [
        ["Désignation", "Montant"],
        ["Adhésion (payée à part, par chèque)", f"{inscription.montant_adhesion:.2f} €"],
        [
            f"3 trimestres à {inscription.nb_cours_semaine} cours/semaine "
            f"(palier « {libelle_palier} » {montant_trimestriel_brut:.2f} €{reduction})",
            f"{montant_trois_trimestres:.2f} €",
        ],
        ["Total année", f"{total_annee:.2f} €"],
    ]
    tableau = Table(lignes, colWidths=[11 * cm, 5 * cm])
    tableau.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements = [
        _titre("Facture"),
        _texte(f"Saison {inscription.saison}"),
        _texte(f"Élève : {inscription.eleve_prenom} {inscription.eleve_nom}"),
        _texte(f"Moyen de paiement : {inscription.moyen_paiement}"),
        Spacer(1, 0.5 * cm),
        tableau,
    ]
    if inscription.alerte_palier_mixte:
        elements.append(Spacer(1, 0.3 * cm))
        elements.append(
            _texte(
                "⚠ Cours choisis touchant plusieurs paliers tarifaires — montant le plus "
                "élevé retenu, à vérifier par l'école."
            )
        )
    doc.build(elements)
    return tampon.getvalue()
