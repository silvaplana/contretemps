"""Routes REST du module documents. Ne fait que traduire HTTP <-> appels à
`Documents` (service.py) ; les droits sont vérifiés par le service.

Toutes les routes sont sous `/documents/orgs/{org_id}/…`. La personne qui
appelle est fournie par l'appli hôte (`current_member`, une dépendance
FastAPI : voir documents_contretemps/adapter.py).
"""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import quote

from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from db import get_db

from . import assembly
from .ports import Member
from .service import DocError, Documents
from .storage import FileTooLarge


class Target(BaseModel):
    type: str
    id: str


class SendRequest(BaseModel):
    principals: list[Target] = Field(default_factory=list, max_length=1000)
    message: str | None = Field(default=None, max_length=2000)


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


class Recipient(BaseModel):
    """« Pour : » d'un élément du bac Échanges ; type et id vides = tout le monde."""

    type: str | None = None
    id: str | None = None


class NewApp(BaseModel):
    space: str
    parent_id: int | None = None
    family: str
    name: str | None = None


class AppSave(BaseModel):
    content: dict
    family: str | None = None
    # Version sur laquelle l'éditeur travaillait (détecte une modification
    # faite ailleurs entre-temps).
    base_version: int | None = None


class AppAnswer(BaseModel):
    values: dict


class TrialRequest(BaseModel):
    person_id: int | None = None


class Mark(BaseModel):
    present: bool


class Convene(BaseModel):
    kind: str
    starts_at: str = Field(max_length=40)
    folder_id: int | None = None
    new_folder: bool = False


class TemplateNew(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class TemplateUse(BaseModel):
    space: str
    parent_id: int | None = None


class TemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    hidden: bool | None = None


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

        @self.app.get(base + "/recent")
        def recent(org_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: self.client.recent(db, self._member(org_id, m)))

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

        @self.app.put(base + "/nodes/{node_id}/recipient")
        def set_recipient(org_id: int, node_id: int, data: Recipient, db: Session = db_dep, m: Member = member):
            principal = (data.type, data.id) if data.type and data.id else None
            return appel(lambda: self.client.set_recipient(db, self._member(org_id, m), node_id, principal))

        @self.app.delete(base + "/spaces/{space}/trash")
        def empty_trash(org_id: int, space: str, db: Session = db_dep, m: Member = member):
            return appel(lambda: {"erased": self.client.empty_trash(db, self._member(org_id, m), space)})

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

        @self.app.get(base + "/nodes/{node_id}/preview")
        def preview(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            chemin = appel(lambda: self.client.preview(db, self._member(org_id, m), node_id))
            return FileResponse(chemin, media_type="application/pdf", headers={"Cache-Control": "private, max-age=3600"})

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

        # Fichiers de l'appli (fichier-de-base.md)
        apps = self.client.apps

        @self.app.post(base + "/apps", status_code=201)
        def create_app(org_id: int, data: NewApp, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.create(db, self._member(org_id, m), data.space, data.parent_id, data.family, data.name))

        @self.app.get(base + "/nodes/{node_id}/app")
        def get_app(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.get(db, self._member(org_id, m), node_id))

        @self.app.put(base + "/nodes/{node_id}/app")
        def save_app(org_id: int, node_id: int, data: AppSave, db: Session = db_dep, m: Member = member):
            return appel(
                lambda: apps.save(db, self._member(org_id, m), node_id, data.content, data.family, data.base_version)
            )

        @self.app.post(base + "/nodes/{node_id}/app/try", status_code=201)
        def try_app(org_id: int, node_id: int, data: AppAnswer, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.try_answer(db, self._member(org_id, m), node_id, data.values))

        @self.app.get(base + "/nodes/{node_id}/app/responses")
        def app_responses(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.responses(db, self._member(org_id, m), node_id))

        @self.app.delete(base + "/nodes/{node_id}/app/responses/tests")
        def clear_tests(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.clear_tests(db, self._member(org_id, m), node_id))

        # Page en ligne (documents.md §5.5)
        @self.app.post(base + "/nodes/{node_id}/app/publication")
        def publish(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.publish(db, self._member(org_id, m), node_id))

        @self.app.delete(base + "/nodes/{node_id}/app/publication")
        def unpublish(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.unpublish(db, self._member(org_id, m), node_id))

        # Routes publiques (sans compte) : la page en ligne et ses réponses.
        # L'appli les déclare publiques (comptes/rbac.py).
        @self.app.get("/documents/public/orgs/{org_id}/pages/{slug}")
        def public_page(org_id: int, slug: str, db: Session = db_dep):
            return appel(lambda: apps.public_page(db, org_id, slug))

        @self.app.post("/documents/public/orgs/{org_id}/pages/{slug}/answers", status_code=201)
        def public_answer(org_id: int, slug: str, data: AppAnswer, db: Session = db_dep):
            return appel(lambda: apps.public_answer(db, org_id, slug, data.values))

        # Diffuser à des personnes choisies (fichier-de-base.md §2.3)
        sends = self.client.sends

        @self.app.post(base + "/nodes/{node_id}/app/sends/preview")
        def send_preview(org_id: int, node_id: int, data: SendRequest, db: Session = db_dep, m: Member = member):
            cibles = [p.model_dump() for p in data.principals]
            return appel(lambda: sends.preview(db, self._member(org_id, m), node_id, cibles))

        @self.app.post(base + "/nodes/{node_id}/app/sends", status_code=201)
        def send(
            org_id: int, node_id: int, data: SendRequest, taches: BackgroundTasks, db: Session = db_dep, m: Member = member
        ):
            cibles = [p.model_dump() for p in data.principals]
            resume, jobs = appel(lambda: sends.send(db, self._member(org_id, m), node_id, cibles, data.message))
            taches.add_task(sends.deliver, db.get_bind(), jobs)
            return resume

        @self.app.post(base + "/nodes/{node_id}/app/sends/trial", status_code=201)
        def send_trial(
            org_id: int, node_id: int, taches: BackgroundTasks, data: TrialRequest | None = None,
            db: Session = db_dep, m: Member = member,
        ):
            qui = data.person_id if data else None
            resume, jobs = appel(lambda: sends.trial(db, self._member(org_id, m), node_id, qui))
            taches.add_task(sends.deliver, db.get_bind(), jobs)
            return resume

        @self.app.get(base + "/nodes/{node_id}/app/sends")
        def send_list(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: sends.list(db, self._member(org_id, m), node_id))

        # Le lien personnel reçu par email (public, sans compte).
        @self.app.get("/documents/public/links/{token}")
        def link_page(token: str, db: Session = db_dep):
            return appel(lambda: sends.link_page(db, token))

        @self.app.post("/documents/public/links/{token}/answers", status_code=201)
        def link_answer(token: str, data: AppAnswer, db: Session = db_dep):
            return appel(lambda: sends.link_answer(db, token, data.values))

        # Assemblée générale : convocation et procurations (procurations.md)
        @self.app.post(base + "/assemblies", status_code=201)
        def convene(org_id: int, data: Convene, db: Session = db_dep, m: Member = member):
            return appel(lambda: assembly.convene(
                self.client, db, self._member(org_id, m), data.kind, data.starts_at, data.folder_id, data.new_folder,
            ))

        @self.app.get(base + "/nodes/{node_id}/app/assembly")
        def assembly_overview(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: assembly.overview(self.client, db, self._member(org_id, m), node_id))

        @self.app.get(base + "/nodes/{node_id}/app/assembly/{what}")
        def assembly_export(org_id: int, node_id: int, what: str, db: Session = db_dep, m: Member = member):
            if what not in ("summary.pdf", "summary.xlsx", "convocation.pdf"):
                raise HTTPException(status_code=404, detail="Introuvable")
            contenu, mime, nom = appel(lambda: assembly.export(self.client, db, self._member(org_id, m), node_id, what))
            return Response(contenu, media_type=mime, headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(nom)}"})

        # Feuille d'émargement (procurations.md §4, étape 2)
        @self.app.get(base + "/nodes/{node_id}/app/attendance")
        def attendance(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: assembly.attendance(self.client, db, self._member(org_id, m), node_id))

        @self.app.put(base + "/nodes/{node_id}/app/attendance/{person_id}")
        def mark(org_id: int, node_id: int, person_id: int, data: Mark, db: Session = db_dep, m: Member = member):
            return appel(lambda: assembly.mark(self.client, db, self._member(org_id, m), node_id, person_id, data.present))

        @self.app.post(base + "/nodes/{node_id}/app/assembly/remind", status_code=201)
        def remind(org_id: int, node_id: int, taches: BackgroundTasks, db: Session = db_dep, m: Member = member):
            resume, jobs = appel(lambda: assembly.remind(self.client, db, self._member(org_id, m), node_id))
            taches.add_task(assembly.send_reminders, self.client.mailer, jobs)
            return resume

        @self.app.post(base + "/nodes/{node_id}/app/attendance/pdf", status_code=201)
        def store_sheet(org_id: int, node_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: assembly.store_sheet(self.client, db, self._member(org_id, m), node_id))

        # Modèles de l'école (fichier-de-base.md §5)
        @self.app.post(base + "/nodes/{node_id}/app/template", status_code=201)
        def make_template(org_id: int, node_id: int, data: TemplateNew, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.make_template(db, self._member(org_id, m), node_id, data.name))

        @self.app.get(base + "/app-templates")
        def templates(org_id: int, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.templates(db, self._member(org_id, m)))

        @self.app.post(base + "/app-templates/{template_id}/use", status_code=201)
        def use_template(org_id: int, template_id: int, data: TemplateUse, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.use_template(db, self._member(org_id, m), template_id, data.space, data.parent_id))

        @self.app.patch(base + "/app-templates/{template_id}")
        def update_template(org_id: int, template_id: int, data: TemplateUpdate, db: Session = db_dep, m: Member = member):
            return appel(lambda: apps.update_template(db, self._member(org_id, m), template_id, data.name, data.hidden))

        @self.app.delete(base + "/app-templates/{template_id}", status_code=204)
        def delete_template(org_id: int, template_id: int, db: Session = db_dep, m: Member = member):
            appel(lambda: apps.delete_template(db, self._member(org_id, m), template_id))

        @self.app.get(base + "/principals")
        def principals(org_id: int, q: str = "", db: Session = db_dep, m: Member = member):
            return self.client.principals(db, self._member(org_id, m), q)
