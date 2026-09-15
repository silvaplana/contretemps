"""Génère la facture (PDF) via un template HTML/CSS + rendu headless
Chromium ("imprimer en PDF") — remplace l'ancienne version reportlab
(voir pdf.py:generer_facture_pdf, gardée telle quelle pour le dossier
d'inscription, qui n'a pas ce template). Le rendu HTML/CSS permet une
mise en page bien plus proche d'une vraie facture (dégradés, encadrés,
typographies...) qu'avec les primitives de dessin de reportlab —
gabarit fourni par l'utilisateur (voir data/facture/ à la racine du
repo, hors de ce module : le brouillon d'origine, gardé pour référence/
retouches visuelles futures — CE module en est la version branchée sur
les vraies données).

Fonction PURE comme le reste de pdf.py : prend l'inscription déjà en
base (ou tout objet portant les mêmes attributs), pas de dépendance
DB/FastAPI ici, testable isolément — voir tests/test_facture_html.py.
"""

from __future__ import annotations

import base64
import html
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .coordonnees_association import (
    ADRESSE_L1,
    ADRESSE_L2,
    APE,
    EMAIL,
    NOM_TRESORIER,
    RNA,
    SIRET,
    SITE,
    TELEPHONE,
)
from .tarifs import (
    LIBELLE_PALIER,
    NB_TRIMESTRES,
    REDUCTION_FAMILLE,
    calculer_echeances_helloasso,
    mois_encaissements_a_venir,
)

logger = logging.getLogger(__name__)

_DOSSIER = Path(__file__).parent / "facture_template"
_TEMPLATE = (_DOSSIER / "facture.template.html").read_text(encoding="utf-8")


def _b64(nom_fichier: str) -> str:
    return "data:image/jpeg;base64," + base64.b64encode((_DOSSIER / nom_fichier).read_bytes()).decode()


_LOGO_B64 = _b64("logo.jpg")
_SIGNATURE_B64 = _b64("signature.jpg")

# Chromium (ou équivalent) requis pour le rendu "imprimer en PDF" — pas
# de dépendance Python dédiée (voir Dockerfile : `chromium` installé via
# apt), juste un binaire externe. Plusieurs noms possibles selon
# l'environnement (image Docker vs poste de dev).
_BINAIRES_CHROMIUM = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


def _echappe(texte: str | None) -> str:
    """Toute donnée saisie par la famille (nom, adresse...) est
    interpolée dans du HTML — échapper systématiquement, sinon une
    inscription malveillante pourrait casser la mise en page ou
    injecter du HTML dans la facture."""
    return html.escape(texte or "", quote=False)


def _euros(montant: float) -> str:
    entier = f"{montant:,.2f}".replace(",", " ").replace(".", ",")
    return f"{entier} €"


def _numero_facture(inscription) -> str:
    annee_debut = inscription.saison.split("-")[0]
    return f"F{annee_debut}-{inscription.id:04d}"


def _numero_adherent(inscription) -> str:
    annee_debut = inscription.saison.split("-")[0]
    return f"ADH-{annee_debut}-{inscription.id:04d}"


def _lignes_html(inscription, noms_cours: list[str]) -> str:
    libelle_palier = LIBELLE_PALIER.get(inscription.palier_tarifaire, inscription.palier_tarifaire)
    montant_trimestriel_brut = inscription.montant_trimestriel + (
        REDUCTION_FAMILLE if inscription.reduction_famille_appliquee else 0.0
    )
    sous_total_cours = montant_trimestriel_brut * NB_TRIMESTRES

    lignes = [
        f"""
        <tr>
          <td>
            <div class="des">Adhésion annuelle à l'association</div>
            <div class="det">Cotisation membre</div>
          </td>
          <td>Saison {inscription.saison}</td>
          <td class="num">1</td>
          <td class="num">{_euros(inscription.montant_adhesion)}</td>
          <td class="num">{_euros(inscription.montant_adhesion)}</td>
        </tr>""",
        f"""
        <tr>
          <td>
            <div class="des">Cours de danse — {inscription.nb_cours_semaine} cours / semaine</div>
            <div class="det">
              {_echappe(' · '.join(noms_cours)) if noms_cours else '—'}<br>
              Palier tarifaire appliqué : « {libelle_palier} » — {_euros(montant_trimestriel_brut)} / trimestre
            </div>
          </td>
          <td>{NB_TRIMESTRES} trimestres</td>
          <td class="num">{NB_TRIMESTRES}</td>
          <td class="num">{_euros(montant_trimestriel_brut)}</td>
          <td class="num">{_euros(sous_total_cours)}</td>
        </tr>""",
    ]
    if inscription.reduction_famille_appliquee:
        montant_reduction = REDUCTION_FAMILLE * NB_TRIMESTRES
        lignes.append(f"""
        <tr class="remise">
          <td>
            <div class="des">Réduction famille</div>
            <div class="det">Adhésion dégressive dès deux membres d'une même famille — {_euros(REDUCTION_FAMILLE)} / trimestre</div>
          </td>
          <td>{NB_TRIMESTRES} trimestres</td>
          <td class="num">{NB_TRIMESTRES}</td>
          <td class="num">−{_euros(REDUCTION_FAMILLE)}</td>
          <td class="num">−{_euros(montant_reduction)}</td>
        </tr>""")
    return "\n".join(lignes)


def _totaux_html(inscription) -> str:
    montant_trimestriel_brut = inscription.montant_trimestriel + (
        REDUCTION_FAMILLE if inscription.reduction_famille_appliquee else 0.0
    )
    sous_total_cours = montant_trimestriel_brut * NB_TRIMESTRES
    total_annee = inscription.montant_adhesion + inscription.montant_trimestriel * NB_TRIMESTRES

    lignes = [
        f'<tr><td class="k">Sous-total cours</td><td class="v">{_euros(sous_total_cours)}</td></tr>',
        f'<tr><td class="k">Adhésion</td><td class="v">{_euros(inscription.montant_adhesion)}</td></tr>',
    ]
    if inscription.reduction_famille_appliquee:
        montant_reduction = REDUCTION_FAMILLE * NB_TRIMESTRES
        lignes.append(
            f'<tr><td class="k">Réduction famille</td><td class="v">−{_euros(montant_reduction)}</td></tr>'
        )
    lignes.append(f'<tr class="sep"><td class="k">Total</td><td class="v">{_euros(total_annee)}</td></tr>')
    lignes.append('<tr><td class="k">TVA</td><td class="v">—</td></tr>')
    lignes.append(
        f'<tr class="net"><td class="k">NET À PAYER</td><td class="v">{_euros(total_annee)}</td></tr>'
    )
    return "\n".join(lignes)


_MOIS_FR = [
    "janvier", "février", "mars", "avril", "mai", "juin",
    "juillet", "août", "septembre", "octobre", "novembre", "décembre",
]


def _libelle_mois(date) -> str:
    return f"{_MOIS_FR[date.month - 1]} {date.year}"


def _reglement_html(inscription) -> str:
    """"HelloAsso" n'apparaît jamais — prestataire invisible pour la
    famille (voir frontend-inscription/src/PaiementEtape.jsx), juste
    "carte bancaire"."""
    if inscription.moyen_paiement == "cheque":
        return _reglement_cheque_html(inscription)
    return _reglement_carte_html(inscription)


def _reglement_cheque_html(inscription) -> str:
    """Un chèque séparé pour l'adhésion, TOUJOURS (même règle que
    Confirmation.jsx/PaiementEtape.jsx) — contrairement à la carte, où
    l'adhésion peut être fusionnée avec un trimestre déjà entamé dans
    UN SEUL prélèvement (voir _reglement_carte_html)."""
    lignes = [
        "Moyen de paiement : <b>Chèque</b>",
        "Chèques à l'ordre de <b>Contretemps</b>, à remettre à l'école.",
    ]
    base = f"Un chèque de {_euros(inscription.montant_adhesion)} à l'inscription, puis le solde"
    if inscription.paiement_nb_echeances == 3:
        mois_a_venir = mois_encaissements_a_venir(inscription.saison)
        if mois_a_venir:
            dates = ", ".join(_libelle_mois(d) for d in mois_a_venir)
            lignes.append(
                f"{base} en {len(mois_a_venir)} chèques de {_euros(inscription.montant_trimestriel)} "
                f"chacun, encaissés en début de trimestre : {dates}."
            )
        else:
            lignes.append(f"{base} en 1 chèque, remis avec celui de l'adhésion.")
    else:
        lignes.append(f"{base} en 1 chèque, remis avec celui de l'adhésion.")
    return "<br>".join(lignes)


def _reglement_carte_html(inscription) -> str:
    echeances = calculer_echeances_helloasso(
        inscription.montant_adhesion,
        inscription.montant_trimestriel,
        inscription.paiement_nb_echeances,
        inscription.saison,
    )
    immediat, futures = echeances[0], echeances[1:]
    if not futures:
        detail = f"Payé en une fois par carte bancaire : {_euros(immediat.montant)}."
    else:
        dates = ", ".join(_libelle_mois(e.date_prelevement) for e in futures)
        unite = f"prélèvement{'s' if len(futures) > 1 else ''}"
        detail = (
            f"{_euros(immediat.montant)} prélevés à l'inscription, puis le solde en "
            f"{len(futures)} {unite} de {_euros(futures[0].montant)} chacun, au début de "
            f"chaque trimestre : {dates}."
        )
    return "<br>".join(["Moyen de paiement : <b>Carte bancaire</b>", detail])


def _client_adresse_html(inscription) -> str:
    if not inscription.eleve_adresse:
        return ""
    lignes_adresse = "<br>".join(_echappe(l) for l in inscription.eleve_adresse.splitlines() if l.strip())
    return f"{lignes_adresse}<br>"


def _acquit_html(inscription) -> str:
    """Voir décision utilisateur : "Facture acquittée" + signature
    UNIQUEMENT si vraiment payé (carte bancaire confirmée) — un chèque
    n'est jamais confirmé en ligne dans ce système, donc jamais
    "acquitté" ici, même une fois remis à l'école."""
    paye = inscription.moyen_paiement == "helloasso" and inscription.statut_paiement == "paye"
    if paye:
        from datetime import datetime

        return f"""
  <div class="acquit">
    <div class="cartouche">
      <div class="titre">Facture acquittée</div>
      <div class="lieu">Le Beausset, le {datetime.now():%d/%m/%Y}</div>
      <img src="{_SIGNATURE_B64}" alt="Signature">
      <div class="role">{NOM_TRESORIER}</div>
    </div>
  </div>"""
    return """
  <div class="acquit">
    <div class="cartouche">
      <div class="titre">Facture à régler</div>
    </div>
  </div>"""


def _note_palier_mixte_html(inscription) -> str:
    if not inscription.alerte_palier_mixte:
        return ""
    return (
        '<div class="note">Les cours choisis relèvent de plusieurs paliers tarifaires : '
        "conformément au règlement intérieur de l'école, le palier le plus élevé est retenu "
        "pour l'ensemble de l'inscription.</div>"
    )


def _trouver_chromium() -> str:
    for binaire in _BINAIRES_CHROMIUM:
        chemin = shutil.which(binaire)
        if chemin:
            return chemin
    raise RuntimeError(
        "Aucun binaire Chromium/Chrome trouvé (essayé : " + ", ".join(_BINAIRES_CHROMIUM) + ")"
    )


def generer_facture_pdf(inscription, noms_cours: list[str]) -> bytes:
    from datetime import datetime

    valeurs = {
        "LOGO": _LOGO_B64,
        "NUM_FACTURE": _numero_facture(inscription),
        "DATE_EMISSION": f"{datetime.now():%d/%m/%Y}",
        "SAISON": inscription.saison,
        "NUM_ADHERENT": _numero_adherent(inscription),
        "SIRET": SIRET,
        "APE": APE,
        "RNA": RNA,
        "TEL": TELEPHONE,
        "EMAIL": EMAIL,
        "SITE": SITE,
        "ADRESSE_L1": ADRESSE_L1,
        "ADRESSE_L2": ADRESSE_L2,
        "CLIENT_NOM": _echappe(inscription.signataire_nom) or _echappe(
            f"{inscription.eleve_prenom} {inscription.eleve_nom}"
        ),
        "CLIENT_ADRESSE": _client_adresse_html(inscription),
        "ELEVE": _echappe(f"{inscription.eleve_prenom} {inscription.eleve_nom}"),
        "LIGNES": _lignes_html(inscription, noms_cours),
        "TOTAUX": _totaux_html(inscription),
        "REGLEMENT": _reglement_html(inscription),
        "NOTE_PALIER_MIXTE": _note_palier_mixte_html(inscription),
        "ACQUIT": _acquit_html(inscription),
    }

    html_final = _TEMPLATE
    for cle, valeur in valeurs.items():
        html_final = html_final.replace("{{" + cle + "}}", valeur)

    with tempfile.TemporaryDirectory() as dossier_temp:
        chemin_html = Path(dossier_temp) / "facture.html"
        chemin_pdf = Path(dossier_temp) / "facture.pdf"
        chemin_html.write_text(html_final, encoding="utf-8")

        subprocess.run(
            [
                _trouver_chromium(),
                "--headless", "--disable-gpu", "--no-sandbox",
                "--no-pdf-header-footer", "--print-to-pdf-no-header",
                f"--print-to-pdf={chemin_pdf}",
                chemin_html.as_uri(),
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
        return chemin_pdf.read_bytes()
