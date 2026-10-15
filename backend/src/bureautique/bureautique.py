"""Édition de Word, Excel et PowerPoint dans l'appli avec OnlyOffice
(essai, Seb 16 octobre). Le serveur de documents OnlyOffice est partagé par
les applis du VPS (~/onlyoffice, https://silvaplana.cloud/onlyoffice/).

Déroulé :
1. l'appli demande la configuration de l'éditeur (`configuration`) ; elle
   porte deux adresses de Contretemps, chacune avec un jeton signé : où
   OnlyOffice lit le fichier, et où il renvoie le fichier modifié ;
2. OnlyOffice lit le fichier (`fichier`), puis, à l'enregistrement, appelle
   le retour (`retour`) avec l'adresse du fichier modifié : Contretemps le
   télécharge et en fait une nouvelle version dans Documents (droits de la
   personne qui a ouvert l'éditeur, historique et retour arrière habituels).

Tous les échanges avec OnlyOffice sont signés (JWT HS256, clé partagée
ONLYOFFICE_JWT_SECRET) : OnlyOffice refuse une configuration non signée, et
Contretemps refuse un retour dont la signature ne correspond pas."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import io
import logging
import os
import time
import urllib.request

from documents.ports import Member
from documents.preview import extension
from documents.service import Documents

logger = logging.getLogger(__name__)

TYPES = {
    "word": {".doc", ".docx", ".odt", ".rtf", ".txt"},
    "cell": {".xls", ".xlsx", ".ods", ".csv"},
    "slide": {".ppt", ".pptx", ".odp"},
}
DUREE_JETON = 24 * 3600  # le retour peut arriver après la fermeture de l'éditeur
TAILLE_MAX_RETOUR = 200 * 1024 * 1024


def _b64(octets: bytes) -> str:
    return base64.urlsafe_b64encode(octets).rstrip(b"=").decode("ascii")


def _de_b64(texte: str) -> bytes:
    return base64.urlsafe_b64decode(texte + "=" * (-len(texte) % 4))


def jwt_signer(charge: dict, secret: str) -> str:
    entete = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    corps = _b64(json.dumps(charge, separators=(",", ":"), ensure_ascii=False).encode())
    signature = _b64(hmac.new(secret.encode(), f"{entete}.{corps}".encode(), hashlib.sha256).digest())
    return f"{entete}.{corps}.{signature}"


def jwt_lire(jeton: str, secret: str) -> dict | None:
    try:
        entete, corps, signature = jeton.split(".")
        attendu = _b64(hmac.new(secret.encode(), f"{entete}.{corps}".encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(attendu, signature):
            return None
        return json.loads(_de_b64(corps))
    except (ValueError, json.JSONDecodeError):
        return None


def type_document(nom: str) -> str | None:
    ext = extension(nom)
    return next((t for t, exts in TYPES.items() if ext in exts), None)


class Bureautique:
    def __init__(self, documents: Documents, membre_de=None) -> None:
        """`membre_de(db, compte_id, org_id)` : le membre qui a ouvert
        l'éditeur, retrouvé au moment du retour (branché par app/main.py)."""
        self.documents = documents
        self.membre_de = membre_de

    @property
    def secret(self) -> str | None:
        return os.environ.get("ONLYOFFICE_JWT_SECRET") or None

    @property
    def adresse(self) -> str:
        return os.environ.get("ONLYOFFICE_URL", "https://silvaplana.cloud/onlyoffice").rstrip("/")

    @property
    def actif(self) -> bool:
        return self.secret is not None

    # Jeton de Contretemps (dans les adresses données à OnlyOffice).
    def _jeton(self, org_id: int, node_id: int, compte_id: int) -> str:
        return jwt_signer({"o": org_id, "n": node_id, "c": compte_id, "exp": int(time.time()) + DUREE_JETON}, self.secret)

    def lire_jeton(self, jeton: str) -> dict | None:
        charge = jwt_lire(jeton, self.secret) if self.secret else None
        if charge is None or charge.get("exp", 0) < time.time():
            return None
        return charge

    def configuration(self, db, member: Member, compte_id: int, node_id: int, base_api: str) -> dict:
        """Configuration de l'éditeur, signée. Modification si la personne
        peut modifier le fichier (et qu'il n'est ni officiel ni d'une saison
        close), lecture sinon."""
        detail = self.documents.detail(db, member, node_id)
        genre = type_document(detail["name"])
        if detail["kind"] != "file" or genre is None:
            raise ValueError("Ce fichier ne s'ouvre pas dans l'éditeur.")
        modifiable = detail.get("level") in ("edit", "manage") and not detail.get("frozen") and not detail.get("closed_period")
        jeton = self._jeton(member.org_id, node_id, compte_id)
        # Même clé pour tous tant que le contenu ne change pas : ceux qui
        # ouvrent le même fichier en même temps éditent ensemble.
        cle = hashlib.sha256(f"{member.org_id}-{node_id}-{detail.get('updated_at')}".encode()).hexdigest()[:40]
        config = {
            "document": {
                "fileType": extension(detail["name"]).lstrip("."),
                "key": cle,
                "title": detail["name"],
                "url": f"{base_api}/bureautique/fichier/{jeton}",
                "permissions": {"edit": modifiable, "download": True, "print": True},
            },
            "documentType": genre,
            "editorConfig": {
                "callbackUrl": f"{base_api}/bureautique/retour/{jeton}",
                "lang": "fr",
                "region": "fr-FR",
                "mode": "edit" if modifiable else "view",
                "user": {"id": str(member.person_id), "name": member.display_name or "Contretemps"},
                "customization": {"forcesave": True, "autosave": True, "compactHeader": True},
            },
            "width": "100%",
            "height": "100%",
            "type": "desktop",
        }
        config["token"] = jwt_signer(config, self.secret)
        return {"config": config, "api_js": f"{self.adresse}/web-apps/apps/api/documents/api.js", "modifiable": modifiable}

    def retour(self, db, charge_jeton: dict, corps: dict) -> None:
        """Appel d'OnlyOffice : statut 2 (document prêt après fermeture) ou
        6 (enregistrement forcé) -> nouvelle version dans Documents."""
        if corps.get("status") not in (2, 6) or not corps.get("url"):
            return
        url = corps["url"]
        if not url.startswith(self.adresse + "/"):
            raise ValueError("Adresse de fichier inattendue")
        with urllib.request.urlopen(url, timeout=60) as reponse:
            contenu = reponse.read(TAILLE_MAX_RETOUR + 1)
        if len(contenu) > TAILLE_MAX_RETOUR:
            raise ValueError("Fichier modifié trop gros")
        member = self.membre_de(db, charge_jeton["c"], charge_jeton["o"])
        detail = self.documents.detail(db, member, charge_jeton["n"])
        self.documents.new_version(db, member, charge_jeton["n"], detail["name"], io.BytesIO(contenu))
        logger.info("OnlyOffice : nouvelle version du fichier %s", charge_jeton["n"])
