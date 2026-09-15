"""Utilitaires communs aux 2 PDF d'une inscription (dossier rempli +
facture) — la génération elle-même vit dans dossier_html.py et
facture_html.py (rendu HTML/CSS + headless Chromium, gabarits fournis
par l'utilisateur), plus rien ici ne dépend de reportlab."""

from __future__ import annotations

import re
import unicodedata


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
