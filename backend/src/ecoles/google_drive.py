"""Envoi des 2 fichiers de sauvegarde programmée vers Google Drive (voir
app/sauvegarde_worker.py) — via un COMPTE DE SERVICE (décision utilisateur
explicite) : le worker tourne sans personne présent pour se connecter à la
main, un compte de service Google n'a besoin d'aucune interaction humaine
une fois configuré.

Optionnel — comme SMTP/HelloAsso (voir .env.example) : sans configuration,
`est_configure()` renvoie False et le worker se contente du filet de
sécurité serveur existant (voir ecoles/stockage.py), sans erreur.

Appels REST directs à l'API Drive v3 (voir `requests`, déjà une
dépendance — même choix que inscriptions/helloasso.py) plutôt que le SDK
google-api-python-client (plus lourd, plus de dépendances transitives) :
seul `google-auth` est nécessaire, pour échanger la clé du compte de
service contre un jeton d'accès.

⚠️ Pas de Drive gratuit pour un compte de service seul (pas de quota de
stockage propre, sauf Google Workspace payant) : le dossier cible
(GOOGLE_DRIVE_DOSSIER_ID) doit être un dossier d'un VRAI compte Google
(l'école), partagé en édition avec l'adresse email du compte de service —
voir spec/SPEC.md ou le message à l'utilisateur pour la procédure pas à
pas.
"""

from __future__ import annotations

import json
import os

import requests
from google.auth.transport.requests import Request
from google.oauth2 import service_account

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
MEDIA_TYPE_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class GoogleDrive:
    def __init__(self) -> None:
        self.fichier_cle = os.environ.get("GOOGLE_DRIVE_SERVICE_ACCOUNT_FILE")
        self.dossier_id = os.environ.get("GOOGLE_DRIVE_DOSSIER_ID")

    def est_configure(self) -> bool:
        return bool(self.fichier_cle and self.dossier_id and os.path.isfile(self.fichier_cle))

    def _jeton_acces(self) -> str:
        credentials = service_account.Credentials.from_service_account_file(
            self.fichier_cle, scopes=SCOPES
        )
        credentials.refresh(Request())
        return credentials.token

    def televerser(self, nom_fichier: str, contenu: bytes) -> None:
        """Envoie un fichier dans le dossier configuré. Lève une exception
        si ça échoue — laissé à l'appelant (voir sauvegarde_worker.py) de
        logguer sans jamais bloquer le filet de sécurité serveur, déjà
        écrit avant cet appel."""
        jeton = self._jeton_acces()
        metadonnees = {"name": nom_fichier, "parents": [self.dossier_id]}
        reponse = requests.post(
            "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
            headers={"Authorization": f"Bearer {jeton}"},
            files={
                "metadata": (None, json.dumps(metadonnees), "application/json"),
                "media": (nom_fichier, contenu, MEDIA_TYPE_XLSX),
            },
            timeout=30,
        )
        reponse.raise_for_status()
