"""Routes REST du module documents. Ne fait que traduire HTTP <-> appels à
`Documents` (service.py) ; les droits sont vérifiés par le service.

Toutes les routes sont sous `/documents/orgs/{org_id}/…`. La personne qui
appelle est fournie par l'appli hôte (`current_member`, une dépendance
FastAPI : voir documents_contretemps/adapter.py).
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from db import get_db

from .ports import Member
from .service import DocError, Documents
from .storage import FileTooLarge


class NewFolder(BaseModel):
    space: str
    parent_id: int | None = None
    name: str


class NodeUpdate(BaseModel):
    name: str | None = None
    # Déplacer : `move` à vrai, avec l'espace et le dossier de destination
    # (parent_id None = racine de l'espace).
    move: bool = False
    space: str | None = None
    parent_id: int | None = None
    # Changer le statut : `change_status` à vrai (status None = sans statut).
    change_status: bool = False
    status: str | None = None
    pinned: bool | None = None


class CopyTarget(BaseModel):
    space: str
    parent_id: int | None = None


class AccessEntry(BaseModel):
    type: str
    id: str
    level: str


class AccessUpdate(BaseModel):
    restricted: bool = False
    entries: list[AccessEntry] = []


def _http(erreur: DocError) -> HTTPException:
    return HTTPException(status_code=erreur.status, detail=erreur.message)


def _disposition(nom: str, telecharger: bool) -> str:
    mode = "attachment" if telecharger else "inline"
    ascii_ = nom.encode("ascii", "replace").decode("ascii").replace('"', "")
    return f"{mode}; filename=\"{ascii_}\"; filename*=UTF-8''{quote(nom)}"


class DocumentsReceiver:
    def __init__(self, client: Documents, app: FastAPI, current_member: Callable[..., Member]) -> None:
        self.client = client
        self.app = app
        self.current_member = current_member
        self._register_routes()

    def _member(self, org_id: int, member: Member) -> Member:
        if member.org_id != org_id and not member.is_superuser:
            raise HTTPException(status_code=403, detail="Réservé aux membres de cette organisation")
        if member.org_id != org_id:
            # Superuser : agit dans l'organisation choisie.
            from dataclasses import replace

            member = replace(member, org_id=org_id)
        return member

    def _register_routes(self) -> None:
        base = "/documents/orgs/{org_id}"
        member = Depends(self.current_member)
        db_dep = Depends(get_db)

        def appel(fonction):
            try:
                return fonction()
            except DocError as erreur:
                raise _http(erreur) from erreur

        @self.app.get(base + "/spaces")
        def spaces(org_id: int, m: Member = member):
            return self.client.spaces(self._member(org_id, m))

        @self.app.get(base + "/spaces/{space}")
        def browse(org_id: int, space: str, folder: int | None = None, db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.browse(db, self._member(org_id, m), space, folder))

        @self.app.get(base + "/spaces/{space}/search")
        def search(org_id: int, space: str, q: str = "", db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.search(db, self._member(org_id, m), space, q))

        @self.app.get(base + "/spaces/{space}/trash")
        def trash(org_id: int, space: str, db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.trash(db, self._member(org_id, m), space))

        @self.app.post(base + "/folders", status_code=201)
        def create_folder(org_id: int, data: NewFolder, db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.create_folder(db, self._member(org_id, m), data.space, data.parent_id, data.name))

        @self.app.post(base + "/files", status_code=201)
        def upload(
            org_id: int,
            space: str = Form(...),
            parent_id: int | None = Form(None),
            file: UploadFile = File(...),
            db: Session = db_dep,
            m: Member = member,
        ):
            try:
                return appel(
                    lambda: self.client.upload(db, self._member(org_id, m), space, parent_id, file.filename or "fichier", file.file)
                )
            except FileTooLarge as erreur:
                raise HTTPException(status_code=413, detail=str(erreur)) from erreur

        @self.app.get(base + "/nodes/{node_id}")
        def detail(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.detail(db, self._member(org_id, m), node_id))

        @self.app.patch(base + "/nodes/{node_id}")
        def update(org_id: int, node_id: int, data: NodeUpdate, db: Session = db_dep, m: Member = member):
            return appel(
                lambda: self.client.update(
                    db, self._member(org_id, m), node_id,
                    name=data.name, move=data.move, space=data.space, parent_id=data.parent_id,
                    change_status=data.change_status, status=data.status, pinned=data.pinned,
                )
            )

        @self.app.delete(base + "/nodes/{node_id}", status_code=204)
        def delete(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            appel(lambda: self.client.delete(db, self._member(org_id, m), node_id))

        @self.app.post(base + "/nodes/{node_id}/copy", status_code=201)
        def copy(org_id: int, node_id: int, data: CopyTarget, db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.copy(db, self._member(org_id, m), node_id, data.space, data.parent_id))

        @self.app.post(base + "/nodes/{node_id}/restore")
        def restore(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.restore(db, self._member(org_id, m), node_id))

        @self.app.post(base + "/nodes/{node_id}/versions", status_code=201)
        def new_version(org_id: int, node_id: int, file: UploadFile = File(...), db: Session = db_dep, m: Member = member):
            try:
                return appel(
                    lambda: self.client.new_version(db, self._member(org_id, m), node_id, file.filename or "fichier", file.file)
                )
            except FileTooLarge as erreur:
                raise HTTPException(status_code=413, detail=str(erreur)) from erreur

        @self.app.get(base + "/nodes/{node_id}/content")
        def content(
            org_id: int, node_id: int, version: int | None = None, download: bool = False,
            db: Session = db_dep, m: Member = member,
        ):
            chemin, nom, mime = appel(lambda: self.client.content(db, self._member(org_id, m), node_id, version))
            if not chemin.exists():
                raise HTTPException(status_code=404, detail="Contenu introuvable sur le serveur")
            return FileResponse(
                chemin, media_type=mime,
                headers={"Content-Disposition": _disposition(nom, download), "Cache-Control": "private, max-age=300"},
            )

        @self.app.get(base + "/nodes/{node_id}/thumbnail")
        def thumbnail(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            chemin = appel(lambda: self.client.thumbnail(db, self._member(org_id, m), node_id))
            return FileResponse(chemin, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})

        @self.app.get(base + "/nodes/{node_id}/access")
        def get_access(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.get_access(db, self._member(org_id, m), node_id))

        @self.app.put(base + "/nodes/{node_id}/access")
        def set_access(org_id: int, node_id: int, data: AccessUpdate, db: Session = db_dep, m: Member = member):
            return appel(
                lambda: self.client.set_access(
                    db, self._member(org_id, m), node_id, data.restricted, [e.model_dump() for e in data.entries]
                )
            )

        @self.app.get(base + "/principals")
        def principals(org_id: int, q: str = "", db: Session = db_dep, m: Member = member):
            return self.client.principals(db, self._member(org_id, m), q)
