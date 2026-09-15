"""Génère le dossier d'inscription (PDF) via un template HTML/CSS +
rendu headless Chromium — même principe que facture_html.py (voir ce
module pour le détail de l'approche), remplace la version reportlab
(pdf.py:generer_dossier_pdf). Gabarit fourni par l'utilisateur (voir
data/dossier inscription/ à la racine du repo, hors de ce module : le
brouillon d'origine — CE module en est la version branchée sur les
vraies données).

Écarts volontaires par rapport au gabarit d'origine :
- Pas d'image de signature dessinée : décision déjà actée pour ce
  projet (voir spec/SPEC-inscription.md — signature électronique =
  case cochée + nom tapé, jamais un canvas dessiné). Le cadre
  "Signataire" du gabarit affiche donc le nom tapé + la date, sans
  image — une image de signature fixe, la même pour toutes les
  familles, serait trompeuse.
- "Règlement de la cotisation (HelloAsso)" → "Règlement de la
  cotisation" : HelloAsso n'apparaît jamais côté famille (voir
  frontend-inscription/src/PaiementEtape.jsx).

Fonction PURE comme le reste de pdf.py — voir tests/test_dossier_html.py.
"""

from __future__ import annotations

import base64
import html
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

from .coordonnees_association import ADRESSE_L1, ADRESSE_L2, EMAIL, RNA, SIRET, TELEPHONE

logger = logging.getLogger(__name__)

_DOSSIER = Path(__file__).parent / "dossier_template"
_TEMPLATE = (_DOSSIER / "dossier.template.html").read_text(encoding="utf-8")
_LOGO_B64 = "data:image/jpeg;base64," + base64.b64encode((_DOSSIER / "logo.jpg").read_bytes()).decode()

_BINAIRES_CHROMIUM = ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable")


def _echappe(texte: str | None) -> str:
    return html.escape(texte or "", quote=False)


def _vide(texte: str | None) -> str:
    """Champ non renseigné -> tiret grisé, même convention que le
    gabarit d'origine (voir data/dossier inscription/build_dossier.py:vide)."""
    texte = (texte or "").strip()
    if not texte:
        return '<span class="vide">Non renseigné</span>'
    return _echappe(texte)


def _pill(valeur: bool) -> tuple[str, str]:
    return ("Oui", "oui") if valeur else ("Non", "non")


def _numero_dossier(inscription) -> str:
    annee_debut = inscription.saison.split("-")[0]
    return f"INS-{annee_debut}-{inscription.id:04d}"


def _photo_html(chemin_photo: Path | None) -> str:
    """`None`/illisible -> pas de bloc photo du tout (jamais une case
    vide disgracieuse) — même philosophie que pdf.py:_photo_flowable :
    une photo cassée ne doit jamais faire échouer le reste du dossier."""
    if chemin_photo is None:
        return ""
    try:
        mime = "image/png" if chemin_photo.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(chemin_photo.read_bytes()).decode()
        return f'<img class="photo" src="data:{mime};base64,{b64}" alt="Photo de l\'élève">'
    except Exception:
        logger.warning("Photo illisible, ignorée dans le dossier : %s", chemin_photo)
        return ""


def _cours_html(noms_cours: list[str]) -> str:
    return "".join(f"<span>{_echappe(nom)}</span>" for nom in noms_cours)


def _cours_meta_html(inscription, noms_cours: list[str]) -> str:
    n = len(noms_cours)
    # "cours" est invariable en français (un cours, des cours) — seul
    # "sélectionné" prend un "s" au pluriel.
    base = f"{n} cours sélectionné{'s' if n > 1 else ''} — saison {inscription.saison}."
    if inscription.alerte_palier_mixte:
        base += " Les cours choisis touchent plusieurs paliers tarifaires : le palier le plus élevé est retenu."
    return base


def _reglement_coche_html(inscription) -> str:
    if inscription.reglement_lu_approuve:
        return '<div class="coche"><div class="box">✓</div><div>Lu et approuvé</div></div>'
    return '<div class="coche"><div class="box">✗</div><div>Non approuvé</div></div>'


def _trouver_chromium() -> str:
    for binaire in _BINAIRES_CHROMIUM:
        chemin = shutil.which(binaire)
        if chemin:
            return chemin
    raise RuntimeError(
        "Aucun binaire Chromium/Chrome trouvé (essayé : " + ", ".join(_BINAIRES_CHROMIUM) + ")"
    )


def generer_dossier_pdf(inscription, noms_cours: list[str], chemin_photo: Path | None = None) -> bytes:
    autor_txt, autor_cls = _pill(inscription.droit_image_autorise)
    site_txt, site_cls = _pill(inscription.droit_image_site)
    rs_txt, rs_cls = _pill(inscription.droit_image_reseaux)
    aff_txt, aff_cls = _pill(inscription.droit_image_affiches)

    valeurs = {
        "LOGO": _LOGO_B64,
        "SAISON": inscription.saison,
        "NUM_DOSSIER": _numero_dossier(inscription),
        "DATE_DEPOT": f"{inscription.created_at:%d/%m/%Y}",
        "TEL": TELEPHONE,
        "EMAIL": EMAIL,
        "SIRET": SIRET,
        "RNA": RNA,
        "ADRESSE_L1": ADRESSE_L1,
        "ADRESSE_L2": ADRESSE_L2,
        "ELEVE_NOM": _echappe(inscription.eleve_nom),
        "ELEVE_PRENOM": _echappe(inscription.eleve_prenom),
        "ELEVE_NAISSANCE": f"{inscription.eleve_date_naissance:%d/%m/%Y}",
        "ELEVE_ADRESSE": _vide(inscription.eleve_adresse),
        "ELEVE_TEL": _vide(inscription.eleve_telephone),
        "ELEVE_EMAIL": _vide(inscription.eleve_email),
        "PHOTO": _photo_html(chemin_photo),
        "URG_NOM": _vide(inscription.contact_urgence_nom),
        "URG_PRENOM": _vide(inscription.contact_urgence_prenom),
        "URG_LIEN": _vide(inscription.contact_urgence_lien),
        "URG_TEL": _vide(inscription.contact_urgence_telephone),
        "COURS": _cours_html(noms_cours),
        "COURS_META": _cours_meta_html(inscription, noms_cours),
        "MED_ALLERGIES": _vide(inscription.allergies),
        "MED_TRAITEMENT": _vide(inscription.traitement_medical),
        "MED_AUTRES": _vide(inscription.informations_importantes),
        "AUTOR": autor_txt,
        "AUTOR_CLS": autor_cls,
        "IMG_SITE": site_txt,
        "IMG_SITE_CLS": site_cls,
        "IMG_RS": rs_txt,
        "IMG_RS_CLS": rs_cls,
        "IMG_AFF": aff_txt,
        "IMG_AFF_CLS": aff_cls,
        "REGLEMENT_COCHE": _reglement_coche_html(inscription),
        "SIGNATAIRE": _echappe(inscription.signataire_nom) or '<span class="vide">Non renseigné</span>',
        "DATE_SOUMISSION": f"{inscription.created_at:%d/%m/%Y à %H:%M}",
        "IP_SUFFIXE": f" depuis {_echappe(inscription.ip_soumission)}" if inscription.ip_soumission else "",
    }

    html_final = _TEMPLATE
    for cle, valeur in valeurs.items():
        html_final = html_final.replace("{{" + cle + "}}", valeur)

    with tempfile.TemporaryDirectory() as dossier_temp:
        chemin_html = Path(dossier_temp) / "dossier.html"
        chemin_pdf = Path(dossier_temp) / "dossier.pdf"
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
