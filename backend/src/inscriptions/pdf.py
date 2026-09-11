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

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_STYLES = getSampleStyleSheet()


def _titre(texte: str) -> Paragraph:
    return Paragraph(texte, _STYLES["Heading1"])


def _sous_titre(texte: str) -> Paragraph:
    return Paragraph(texte, _STYLES["Heading2"])


def _texte(texte: str) -> Paragraph:
    return Paragraph(texte, _STYLES["Normal"])


def _oui_non(valeur: bool) -> str:
    return "Oui" if valeur else "Non"


def generer_dossier_pdf(inscription, noms_cours: list[str]) -> bytes:
    """Reprend les sections du vrai dossier papier : fiche d'inscription
    (élève + contact urgence + cours + infos médicales), autorisations
    (droit à l'image, règlement intérieur signé)."""
    style_tableau = TableStyle(
        [
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )

    tableau_eleve = Table(
        [
            ["Nom", inscription.eleve_nom],
            ["Prénom", inscription.eleve_prenom],
            ["Date de naissance", inscription.eleve_date_naissance.strftime("%d/%m/%Y")],
            ["Adresse", inscription.eleve_adresse or "—"],
            ["Téléphone", inscription.eleve_telephone or "—"],
            ["Email", inscription.eleve_email or "—"],
        ],
        colWidths=[5 * cm, 11 * cm],
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

    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    elements = [
        _titre("Dossier d'inscription"),
        _texte(f"Saison {inscription.saison}"),
        Spacer(1, 0.5 * cm),
        _sous_titre("Élève"),
        tableau_eleve,
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
    déjà enregistrés sur l'inscription."""
    tampon = io.BytesIO()
    doc = SimpleDocTemplate(tampon, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm)
    lignes = [
        ["Désignation", "Montant"],
        ["Adhésion (payée à part, par chèque)", f"{inscription.montant_adhesion:.2f} €"],
        [
            f"Mensualité (septembre à juin, {inscription.nb_cours_semaine} cours/semaine)",
            f"{inscription.montant_mensuel_septembre:.2f} €",
        ],
        ["Ou trimestriel (3 échéances)", f"{inscription.montant_trimestriel:.2f} €"],
    ]
    if inscription.reduction_famille_appliquee:
        lignes.append(["Réduction famille appliquée", "-5,00 € / élève"])
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
