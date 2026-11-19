"""Lire et écrire dans un drive (spec/core.md §3, « Drives du club »).

Un client par fournisseur, mêmes quatre gestes : `check()`, `list(path)`,
`read(path)`, `write(folder, name, content, mime)`. Un chemin est une suite
de noms de dossiers séparés par « / », sans « / » au début (« FINANCIER/
SALAIRES ») ; la racine est « ».

- kDrive (Infomaniak) : l'API d'Infomaniak avec un jeton (droit « drive »)
  et le numéro du kDrive ; WebDAV est fermé avec my kSuite (Seb, 19 novembre).
- Google Drive : un compte de service de l'appli (clé JSON du serveur,
  /run/secrets/google_drive.json ou la variable
  GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE, DEPLOY.md §4) ; le club partage ses dossiers
  avec l'adresse de ce compte. La racine liste les dossiers partagés.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

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


# --- kDrive (API d'Infomaniak) ------------------------------------------------

KDRIVE_API = "https://api.infomaniak.com"
KDRIVE_ROOT = 1  # la racine du kDrive : « Private » (Mon dossier), « Common documents »…


class KDrive:
    """kDrive par l'API d'Infomaniak avec un jeton (droit « drive ») : marche
    avec toutes les offres, y compris my kSuite où WebDAV est fermé (Seb,
    19 novembre). `secret` = le jeton, `drive_ref` = le numéro du kDrive."""

    def __init__(self, address: str, token: str, drive_ref: str, http: httpx.Client | None = None) -> None:
        self.drive = drive_ref.strip()
        self.http = http or httpx.Client(timeout=TIMEOUT, follow_redirects=True)
        self.headers = {"Authorization": f"Bearer {token.strip()}"}

    def _send(self, method: str, url: str, headers: dict | None = None, **kwargs) -> httpx.Response:
        try:
            reponse = self.http.request(method, KDRIVE_API + url, headers={**self.headers, **(headers or {})}, **kwargs)
        except httpx.HTTPError as erreur:
            raise DriveError("Le kDrive ne répond pas. Réessayez dans un moment.") from erreur
        if reponse.status_code in (401, 403):
            raise DriveRefused("Infomaniak n'a pas accepté le jeton, ou il n'a pas le droit « drive » sur ce kDrive.")
        code = ""
        if reponse.headers.get("content-type", "").startswith("application/json"):
            corps = reponse.json()
            if isinstance(corps, dict) and corps.get("result") == "error":
                code = (corps.get("error") or {}).get("code", "")
        if reponse.status_code == 404 or code == "object_not_found":
            raise DriveNotFound("Introuvable sur le kDrive.")
        if code in ("not_authorized", "unauthorized", "forbidden", "access_denied"):
            raise DriveRefused("Infomaniak n'a pas accepté le jeton, ou il n'a pas le droit « drive » sur ce kDrive.")
        if reponse.status_code >= 400 or code:
            raise DriveError(f"Le kDrive a répondu {reponse.status_code} {code}".strip() + ".")
        return reponse

    def _children(self, folder_id: int) -> list[dict]:
        items, cursor = [], None
        while True:
            params = {"limit": 1000, **({"cursor": cursor} if cursor else {})}
            data = self._send("GET", f"/3/drive/{self.drive}/files/{folder_id}/files", params=params).json()
            items += data.get("data") or []
            cursor = data.get("cursor")
            if not data.get("has_more") or not cursor:
                return items

    def _id(self, path: str) -> int:
        current = KDRIVE_ROOT
        for name in [p for p in path.strip("/").split("/") if p]:
            found = next((i for i in self._children(current) if i.get("name") == name), None)
            if found is None:
                raise DriveNotFound("Introuvable sur le kDrive.")
            current = found["id"]
        return current

    def check(self) -> None:
        self._send("GET", f"/3/drive/{self.drive}/files/{KDRIVE_ROOT}")

    def list(self, path: str = "") -> list[Entry]:
        entries = []
        for i in self._children(self._id(path)):
            stamp = i.get("last_modified_at") or i.get("created_at")
            entries.append(Entry(
                name=i["name"], path=join(path, i["name"]), is_dir=i.get("type") == "dir", size=int(i.get("size") or 0),
                modified=datetime.fromtimestamp(stamp, timezone.utc) if stamp else None,
            ))
        return sorted(entries, key=lambda e: (not e.is_dir, e.name.lower()))

    def read(self, path: str) -> bytes:
        return self._send("GET", f"/2/drive/{self.drive}/files/{self._id(path)}/download").content

    def folder(self, path: str) -> str:
        """Creates the folders of `path` that are missing; returns it."""
        done = ""
        for name in [p for p in path.strip("/").split("/") if p]:
            done = join(done, name)
            try:
                reponse = self.http.request("MKCOL", self._url(done))
            except httpx.HTTPError as erreur:
                raise DriveError("Le kDrive ne répond pas. Réessayez dans un moment.") from erreur
            if reponse.status_code in (401, 403):
                raise DriveRefused("Infomaniak n'a pas accepté l'adresse ou le mot de passe d'application.")
            if reponse.status_code not in (201, 405):  # 405: already there
                raise DriveError(f"Le kDrive a répondu {reponse.status_code}.")
        return done

    def write(self, folder: str, name: str, content: bytes, mime: str = "application/octet-stream") -> str:
        self._send(
            "POST", f"/3/drive/{self.drive}/upload", content=content,
            params={"file_name": name, "directory_id": self._id(folder), "total_size": len(content), "conflict": "version"},
            headers={"Content-Type": "application/octet-stream"},
        )
        return join(folder, name)


# --- Google Drive (compte de service) ----------------------------------------

API = "https://www.googleapis.com/drive/v3"
UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
FOLDER = "application/vnd.google-apps.folder"
KEY_FILE = "/run/secrets/google_drive.json"


def service_account() -> dict | None:
    """La clé JSON du compte de service, ou None si le serveur n'en a pas
    (Google Drive pas encore proposé, spec/core.md §3)."""
    chemin = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE", "").strip() or KEY_FILE
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
            params = {"q": q, "fields": "nextPageToken,files(id,name,mimeType,size,modifiedTime,parents)", "pageSize": 1000,
                      "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}
            if page:
                params["pageToken"] = page
            data = self._get(f"{API}/files", **params).json()
            files += data.get("files", [])
            page = data.get("nextPageToken")
            if not page:
                return files

    def _roots(self) -> list[dict]:
        """Les dossiers partagés avec l'appli : ceux qu'elle voit et dont le
        parent ne lui est pas visible. Plus sûr que `sharedWithMe`, que Google
        ne remplit pas toujours pour un compte de service (Seb, 19 novembre)."""
        folders = self._files(f"mimeType = '{FOLDER}' and trashed = false")
        ids = {f["id"] for f in folders}
        return [f for f in folders if not set(f.get("parents") or []) & ids]

    def _id(self, path: str) -> str | None:
        """L'identifiant Google d'un chemin ; None pour la racine."""
        current = None
        for name in [p for p in path.strip("/").split("/") if p]:
            if current is None:
                found = [f for f in self._roots() if f["name"] == name]
            else:
                safe = name.replace("\\", "\\\\").replace("'", "\\'")
                found = self._files(f"'{current}' in parents and name = '{safe}' and trashed = false")
            if not found:
                raise DriveNotFound("Introuvable sur Google Drive.")
            current = found[0]["id"]
        return current

    def check(self) -> None:
        if not self.list(""):
            raise DriveRefused(
                "Google Drive ne montre aucun dossier partagé avec l'adresse de l'appli : partagez un dossier "
                "(pas un fichier) avec cette adresse, puis réessayez dans une minute.")

    def list(self, path: str = "") -> list[Entry]:
        folder = self._id(path)
        entries = []
        for f in self._roots() if folder is None else self._files(f"'{folder}' in parents and trashed = false"):
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

    def folder(self, path: str) -> str:
        """Creates the folders of `path` that are missing, under a folder
        shared with the app; returns it."""
        current, done = None, ""
        for name in [p for p in path.strip("/").split("/") if p]:
            done = join(done, name)
            safe = name.replace("\\", "\\\\").replace("'", "\\'")
            where = "sharedWithMe" if current is None else f"'{current}' in parents"
            found = self._files(f"{where} and name = '{safe}' and mimeType = '{FOLDER}' and trashed = false")
            if found:
                current = found[0]["id"]
                continue
            if current is None:
                raise DriveError("Choisissez un dossier partagé, pas la racine.")
            try:
                reponse = self.http.post(
                    f"{API}/files", params={"supportsAllDrives": "true"},
                    json={"name": name, "mimeType": FOLDER, "parents": [current]},
                    headers={"Authorization": f"Bearer {self._access_token()}"},
                )
            except httpx.HTTPError as erreur:
                raise DriveError("Google Drive ne répond pas. Réessayez dans un moment.") from erreur
            if reponse.status_code in (401, 403):
                raise DriveRefused("Google Drive refuse d'écrire : partagez le dossier en « Éditeur ».")
            if reponse.status_code >= 400:
                raise DriveError(f"Google Drive a répondu {reponse.status_code}.")
            current = reponse.json()["id"]
        return done

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
