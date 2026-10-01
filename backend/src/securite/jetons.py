"""Jetons de session signés (voir spec/SPEC.md §2.2 et §2.5).

À la connexion, le serveur remet un jeton que l'appli renvoie à chaque
requête (en-tête `Authorization: Bearer ...`). Il désigne une ADRESSE EMAIL
(table `acces_emails`, §6.3ter), pas une fiche : le profil actif voyage à
part, dans `X-Compte-Id`, et le serveur vérifie qu'il appartient bien à cet
email (voir comptes/rbac.py). Le serveur recalcule la signature : un jeton
modifié ou fabriqué à la main est refusé, un jeton expiré aussi.

Deux PORTÉES :
- "standard" : tout le monde. 30 jours, prolongés à chaque usage (un
  nouveau jeton est remis au fil de l'eau, voir `a_renouveler`) ;
- "superuser" : le Superuser, au-dessus des écoles (§2.5). 12 heures, jamais
  prolongé. Ses droits ne sont JAMAIS accordés sans ce jeton.

Le jeton porte aussi :
- `rang` : le rang du profil avec lequel la session a été ouverte
  (comptes/roles.py : RANG). Un profil de rang supérieur de la même famille
  n'est accessible qu'après avoir retapé le mot de passe (§2.2 : un enfant
  sur le téléphone d'un parent admin) ;
- `emp` : une empreinte du mot de passe au moment de l'émission. Changer de
  mot de passe la change : tous les jetons déjà remis deviennent invalides,
  ce qui déconnecte les autres appareils (décision du 2026-10-01).

Format : base64url(JSON) + "." + base64url(HMAC-SHA256). Même principe
qu'un JWT, sans dépendance.

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
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

STANDARD = "standard"
SUPERUSER = "superuser"

DUREES_SECONDES = {
    STANDARD: 30 * 24 * 3600,  # décision utilisateur du 2026-10-01
    SUPERUSER: 12 * 3600,  # décision utilisateur du 2026-09-21
}
# "Prolongé à chaque usage" : un jeton "standard" plus vieux que ça est
# remplacé par un neuf à la requête suivante. Pas à CHAQUE requête : inutile
# de réécrire le jeton de l'appareil des dizaines de fois par minute.
AGE_RENOUVELLEMENT_SECONDES = 24 * 3600


@dataclass(frozen=True)
class Jeton:
    acces_email_id: int
    portee: str
    rang: int
    empreinte: str
    emis_le: int


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


def emettre(
    acces_email_id: int,
    *,
    portee: str = STANDARD,
    rang: int = 0,
    empreinte: str = "",
    maintenant: float | None = None,
) -> str:
    maintenant = time.time() if maintenant is None else maintenant
    charge = _b64(
        json.dumps(
            {
                "sub": acces_email_id,
                "portee": portee,
                "rang": rang,
                "emp": empreinte,
                "iat": int(maintenant),
                "exp": int(maintenant + DUREES_SECONDES[portee]),
            }
        ).encode()
    )
    return f"{charge}.{_signer(charge)}"


def lire(jeton: str, maintenant: float | None = None) -> Jeton | None:
    """Le contenu du jeton s'il est intact et pas expiré, sinon None."""
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
    # Un jeton d'avant le 2026-10-01 (sans empreinte, ni portée connue) est
    # refusé : il désignait une fiche, pas une adresse email.
    if contenu.get("portee") not in DUREES_SECONDES or not isinstance(contenu.get("emp"), str):
        return None
    return Jeton(
        acces_email_id=contenu["sub"],
        portee=contenu["portee"],
        rang=int(contenu.get("rang", 0)),
        empreinte=contenu["emp"],
        emis_le=int(contenu.get("iat", 0)),
    )


def a_renouveler(jeton: Jeton, maintenant: float | None = None) -> bool:
    maintenant = time.time() if maintenant is None else maintenant
    return jeton.portee == STANDARD and maintenant - jeton.emis_le > AGE_RENOUVELLEMENT_SECONDES


def depuis_entete(authorization: str | None) -> Jeton | None:
    """Le jeton d'un en-tête `Authorization: Bearer ...`, s'il est valide."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    return lire(authorization[len("bearer "):].strip())
