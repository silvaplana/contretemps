"""Jetons signés du Superuser (voir spec/SPEC.md §2.5).

À la connexion, le serveur remet un jeton valable 12 heures ; le navigateur
le renvoie à chaque requête (en-tête `Authorization: Bearer ...`). Le
serveur recalcule la signature : un jeton modifié ou fabriqué à la main est
refusé, un jeton expiré aussi. Les droits de Superuser ne sont JAMAIS
accordés sans jeton valide (voir comptes/rbac.py).

Format : base64url(JSON {"sub": id, "exp": horodatage}) + "." +
base64url(HMAC-SHA256). Même principe qu'un JWT, sans dépendance.

Le secret de signature : variable d'environnement SECRET_JETONS si elle
existe, sinon un fichier généré au premier usage (voir `_secret`) dans le
volume persistant — il survit aux redéploiements, et n'est jamais dans le
dépôt. Changer ce secret invalide tous les jetons en cours.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from functools import lru_cache
from pathlib import Path

DUREE_SECONDES = 12 * 3600  # décision utilisateur du 2026-09-21


def _b64(octets: bytes) -> str:
    return base64.urlsafe_b64encode(octets).decode("ascii").rstrip("=")


def _d64(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def _chemin_fichier_secret() -> Path:
    explicite = os.environ.get("FICHIER_SECRET_JETONS")
    if explicite:
        return Path(explicite)
    # Par défaut, à côté de la base SQLite : /app/data en prod (volume
    # persistant, voir backend/Dockerfile), le dossier backend/ en dev.
    url = os.environ.get("DATABASE_URL", "sqlite:///./contretemps.db")
    if url.startswith("sqlite:///"):
        return Path(url.removeprefix("sqlite:///")).resolve().parent / "secret_jetons"
    raise RuntimeError("Définir SECRET_JETONS ou FICHIER_SECRET_JETONS (base non SQLite)")


@lru_cache(maxsize=1)
def _secret() -> bytes:
    valeur = os.environ.get("SECRET_JETONS")
    if valeur:
        return valeur.encode("utf-8")
    chemin = _chemin_fichier_secret()
    if not chemin.exists():
        chemin.parent.mkdir(parents=True, exist_ok=True)
        chemin.write_text(secrets.token_urlsafe(48), encoding="utf-8")
        chemin.chmod(0o600)
    return chemin.read_text(encoding="utf-8").strip().encode("utf-8")


def _signer(charge: str) -> str:
    return _b64(hmac.new(_secret(), charge.encode("ascii"), hashlib.sha256).digest())


def emettre(compte_id: int, maintenant: float | None = None) -> str:
    maintenant = time.time() if maintenant is None else maintenant
    charge = _b64(json.dumps({"sub": compte_id, "exp": int(maintenant + DUREE_SECONDES)}).encode())
    return f"{charge}.{_signer(charge)}"


def verifier(jeton: str, maintenant: float | None = None) -> int | None:
    """L'id du compte si le jeton est intact et pas expiré, sinon None."""
    try:
        charge, signature = jeton.split(".")
        if not hmac.compare_digest(signature, _signer(charge)):
            return None
        contenu = json.loads(_d64(charge))
    except (ValueError, TypeError):
        return None
    maintenant = time.time() if maintenant is None else maintenant
    if not isinstance(contenu.get("sub"), int) or contenu.get("exp", 0) <= maintenant:
        return None
    return contenu["sub"]
