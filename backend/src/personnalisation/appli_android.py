"""Appli Android d'une école (spec/core.md §2.7 ter, Seb 18/11/2026).

Pour filmer avec la télécommande (Fights), le téléphone de la salle ne doit
pas se mettre en veille : seule l'appli Android « Tournage <école> » le
permet (ANDROID.md). Un Super User l'allume pour une école dont Fights est
allumé ; l'action GitHub « Appli Tournage (APK) » la fabrique alors et la
publie dans la release « tournage-latest », dont `version.json` dit quelles
applis sont prêtes. Les adhérents Android la reçoivent à leur arrivée.

`ecoles.appli_android` : allumée ou non. `ecoles.apk_cle` : le nom de l'appli dans la release
(tournage-<cle>.apk). Fixé au premier « Oui » et jamais changé ensuite :
les applis installées se mettent à jour par lui (Updater.java).
"""

import json
import logging
import os
import time
import urllib.request

from ecoles.models import Ecole

log = logging.getLogger(__name__)

DEPOT = os.environ.get("GITHUB_DEPOT", "silvaplana/contretemps")
RELEASE = f"https://github.com/{DEPOT}/releases/download/tournage-latest"
ACTION = "tournage-apk.yml"

_cache: dict = {"quand": 0.0, "version": None}


def version_publiee() -> dict:
    """`version.json` de la release ({build, date, apk: {cle: url}}), relu
    au plus toutes les 30 s ; {} si GitHub ne répond pas."""
    if time.monotonic() - _cache["quand"] > 30:
        try:
            with urllib.request.urlopen(f"{RELEASE}/version.json", timeout=5) as reponse:
                _cache["version"] = json.load(reponse)
        except Exception as erreur:  # noqa: BLE001 - GitHub absent : rien de prêt
            log.warning("version.json illisible : %s", erreur)
            _cache["version"] = {}
        _cache["quand"] = time.monotonic()
    return _cache["version"] or {}


def oublier_version() -> None:
    _cache["quand"] = 0.0


def lancer_fabrication() -> bool:
    """Demande à GitHub de fabriquer les applis (workflow_dispatch). Jeton
    `GITHUB_APK_TOKEN` (droit « Actions : écriture » sur le dépôt) dans
    backend/.env ; sans lui, rien n'est lancé (False)."""
    jeton = os.environ.get("GITHUB_APK_TOKEN", "")
    if not jeton:
        return False
    requete = urllib.request.Request(
        f"https://api.github.com/repos/{DEPOT}/actions/workflows/{ACTION}/dispatches",
        data=json.dumps({"ref": "main"}).encode(),
        method="POST",
        headers={
            "Authorization": f"Bearer {jeton}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "appli-tournage",
        },
    )
    try:
        with urllib.request.urlopen(requete, timeout=10):
            return True
    except Exception as erreur:  # noqa: BLE001
        log.warning("Fabrication de l'appli Android non lancée : %s", erreur)
        return False


def telechargement(ecole: Ecole) -> tuple[str, str] | None:
    """(nom de l'appli, lien du fichier) pour le mail d'invitation d'un
    administrateur sur l'appli Android (Seb 18/11/2026) ; None si l'appli
    de l'école n'est pas allumée ou pas encore publiée."""
    if not ecole.appli_android or ecole.apk_cle is None:
        return None
    url = (version_publiee().get("apk") or {}).get(ecole.apk_cle)
    return (f"Tournage {ecole.nom_appli or ecole.nom}", url) if url else None


def etat(ecole: Ecole, fights_allume: bool) -> dict:
    """Ce que montrent Admin › École › Personnalisation et l'écran
    d'installation : `disponible` (Fights allumé), `actif`, `prete`, `url`
    (le fichier à télécharger) et `date` de la version publiée."""
    actif = fights_allume and ecole.appli_android and ecole.apk_cle is not None
    version = version_publiee() if actif else {}
    url = (version.get("apk") or {}).get(ecole.apk_cle) if actif else None
    return {
        "disponible": fights_allume,
        "actif": actif,
        "prete": url is not None,
        "url": url,
        "date": version.get("date") if url else None,
    }
