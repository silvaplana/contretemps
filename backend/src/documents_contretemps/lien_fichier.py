"""Ouvrir un PDF des Docs dans la visionneuse du téléphone (Seb, 21 octobre).

Le téléphone (Chrome Android) n'affiche pas un PDF dans la page : il faut
lui donner une vraie adresse, qu'il ouvre avec sa visionneuse. Il ne sait
pas y joindre la session : l'adresse porte un lien signé à durée limitée
(securite/liens.py, comme les vidéos), remis à qui a le droit de lire le
fichier. Elle désigne ce contenu précis : une nouvelle version a un autre
lien, et l'ancien ne sert plus rien.
"""

from __future__ import annotations

from dataclasses import replace

from documents.models import DocNode, DocVersion, StoredFile
from documents.ports import Member
from documents.receiver import _disposition
from documents.service import DocError, Documents
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from securite import liens
from sqlalchemy.orm import Session

from db import get_db


def brancher(app: FastAPI, documents: Documents, current_member) -> None:
    @app.get("/documents/orgs/{org_id}/nodes/{node_id}/link")
    def lien(org_id: int, node_id: int, db: Session = Depends(get_db), m: Member = Depends(current_member)):
        try:
            chemin, _, _ = documents.content(db, replace(m, org_id=org_id), node_id)
        except DocError as erreur:
            raise HTTPException(status_code=erreur.status, detail=erreur.message) from erreur
        sha = chemin.name
        return {"url": f"/documents/fichiers/{node_id}?h={sha}&{liens.parametres(f'doc:{node_id}:{sha}')}"}

    @app.get("/documents/fichiers/{node_id}")
    def fichier(node_id: int, h: str | None = None, e: str | None = None, s: str | None = None, db: Session = Depends(get_db)):
        if not h or not liens.valide(f"doc:{node_id}:{h}", e, s):
            raise HTTPException(status_code=403, detail="Lien expiré : rouvrez le fichier dans l'appli")
        node = db.get(DocNode, node_id)
        version = db.get(DocVersion, node.current_version_id or 0) if node and node.deleted_at is None else None
        stocke = db.get(StoredFile, version.stored_file_id) if version else None
        if stocke is None or stocke.sha256 != h:
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        chemin = documents.storage.path(node.org_id, h)
        if not chemin.is_file():
            raise HTTPException(status_code=404, detail="Fichier introuvable")
        return FileResponse(
            chemin, media_type=stocke.mime,
            headers={"Content-Disposition": _disposition(node.name, False), "Cache-Control": "private, max-age=21600"},
        )
