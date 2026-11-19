"""Lire et écrire dans un drive (spec/core.md §3, « Drives du club »).

Un client par fournisseur, mêmes quatre gestes : `check()`, `list(path)`,
`read(path)`, `write(folder, name, content, mime)`. Un chemin est une suite
de noms de dossiers séparés par « / », sans « / » au début (« FINANCIER/
SALAIRES ») ; la racine est « ».

- kDrive (Infomaniak) : WebDAV, adresse du compte et mot de passe
  d'application, `https://<numéro>.connect.kdrive.infomaniak.com`.
- Google Drive : un compte de service de l'appli (clé JSON du serveur,
  variable GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE) ; le club partage ses dossiers
  avec l'adresse de ce compte. La racine liste les dossiers partagés.
"""

from __future__ import annotations

import base64
import json
import os
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit

import httpx

TIMEOUT = 30


class DriveError(Exception):
    """Le drive n'a pas répondu comme prévu (réseau, serveur)."""


class DriveRefused(DriveError):
    """Le drive refuse l'accès (mot de passe changé, partage retiré)."""


class DriveNotFound(DriveError):
    """Dossier ou fichier introuvable."""


@dataclass(frozen=True)
class Entry:
    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified: datetime | None = None


def join(folder: str, name: str) -> str:
    folder = folder.strip("/")
    return f"{folder}/{name}" if folder else name


# --- kDrive (WebDAV) ---------------------------------------------------------

DAV = "{DAV:}"


class KDrive:
    def __init__(self, address: str, password: str, drive_ref: str, http: httpx.Client | None = None) -> None:
        self.base = f"https://{drive_ref.strip()}.connect.kdrive.infomaniak.com"
        self.http = http or httpx.Client(auth=(address, password), timeout=TIMEOUT)

    def _url(self, path: str) -> str:
        parts = [quote(p) for p in path.strip("/").split("/") if p]
        return self.base + "/" + "/".join(parts)

    def _send(self, method: str, path: str, **kwargs) -> httpx.Response:
        try:
            reponse = self.http.request(method, self._url(path), **kwargs)
        except httpx.HTTPError as erreur:
            raise DriveError("Le kDrive ne répond pas. Réessayez dans un moment.") from erreur
        if reponse.status_code in (401, 403):
            raise DriveRefused("Infomaniak n'a pas accepté l'adresse ou le mot de passe d'application.")
        if reponse.status_code == 404:
            raise DriveNotFound("Introuvable sur le kDrive.")
        if reponse.status_code >= 400:
            raise DriveError(f"Le kDrive a répondu {reponse.status_code}.")
        return reponse

    def check(self) -> None:
        self._send("PROPFIND", "", headers={"Depth": "0"})

    def list(self, path: str = "") -> list[Entry]:
        reponse = self._send("PROPFIND", path, headers={"Depth": "1"})
        racine = urlsplit(self._url(path)).path.rstrip("/")
        entries = []
        for r in ET.fromstring(reponse.content).iter(f"{DAV}response"):
            href = unquote(urlsplit(r.findtext(f"{DAV}href", "")).path).rstrip("/")
            if href == unquote(racine):
                continue
            prop = r.find(f"{DAV}propstat/{DAV}prop")
            is_dir = prop is not None and prop.find(f"{DAV}resourcetype/{DAV}collection") is not None
            size = int((prop.findtext(f"{DAV}getcontentlength") if prop is not None else None) or 0)
            modified = None
            texte = prop.findtext(f"{DAV}getlastmodified") if prop is not None else None
            if texte:
                try:
                    modified = parsedate_to_datetime(texte)
                except (TypeError, ValueError):
                    modified = None
            name = href.rsplit("/", 1)[-1]
            entries.append(Entry(name=name, path=join(path, name), is_dir=is_dir, size=size, modified=modified))
        return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))

    def read(self, path: str) -> bytes:
        return self._send("GET", path).content

    def write(self, folder: str, name: str, content: bytes, mime: str = "application/octet-stream") -> str:
        path = join(folder, name)
        self._send("PUT", path, content=content, headers={"Content-Type": mime})
        return path


# --- Google Drive (compte de service) ----------------------------------------

API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"


def service_account() -> dict | None:
    """La clé JSON du compte de service, ou None si le serveur n'en a pas
    (Google Drive pas encore proposé, spec/core.md §3)."""
    chemin = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", "").strip()
    if not chemin or not Path(chemin).is_file():
        return None
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


class GoogleDrive:
    def __init__(self, key: dict, http: httpx.Client | None = None) -> None:
        self.key = key
        self.http = http or httpx.Client(timeout=TIMEOUT)
        self._token: tuple[str, float] | None = None

    def _access_token(self) -> str:
        if self._token and self._token[1] > time.time() + 60:
            return self._token[0]
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding

        now = int(time.time())
        head = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
        claims = _b64(json.dumps({
            "iss": self.key["client_email"], "scope": "https://www.googleapis.com/auth/drive",
            "aud": "https://oauth2.googleapis.com/token", "iat": now, "exp": now + 3600,
        }).encode())
        private = serialization.load_pem_private_key(self.key["private_key"].encode(), password=None)
        signature = _b64(private.sign(f"{head}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256()))
        try:
            reponse = self.http.post("https://oauth2.googleapis.com/token", data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": f"{head}.{claims}.{signature}",
            })
        except httpx.HTTPError as erreur:
            raise DriveError("Google Drive ne répond pas. Réessayez dans un moment.") from erreur
        if reponse.status_code != 200:
            raise DriveError("La clé Google Drive du serveur est refusée par Google.")
        token = reponse.json()["access_token"]
        self._token = (token, now + int(reponse.json().get("expires_in", 3600)))
        return token

    def _get(self, url: str, **params) -> httpx.Response:
        try:
            reponse = self.http.get(url, params=params, headers={"Authorization": f"Bearer {self._access_token()}"})
        except httpx.HTTPError as erreur:
            raise DriveError("Google Drive ne répond pas. Réessayez dans un moment.") from erreur
        if reponse.status_code in (401, 403):
            raise DriveRefused("Google Drive refuse l'accès : le dossier n'est plus partagé avec l'appli ?")
        if reponse.status_code == 404:
            raise DriveNotFound("Introuvable sur Google Drive.")
        if reponse.status_code >= 400:
            raise DriveError(f"Google Drive a répondu {reponse.status_code}.")
        return reponse

    def _files(self, q: str) -> list[dict]:
        files, page = [], None
        while True:
            params = {"q": q, "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime)", "pageSize": 1000,
                      "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
            if page:
                params["pageToken"] = page
            data = self._get(f"{API}/files", **params).json()
            files += data.get("files", [])
            page = data.get("nextPageToken")
            if not page:
                return files

    def _id(self, path: str) -> str | None:
        """L'identifiant Google d'un chemin ; None pour la racine."""
        current = None
        for name in [p for p in path.strip("/").split("/") if p]:
            safe = name.replace("\\", "\\\\").replace("'", "\\'")
            where = "sharedWithMe" if current is None else f"'{current}' in parents"
            found = self._files(f"{where} and name = '{safe}' and trashed = false")
            if not found:
                raise DriveNotFound("Introuvable sur Google Drive.")
            current = found[0]["id"]
        return current

    def check(self) -> None:
        if not self.list(""):
            raise DriveRefused("Aucun dossier n'est encore partagé avec l'adresse de l'appli.")

    def list(self, path: str = "") -> list[Entry]:
        folder = self._id(path)
        q = f"mimeType = '{FOLDER}' and sharedWithMe and trashed = false" if folder is None else (
            f"'{folder}' in parents and trashed = false")
        entries = []
        for f in self._files(q):
            modified = None
            if f.get("modifiedTime"):
                modified = datetime.fromisoformat(f["modifiedTime"].replace("Z", "+00:00"))
            entries.append(Entry(name=f["name"], path=join(path, f["name"]), is_dir=f["mimeType"] == FOLDER,
                                 size=int(f.get("size") or 0), modified=modified))
        return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))

    def read(self, path: str) -> bytes:
        file_id = self._id(path)
        if file_id is None:
            raise DriveNotFound("Introuvable sur Google Drive.")
        return self._get(f"{API}/files/{file_id}", alt="media", supportsAllDrives="true").content

    def write(self, folder: str, name: str, content: bytes, mime: str = "application/octet-stream") -> str:
        parent = self._id(folder)
        if parent is None:
            raise DriveError("Choisissez un dossier partagé, pas la racine.")
        boundary = "auto-import-boundary"
        meta = json.dumps({"name": name, "parents": [parent]})
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{meta}\r\n"
                f"--{boundary}\r\nContent-Type: {mime}\r\n\r\n").encode() + content + f"\r\n--{boundary}--".encode()
        try:
            reponse = self.http.post(
                UPLOAD, params={"uploadType": "multipart", "supportsAllDrives": "true"}, content=body,
                headers={"Authorization": f"Bearer {self._access_token()}",
                         "Content-Type": f"multipart/related; boundary={boundary}"},
            )
        except httpx.HTTPError as erreur:
            raise DriveError("Google Drive ne répond pas. Réessayez dans un moment.") from erreur
        if reponse.status_code in (401, 403):
            raise DriveRefused("Google Drive refuse d'écrire : partagez le dossier en « Éditeur ».")
        if reponse.status_code >= 400:
            raise DriveError(f"Google Drive a répondu {reponse.status_code}.")
        return join(folder, name)
