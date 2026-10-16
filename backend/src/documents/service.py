"""Logique du module documents : arborescence, droits, versions, corbeille
(spec §4 et §6). Aucune dépendance FastAPI : les routes sont dans
receiver.py.

Chaque opération reçoit la personne qui appelle (`ports.Member`) et
vérifie elle-même ses droits (access.py) : aucune route ne peut l'oublier.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from . import access
from .models import (
    FAMILIES,
    KIND_APP,
    KIND_FILE,
    KIND_FOLDER,
    LEVEL_EDIT,
    LEVEL_MANAGE,
    LEVEL_VIEW,
    SPACES,
    STATUSES,
    SYSTEM_PERIOD,
    SYSTEM_PERMANENT,
    DocAcl,
    DocActivity,
    DocNode,
    DocVersion,
    StoredFile,
    utcnow,
)
from .ports import DEFAULT_PRIVATE_EDITORS, Directory, Member, Periods, Principal
from .preview import can_preview, convert_to_pdf
from .storage import LocalStorage, guess_mime, make_thumbnail

TRASH_DAYS = 30
PERMANENT_NAME = "Permanent"


class DocError(Exception):
    """Refus lisible par l'utilisateur ; `status` est le code HTTP."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


def not_found() -> DocError:
    return DocError(404, "Élément introuvable")


def normalize_search(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode("ascii")
    return " ".join(sans_accents.lower().split())


def clean_name(nom: str) -> str:
    nom = " ".join((nom or "").replace("/", "-").replace("\\", "-").split())
    if not nom or nom in (".", ".."):
        raise DocError(422, "Donnez un nom")
    if len(nom) > 200:
        raise DocError(422, "Nom trop long (200 caractères au plus)")
    return nom


def _variant(nom: str, n: int) -> str:
    """« Photo.jpg » -> « Photo (2).jpg »."""
    base, point, extension = nom.rpartition(".")
    if point and base:
        return f"{base} ({n}).{extension}"
    return f"{nom} ({n})"


@dataclass
class Location:
    """Où l'on est : un espace, et un dossier (None = racine de l'espace)."""

    space: str
    owner_person_id: int | None
    path: list[DocNode]

    @property
    def folder(self) -> DocNode | None:
        return self.path[-1] if self.path else None


class Documents:
    def __init__(
        self,
        storage: LocalStorage,
        directory: Directory,
        periods: Periods,
        period_label: str = "Saison",
        private_editors: Sequence[str] = DEFAULT_PRIVATE_EDITORS,
    ) -> None:
        self.storage = storage
        self.directory = directory
        self.periods = periods
        self.period_label = period_label
        self.private_editors = tuple(private_editors)
        from .app_files import AppFiles

        self.apps = AppFiles(self)

    # ------------------------------------------------------------------
    # Espaces et droits
    # ------------------------------------------------------------------

    def spaces(self, member: Member) -> list[dict]:
        espaces = [
            {"key": "public", "label": "Public"},
            {"key": "private", "label": "Privé"},
        ]
        if member.has_personal_space:
            espaces.append({"key": "personal", "label": "Personnel"})
        return espaces

    def _check_space(self, member: Member, space: str) -> None:
        if space not in SPACES or (space == "personal" and not member.has_personal_space):
            raise DocError(404, "Espace inconnu")

    def _closed_periods(self, db: Session, org_id: int) -> set[int]:
        return {p.id for p in self.periods.list(db, org_id) if not p.is_current}

    def _acl(self, db: Session, node_ids: set[int]) -> dict[int, list[DocAcl]]:
        par_noeud: dict[int, list[DocAcl]] = {}
        if node_ids:
            for ligne in db.scalars(select(DocAcl).where(DocAcl.node_id.in_(node_ids))):
                par_noeud.setdefault(ligne.node_id, []).append(ligne)
        return par_noeud

    def _level(self, member: Member, loc: Location, acl, closed) -> str | None:
        return access.effective_level(
            member, loc.space, loc.owner_person_id, loc.path, acl, self.private_editors, closed
        )

    def _node(self, db: Session, member: Member, node_id: int, deleted: bool = False) -> DocNode:
        node = db.get(DocNode, node_id)
        if node is None or node.org_id != member.org_id or (node.deleted_at is not None) != deleted:
            raise not_found()
        return node

    def _path(self, db: Session, node: DocNode) -> list[DocNode]:
        chemin = [node]
        vus = {node.id}
        while chemin[0].parent_id is not None:
            parent = db.get(DocNode, chemin[0].parent_id)
            if parent is None or parent.id in vus:
                break
            vus.add(parent.id)
            chemin.insert(0, parent)
        return chemin

    def _locate(self, db: Session, member: Member, node: DocNode | None, space: str | None = None) -> Location:
        if node is None:
            self._check_space(member, space)
            owner = member.person_id if space == "personal" else None
            return Location(space, owner, [])
        return Location(node.space, node.owner_person_id, self._path(db, node))

    def _require(self, db: Session, member: Member, loc: Location, needed: str) -> str:
        level = self._level(member, loc, self._acl(db, {n.id for n in loc.path}), self._closed_periods(db, member.org_id))
        if level is None:
            raise not_found()
        if not access.at_least(level, needed):
            if access.closed_period(loc.path, self._closed_periods(db, member.org_id)):
                raise DocError(403, "Cette saison est terminée : son dossier est en lecture seule.")
            raise DocError(403, "Vous n'avez pas le droit de modifier ici.")
        return level

    @staticmethod
    def _official_lock(path: Sequence[DocNode]) -> DocNode | None:
        """Le premier élément Officiel du chemin (lui-même compris), qui fige
        tout ce qu'il contient."""
        for node in path:
            if node.status == "official":
                return node
        return None

    def _require_unfrozen(self, path: Sequence[DocNode]) -> None:
        verrou = self._official_lock(path)
        if verrou is not None:
            if verrou is path[-1]:
                raise DocError(409, "Document officiel : il ne se modifie plus.")
            raise DocError(409, f"Le dossier « {verrou.name} » est officiel : son contenu ne se modifie plus.")

    # ------------------------------------------------------------------
    # Dossiers système (§4.7) : Permanent et un dossier par saison, dans Privé
    # ------------------------------------------------------------------

    def ensure_system_folders(self, db: Session, org_id: int) -> None:
        racine = select(DocNode).where(
            DocNode.org_id == org_id, DocNode.space == "private", DocNode.parent_id.is_(None)
        )
        existants = list(db.scalars(racine.where(DocNode.system_kind.is_not(None))))
        change = False
        if not any(n.system_kind == SYSTEM_PERMANENT for n in existants):
            db.add(self._new_node(org_id, "private", None, KIND_FOLDER, PERMANENT_NAME, None, system_kind=SYSTEM_PERMANENT))
            change = True
        par_periode = {n.period_id: n for n in existants if n.system_kind == SYSTEM_PERIOD}
        for periode in self.periods.list(db, org_id):
            nom = f"{self.period_label} {periode.name}"
            dossier = par_periode.get(periode.id)
            if dossier is None:
                db.add(
                    self._new_node(
                        org_id, "private", None, KIND_FOLDER, nom, None,
                        system_kind=SYSTEM_PERIOD, period_id=periode.id,
                    )
                )
                change = True
            elif dossier.name != nom:
                dossier.name, dossier.name_search = nom, normalize_search(nom)
                change = True
        if change:
            db.commit()

    @staticmethod
    def _new_node(org_id, space, parent_id, kind, name, person_id, **autres) -> DocNode:
        return DocNode(
            org_id=org_id, space=space, parent_id=parent_id, kind=kind, name=name,
            name_search=normalize_search(name), created_by=person_id, updated_by=person_id,
            **autres,
        )

    # ------------------------------------------------------------------
    # Lecture
    # ------------------------------------------------------------------

    def _children(self, db: Session, member: Member, loc: Location) -> list[DocNode]:
        requete = select(DocNode).where(
            DocNode.org_id == member.org_id,
            DocNode.space == loc.space,
            DocNode.deleted_at.is_(None),
        )
        if loc.folder is None:
            requete = requete.where(DocNode.parent_id.is_(None))
        else:
            requete = requete.where(DocNode.parent_id == loc.folder.id)
        if loc.space == "personal":
            requete = requete.where(DocNode.owner_person_id == loc.owner_person_id)
        return list(db.scalars(requete))

    def browse(self, db: Session, member: Member, space: str, folder_id: int | None) -> dict:
        self._check_space(member, space)
        if space == "private" and folder_id is None:
            self.ensure_system_folders(db, member.org_id)
        dossier = self._node(db, member, folder_id) if folder_id is not None else None
        if dossier is not None and (dossier.space != space or dossier.kind != KIND_FOLDER):
            raise not_found()
        loc = self._locate(db, member, dossier, space)
        enfants = self._children(db, member, loc)
        acl = self._acl(db, {n.id for n in loc.path} | {n.id for n in enfants})
        fermees = self._closed_periods(db, member.org_id)
        niveau = self._level(member, loc, acl, fermees)
        if niveau is None and loc.path:
            raise not_found()
        if niveau is None and space == "private":
            return self._shared_with_me(db, member, fermees)

        comptes = self._child_counts(db, [n.id for n in enfants if n.kind == KIND_FOLDER])
        noms = self.directory.person_names(db, member.org_id, {n.updated_by for n in enfants if n.updated_by})
        periodes = {p.id: p for p in self.periods.list(db, member.org_id)}
        elements = []
        for enfant in enfants:
            chemin = loc.path + [enfant]
            niveau_enfant = access.effective_level(
                member, loc.space, loc.owner_person_id, chemin, acl, self.private_editors, fermees
            )
            if niveau_enfant is None:
                continue
            elements.append(
                self._summary(enfant, niveau_enfant, chemin, fermees, comptes, noms, periodes)
            )
        elements.sort(key=self._sort_key(periodes))
        return {
            "space": space,
            "folder": self._summary(dossier, niveau, loc.path, fermees, {}, {}, periodes) if dossier else None,
            "breadcrumb": self._breadcrumb(member, loc, acl, fermees),
            "level": niveau,
            "can_add": access.at_least(niveau, LEVEL_EDIT) and self._official_lock(loc.path) is None,
            "items": elements,
        }

    def _breadcrumb(self, member: Member, loc: Location, acl, fermees) -> list[dict]:
        """Le fil d'Ariane commence au premier dossier visible : un élève ne
        voit pas le dossier de saison au-dessus d'un dossier qu'on lui a
        partagé."""
        debut = 0
        for i in range(len(loc.path)):
            if access.effective_level(
                member, loc.space, loc.owner_person_id, loc.path[: i + 1], acl, self.private_editors, fermees
            ) is not None:
                debut = i
                break
        return [{"id": n.id, "name": n.name} for n in loc.path[debut:]]

    def _shared_with_me(self, db: Session, member: Member, fermees: set[int]) -> dict:
        """Racine de Privé pour qui n'y a aucun droit par défaut (un élève) :
        les éléments les plus hauts qui lui sont partagés, comme « Partagés
        avec moi » de Google Drive, puisqu'il ne peut pas descendre jusqu'à
        eux depuis la racine."""
        cles = [("member", str(member.person_id))] + [("group", g) for g in member.groups]
        lignes = db.scalars(
            select(DocAcl.node_id).where(
                or_(*[(DocAcl.principal_type == t) & (DocAcl.principal_id == i) for t, i in cles])
            )
        )
        candidats = [
            n for n in (db.get(DocNode, i) for i in set(lignes))
            if n is not None and n.org_id == member.org_id and n.space == "private" and n.deleted_at is None
        ]
        periodes = {p.id: p for p in self.periods.list(db, member.org_id)}
        elements, vus = [], set()
        for node in candidats:
            chemin = self._path(db, node)
            if any(n.deleted_at is not None for n in chemin):
                continue
            acl = self._acl(db, {n.id for n in chemin})
            # Le plus haut élément visible du chemin.
            for i in range(len(chemin)):
                niveau = access.effective_level(member, "private", None, chemin[: i + 1], acl, self.private_editors, fermees)
                if niveau is not None:
                    haut = chemin[i]
                    if haut.id not in vus:
                        vus.add(haut.id)
                        comptes = self._child_counts(db, [haut.id]) if haut.kind == KIND_FOLDER else {}
                        elements.append(self._summary(haut, niveau, chemin[: i + 1], fermees, comptes, {}, periodes))
                    break
        elements.sort(key=self._sort_key(periodes))
        return {"space": "private", "folder": None, "breadcrumb": [], "level": None, "can_add": False,
                "shared_with_me": True, "items": elements}

    @staticmethod
    def _sort_key(periodes):
        def cle(e):
            if e["system_kind"] == SYSTEM_PERMANENT:
                return (0, 0, "")
            if e["system_kind"] == SYSTEM_PERIOD:
                # Saison la plus récente d'abord.
                return (1, -(e["period_id"] or 0), "")
            return (2 if e["kind"] == KIND_FOLDER else 3, 0 if e["pinned"] else 1, e["name"].lower())

        return cle

    def _child_counts(self, db: Session, folder_ids: list[int]) -> dict[int, int]:
        if not folder_ids:
            return {}
        lignes = db.execute(
            select(DocNode.parent_id, func.count())
            .where(DocNode.parent_id.in_(folder_ids), DocNode.deleted_at.is_(None))
            .group_by(DocNode.parent_id)
        ).all()
        return dict(lignes)

    def _summary(self, node, level, path, fermees, comptes, noms, periodes) -> dict:
        periode = periodes.get(node.period_id) if node.period_id else None
        ferme = access.closed_period(path, fermees)
        return {
            "id": node.id,
            "kind": node.kind,
            "name": node.name,
            "space": node.space,
            "status": node.status,
            "family": node.family,
            "system_kind": node.system_kind,
            "period_id": node.period_id,
            "period_current": bool(periode and periode.is_current) if node.system_kind == SYSTEM_PERIOD else None,
            "restricted": node.restricted,
            "pinned": node.pinned,
            "size": node.size,
            "mime": node.mime,
            "updated_at": node.updated_at.isoformat() if node.updated_at else None,
            "updated_by": noms.get(node.updated_by),
            "child_count": comptes.get(node.id, 0) if node.kind == KIND_FOLDER else None,
            "level": level,
            "closed_period": ferme,
            "frozen": ferme or self._official_lock(path) is not None,
            "has_thumbnail": bool(node.kind == KIND_FILE and (node.mime or "").startswith("image/")),
        }

    def detail(self, db: Session, member: Member, node_id: int) -> dict:
        node = self._node(db, member, node_id)
        loc = self._locate(db, member, node)
        acl = self._acl(db, {n.id for n in loc.path})
        fermees = self._closed_periods(db, member.org_id)
        niveau = self._level(member, loc, acl, fermees)
        if niveau is None:
            raise not_found()
        versions = list(
            db.scalars(select(DocVersion).where(DocVersion.node_id == node.id).order_by(DocVersion.number.desc()))
        )
        activite = list(
            db.scalars(
                select(DocActivity)
                .where(DocActivity.node_id == node.id)
                .order_by(DocActivity.created_at.desc(), DocActivity.id.desc())
                .limit(60)
            )
        )
        personnes = {node.created_by, node.updated_by} | {v.created_by for v in versions} | {a.person_id for a in activite}
        noms = self.directory.person_names(db, member.org_id, {p for p in personnes if p})
        periodes = {p.id: p for p in self.periods.list(db, member.org_id)}
        comptes = self._child_counts(db, [node.id]) if node.kind == KIND_FOLDER else {}
        fichiers = {}
        if versions:
            fichiers = {
                f.id: f
                for f in db.scalars(select(StoredFile).where(StoredFile.id.in_({v.stored_file_id for v in versions})))
            }
        resume = self._summary(node, niveau, loc.path, fermees, comptes, noms, periodes)
        resume.update(
            {
                "path": [{"id": n.id, "name": n.name} for n in loc.path[:-1]],
                "created_at": node.created_at.isoformat() if node.created_at else None,
                "created_by": noms.get(node.created_by),
                "can_edit": access.at_least(niveau, LEVEL_EDIT) and self._official_lock(loc.path) is None,
                "can_manage": access.at_least(niveau, LEVEL_MANAGE),
                "can_rename": self._can_restructure(db, member, node, loc),
                "versions": [
                    {
                        "id": v.id,
                        "number": v.number,
                        "filename": v.filename,
                        "size": fichiers[v.stored_file_id].size if v.stored_file_id in fichiers else None,
                        "created_at": v.created_at.isoformat(),
                        "created_by": noms.get(v.created_by),
                        "current": v.id == node.current_version_id,
                    }
                    for v in versions
                ],
                "history": [
                    {
                        "action": a.action,
                        "detail": a.detail or {},
                        "at": a.created_at.isoformat(),
                        "by": noms.get(a.person_id),
                    }
                    for a in activite
                ],
            }
        )
        return resume

    def _can_restructure(self, db, member, node, loc) -> bool:
        """Renommer, déplacer, supprimer : Écriture sur le dossier parent
        (logique Unix, §4.4), pas un dossier système, rien d'officiel."""
        if node.system_kind is not None or self._official_lock(loc.path) is not None:
            return False
        parent_loc = Location(loc.space, loc.owner_person_id, loc.path[:-1])
        niveau = self._level(member, parent_loc, self._acl(db, {n.id for n in parent_loc.path}), self._closed_periods(db, member.org_id))
        return access.at_least(niveau, LEVEL_EDIT)

    def search(self, db: Session, member: Member, space: str, query: str) -> list[dict]:
        self._check_space(member, space)
        texte = normalize_search(query)
        if len(texte) < 2:
            return []
        requete = select(DocNode).where(
            DocNode.org_id == member.org_id,
            DocNode.space == space,
            DocNode.deleted_at.is_(None),
            DocNode.name_search.like(f"%{texte}%"),
        )
        if space == "personal":
            requete = requete.where(DocNode.owner_person_id == member.person_id)
        trouves = list(db.scalars(requete.limit(200)))
        fermees = self._closed_periods(db, member.org_id)
        periodes = {p.id: p for p in self.periods.list(db, member.org_id)}
        resultats = []
        for node in trouves:
            loc = self._locate(db, member, node)
            if any(n.deleted_at is not None for n in loc.path):
                continue
            niveau = self._level(member, loc, self._acl(db, {n.id for n in loc.path}), fermees)
            if niveau is None:
                continue
            resume = self._summary(node, niveau, loc.path, fermees, {}, {}, periodes)
            resume["path"] = [{"id": n.id, "name": n.name} for n in loc.path[:-1]]
            resultats.append(resume)
            if len(resultats) >= 50:
                break
        return resultats

    def recent(self, db: Session, member: Member, limit: int = 30) -> list[dict]:
        """« Récents » (façon Google Drive, Seb 15 octobre) : les derniers
        fichiers modifiés, tous espaces confondus, parmi ceux que `member`
        peut voir — avec leur chemin, comme pour la recherche."""
        espaces = [e["key"] for e in self.spaces(member)]
        requete = (
            select(DocNode)
            .where(
                DocNode.org_id == member.org_id,
                DocNode.kind.in_((KIND_FILE, KIND_APP)),
                DocNode.deleted_at.is_(None),
                DocNode.space.in_(espaces),
                or_(DocNode.space != "personal", DocNode.owner_person_id == member.person_id),
            )
            .order_by(DocNode.updated_at.desc(), DocNode.id.desc())
        )
        fermees = self._closed_periods(db, member.org_id)
        periodes = {p.id: p for p in self.periods.list(db, member.org_id)}
        visibles = []
        for node in db.scalars(requete.limit(300)):
            loc = self._locate(db, member, node)
            if any(n.deleted_at is not None for n in loc.path):
                continue
            niveau = self._level(member, loc, self._acl(db, {n.id for n in loc.path}), fermees)
            if niveau is not None:
                visibles.append((node, niveau, loc))
            if len(visibles) >= limit:
                break
        # Qui a modifié : « … · Julia Dho », comme dans un dossier.
        noms = self.directory.person_names(db, member.org_id, {n.updated_by for n, _, _ in visibles if n.updated_by})
        resultats = []
        for node, niveau, loc in visibles:
            resume = self._summary(node, niveau, loc.path, fermees, {}, noms, periodes)
            resume["path"] = [{"id": n.id, "name": n.name} for n in loc.path[:-1]]
            resultats.append(resume)
        return resultats

    # ------------------------------------------------------------------
    # Création
    # ------------------------------------------------------------------

    def _target(self, db: Session, member: Member, space: str, parent_id: int | None) -> Location:
        self._check_space(member, space)
        parent = self._node(db, member, parent_id) if parent_id is not None else None
        if parent is not None and (parent.space != space or parent.kind != KIND_FOLDER):
            raise not_found()
        loc = self._locate(db, member, parent, space)
        self._require(db, member, loc, LEVEL_EDIT)
        if loc.path:
            self._require_unfrozen(loc.path)
        return loc

    def _free_name(self, db: Session, member: Member, loc: Location, nom: str, sauf: int | None = None) -> str | None:
        """None si `nom` est libre dans ce dossier, sinon une variante libre."""
        pris = {n.name.lower() for n in self._children(db, member, loc) if n.id != sauf}
        if nom.lower() not in pris:
            return None
        n = 2
        while _variant(nom, n).lower() in pris:
            n += 1
        return _variant(nom, n)

    def create_folder(self, db: Session, member: Member, space: str, parent_id: int | None, name: str) -> dict:
        loc = self._target(db, member, space, parent_id)
        nom = clean_name(name)
        nom = self._free_name(db, member, loc, nom) or nom
        node = self._new_node(member.org_id, loc.space, parent_id, KIND_FOLDER, nom, member.person_id)
        node.owner_person_id = loc.owner_person_id
        db.add(node)
        db.flush()
        self._log(db, member, node, "created")
        db.commit()
        return {"id": node.id, "name": node.name}

    def upload(
        self, db: Session, member: Member, space: str, parent_id: int | None, filename: str, source: BinaryIO
    ) -> dict:
        loc = self._target(db, member, space, parent_id)
        nom = clean_name(filename)
        stocke = self._store(db, member.org_id, nom, source)
        nom = self._free_name(db, member, loc, nom) or nom
        node = self._new_node(member.org_id, loc.space, parent_id, KIND_FILE, nom, member.person_id)
        node.owner_person_id = loc.owner_person_id
        db.add(node)
        db.flush()
        self._add_version(db, member, node, stocke, nom)
        self._log(db, member, node, "uploaded")
        db.commit()
        return {"id": node.id, "name": node.name}

    def _store(self, db: Session, org_id: int, filename: str, source: BinaryIO) -> StoredFile:
        sha, taille = self.storage.put(org_id, source)
        existant = db.scalar(select(StoredFile).where(StoredFile.org_id == org_id, StoredFile.sha256 == sha))
        if existant is not None:
            return existant
        stocke = StoredFile(org_id=org_id, sha256=sha, size=taille, mime=guess_mime(filename))
        db.add(stocke)
        db.flush()
        return stocke

    def _add_version(self, db, member, node, stocke: StoredFile, filename: str) -> DocVersion:
        numero = (db.scalar(select(func.max(DocVersion.number)).where(DocVersion.node_id == node.id)) or 0) + 1
        version = DocVersion(
            node_id=node.id, number=numero, stored_file_id=stocke.id, filename=filename, created_by=member.person_id
        )
        db.add(version)
        db.flush()
        node.current_version_id = version.id
        node.size = stocke.size
        node.mime = stocke.mime
        node.updated_by = member.person_id
        node.updated_at = utcnow()
        return version

    def new_version(self, db: Session, member: Member, node_id: int, filename: str, source: BinaryIO) -> dict:
        node = self._node(db, member, node_id)
        if node.kind != KIND_FILE:
            raise DocError(422, "Seul un fichier a des versions")
        loc = self._locate(db, member, node)
        niveau = self._require(db, member, loc, LEVEL_EDIT)
        self._require_unfrozen(loc.path)
        stocke = self._store(db, member.org_id, clean_name(filename), source)
        self._add_version(db, member, node, stocke, clean_name(filename))
        # Validé : modifié par quelqu'un qui n'a que l'Écriture, il repasse
        # en Brouillon (§4.4, le statut passe avant les droits).
        if node.status == "validated" and not access.at_least(niveau, LEVEL_MANAGE):
            node.status = "draft"
        self._log(db, member, node, "new_version", {"filename": clean_name(filename)})
        db.commit()
        return {"id": node.id}

    # ------------------------------------------------------------------
    # Modification
    # ------------------------------------------------------------------

    def update(
        self,
        db: Session,
        member: Member,
        node_id: int,
        name: str | None = None,
        parent_id: int | None = None,
        move: bool = False,
        space: str | None = None,
        status: str | None = None,
        change_status: bool = False,
        pinned: bool | None = None,
    ) -> dict:
        node = self._node(db, member, node_id)
        loc = self._locate(db, member, node)
        if name is not None and clean_name(name) != node.name:
            self._rename(db, member, node, loc, clean_name(name))
        if move:
            self._move(db, member, node, loc, space or node.space, parent_id)
            loc = self._locate(db, member, node)
        if change_status:
            self._set_status(db, member, node, loc, status)
        if pinned is not None and pinned != node.pinned:
            self._require(db, member, Location(loc.space, loc.owner_person_id, loc.path[:-1]), LEVEL_EDIT)
            node.pinned = pinned
        db.commit()
        return {"id": node.id, "name": node.name}

    def _check_restructure(self, db, member, node, loc) -> None:
        if node.system_kind is not None:
            raise DocError(409, "Ce dossier fait partie de l'organisation de l'appli : il ne se renomme, ne se déplace ni ne se supprime.")
        self._require_unfrozen(loc.path)
        parent = Location(loc.space, loc.owner_person_id, loc.path[:-1])
        self._require(db, member, parent, LEVEL_EDIT)

    def _rename(self, db, member, node, loc, nom) -> None:
        self._check_restructure(db, member, node, loc)
        if self._free_name(db, member, Location(loc.space, loc.owner_person_id, loc.path[:-1]), nom, sauf=node.id):
            raise DocError(409, "Un élément de ce dossier porte déjà ce nom.")
        ancien = node.name
        node.name, node.name_search = nom, normalize_search(nom)
        node.updated_by, node.updated_at = member.person_id, utcnow()
        self._log(db, member, node, "renamed", {"from": ancien, "to": nom})

    def _move(self, db, member, node, loc, space, parent_id) -> None:
        self._check_restructure(db, member, node, loc)
        cible = self._target(db, member, space, parent_id)
        if any(n.id == node.id for n in cible.path):
            raise DocError(409, "Impossible de ranger un dossier dans lui-même.")
        if (cible.folder.id if cible.folder else None) == node.parent_id and cible.space == node.space:
            return
        if self._free_name(db, member, cible, node.name):
            raise DocError(409, "Un élément du dossier de destination porte déjà ce nom.")
        avant = " › ".join(n.name for n in loc.path[:-1]) or self._space_label(loc.space)
        node.parent_id = cible.folder.id if cible.folder else None
        if cible.space != node.space or cible.owner_person_id != node.owner_person_id:
            for element in self._subtree(db, node):
                element.space, element.owner_person_id = cible.space, cible.owner_person_id
        node.updated_by, node.updated_at = member.person_id, utcnow()
        apres = " › ".join(n.name for n in cible.path) or self._space_label(cible.space)
        self._log(db, member, node, "moved", {"from": avant, "to": apres})

    def copy(self, db: Session, member: Member, node_id: int, space: str, parent_id: int | None) -> dict:
        """Copier / Coller : le dossier ou le fichier et tout son contenu.
        Les contenus ne sont pas dupliqués sur le disque (même empreinte) ;
        la copie prend les droits de son nouveau dossier, et un élément
        Validé ou Officiel redevient Brouillon (ce n'est plus le même)."""
        source = self._node(db, member, node_id)
        self._require(db, member, self._locate(db, member, source), LEVEL_VIEW)
        cible = self._target(db, member, space, parent_id)
        if any(n.id == source.id for n in cible.path):
            raise DocError(409, "Impossible de copier un dossier dans lui-même.")
        if source.system_kind is not None:
            raise DocError(409, "Ce dossier fait partie de l'organisation de l'appli : copiez plutôt son contenu.")
        nom = self._free_name(db, member, cible, source.name) or source.name
        racine = self._copy_node(db, member, source, cible, cible.folder.id if cible.folder else None, nom)
        self._log(db, member, racine, "copied", {"from": source.name})
        db.commit()
        return {"id": racine.id, "name": racine.name}

    def copy_period(
        self,
        db: Session,
        member: Member,
        from_period_id: int,
        to_period_id: int,
        remap_group: Callable[[str], str | None] | None = None,
    ) -> int:
        """Nouvelle période : recopie le contenu du dossier de la période
        `from_period_id` dans celui de `to_period_id` (§4.7, « copier la
        saison précédente »). Contrairement à Copier / Coller, l'organisation
        des droits suit : « Accès restreint » et partages sont repris, chaque
        clé de groupe passant par `remap_group` (l'appli hôte y traduit les
        groupes propres à une période, ou renvoie None pour ne pas reprendre
        le partage). Renvoie le nombre d'éléments recopiés à la racine."""
        self.ensure_system_folders(db, member.org_id)
        dossiers = {
            n.period_id: n
            for n in db.scalars(
                select(DocNode).where(
                    DocNode.org_id == member.org_id,
                    DocNode.system_kind == SYSTEM_PERIOD,
                    DocNode.period_id.in_([from_period_id, to_period_id]),
                )
            )
        }
        source, cible = dossiers.get(from_period_id), dossiers.get(to_period_id)
        if source is None or cible is None or source.id == cible.id:
            return 0
        loc = Location("private", None, [cible])
        droits = remap_group or (lambda cle: cle)
        enfants = list(
            db.scalars(
                select(DocNode)
                .where(DocNode.parent_id == source.id, DocNode.deleted_at.is_(None))
                .order_by(DocNode.id)
            )
        )
        for enfant in enfants:
            self._copy_node(db, member, enfant, loc, cible.id, enfant.name, rights=droits)
        if enfants:
            self._log(db, member, cible, "copied", {"from": source.name})
        db.commit()
        return len(enfants)

    def _copy_node(self, db, member, source: DocNode, cible: Location, parent_id, nom, rights=None) -> DocNode:
        """`rights` : None, la copie prend les droits de son nouveau dossier ;
        sinon elle garde « Accès restreint » et les partages de l'original,
        clés de groupe traduites par `rights` (copie de période)."""
        copie = self._new_node(
            member.org_id, cible.space, parent_id, source.kind, nom, member.person_id,
            owner_person_id=cible.owner_person_id, family=source.family,
            status="draft" if source.status in ("validated", "official") else source.status,
            restricted=source.restricted if rights is not None else False,
        )
        db.add(copie)
        db.flush()
        if rights is not None:
            for ligne in db.scalars(select(DocAcl).where(DocAcl.node_id == source.id)):
                principal = ligne.principal_id if ligne.principal_type != "group" else rights(ligne.principal_id)
                if principal is not None:
                    db.add(DocAcl(node_id=copie.id, principal_type=ligne.principal_type, principal_id=principal, level=ligne.level))
        if source.kind == KIND_FILE and source.current_version_id:
            version = db.get(DocVersion, source.current_version_id)
            self._add_version(db, member, copie, db.get(StoredFile, version.stored_file_id), version.filename)
        elif source.kind == KIND_APP:
            self.apps.copy_content(db, member, source, copie)
        else:
            enfants = db.scalars(
                select(DocNode).where(DocNode.parent_id == source.id, DocNode.deleted_at.is_(None))
            )
            for enfant in list(enfants):
                self._copy_node(db, member, enfant, cible, copie.id, enfant.name, rights=rights)
        return copie

    @staticmethod
    def _space_label(space: str) -> str:
        return {"public": "Public", "private": "Privé", "personal": "Personnel"}[space]

    def _subtree(self, db: Session, node: DocNode) -> list[DocNode]:
        tous, a_voir = [node], [node.id]
        while a_voir:
            enfants = list(db.scalars(select(DocNode).where(DocNode.parent_id.in_(a_voir))))
            tous += enfants
            a_voir = [e.id for e in enfants if e.kind == KIND_FOLDER]
        return tous

    def _set_status(self, db, member, node, loc, status) -> None:
        if status is not None and status not in STATUSES:
            raise DocError(422, "Statut inconnu")
        if status == node.status:
            return
        niveau = self._require(db, member, loc, LEVEL_EDIT)
        # Officiel : seule la Gestion y fait entrer ou en fait sortir (une
        # erreur reste réparable par un admin).
        if node.status == "official" or status in ("validated", "official"):
            if not access.at_least(niveau, LEVEL_MANAGE):
                raise DocError(403, "Seuls ceux qui gèrent ce document peuvent le valider ou le rendre officiel.")
        else:
            self._require_unfrozen(loc.path)
        avant = node.status
        node.status = status
        node.updated_by, node.updated_at = member.person_id, utcnow()
        self._log(db, member, node, "status", {"from": avant, "to": status})

    def set_family(self, db: Session, node: DocNode, family: str | None) -> None:
        """Famille calculée à partir du contenu (§7.1 bis) ; réservé aux
        types de fichiers de l'appli, à venir."""
        if family is not None and family not in FAMILIES:
            raise DocError(422, "Famille inconnue")
        node.family = family

    # ------------------------------------------------------------------
    # Corbeille
    # ------------------------------------------------------------------

    def delete(self, db: Session, member: Member, node_id: int) -> None:
        node = self._node(db, member, node_id)
        loc = self._locate(db, member, node)
        self._check_restructure(db, member, node, loc)
        node.deleted_at, node.deleted_by = utcnow(), member.person_id
        self._log(db, member, node, "deleted")
        db.commit()

    def restore(self, db: Session, member: Member, node_id: int) -> dict:
        node = self._node(db, member, node_id, deleted=True)
        if not self._may_see_in_trash(db, member, node):
            raise not_found()
        parent = db.get(DocNode, node.parent_id) if node.parent_id else None
        # Dossier d'origine supprimé lui aussi (ou perdu) : on restaure à la
        # racine de l'espace.
        if parent is not None and parent.deleted_at is not None:
            node.parent_id = None
        loc = self._locate(db, member, db.get(DocNode, node.parent_id) if node.parent_id else None, node.space)
        if node.space == "personal":
            loc.owner_person_id = node.owner_person_id
        nom = self._free_name(db, member, loc, node.name)
        if nom:
            node.name, node.name_search = nom, normalize_search(nom)
        node.deleted_at, node.deleted_by = None, None
        self._log(db, member, node, "restored")
        db.commit()
        return {"id": node.id, "parent_id": node.parent_id, "space": node.space}

    def _may_see_in_trash(self, db, member, node) -> bool:
        if node.space == "personal":
            return node.owner_person_id == member.person_id
        return member.is_admin or member.is_superuser or node.deleted_by == member.person_id

    def _trash_items(self, db: Session, member: Member, space: str) -> list[DocNode]:
        """Ce que `member` voit dans la corbeille de l'espace : seulement ce
        qui a été supprimé tel quel, pas le contenu d'un dossier supprimé
        (il revient, ou part, avec son dossier)."""
        requete = select(DocNode).where(
            DocNode.org_id == member.org_id, DocNode.space == space, DocNode.deleted_at.is_not(None)
        ).order_by(DocNode.deleted_at.desc())
        elements = [n for n in db.scalars(requete) if self._may_see_in_trash(db, member, n)]
        ids = {n.id for n in elements}
        return [n for n in elements if n.parent_id not in ids]

    def empty_trash(self, db: Session, member: Member, space: str) -> int:
        """Vider la corbeille : efface pour de bon, tout de suite, ce que
        `member` y voit (les admins : tout ; les autres : ce qu'ils ont
        supprimé eux-mêmes). Renvoie le nombre d'éléments effacés."""
        self._check_space(member, space)
        elements = self._trash_items(db, member, space)
        if elements:
            self._erase(db, member.org_id, elements)
        return len(elements)

    def trash(self, db: Session, member: Member, space: str) -> list[dict]:
        self._check_space(member, space)
        self.purge(db, member.org_id)
        elements = self._trash_items(db, member, space)
        noms = self.directory.person_names(db, member.org_id, {n.deleted_by for n in elements if n.deleted_by})
        return [
            {
                "id": n.id,
                "kind": n.kind,
                "name": n.name,
                "mime": n.mime,
                "size": n.size,
                "deleted_at": n.deleted_at.isoformat(),
                "deleted_by": noms.get(n.deleted_by),
                "purge_at": (n.deleted_at + timedelta(days=TRASH_DAYS)).isoformat(),
            }
            for n in elements
        ]

    def purge(self, db: Session, org_id: int) -> int:
        """Efface pour de bon ce qui est dans la corbeille depuis plus de
        30 jours, et les contenus qui ne servent plus à rien."""
        limite = utcnow() - timedelta(days=TRASH_DAYS)
        vieux = list(
            db.scalars(select(DocNode).where(DocNode.org_id == org_id, DocNode.deleted_at < limite))
        )
        if not vieux:
            return 0
        return self._erase(db, org_id, vieux)

    def _erase(self, db: Session, org_id: int, nodes: list[DocNode]) -> int:
        """Efface pour de bon ces éléments et tout leur contenu, et les
        fichiers stockés qui ne servent plus à personne."""
        a_effacer: list[DocNode] = []
        for node in nodes:
            a_effacer += self._subtree(db, node)
        a_effacer = list({n.id: n for n in a_effacer}.values())
        ids = {n.id for n in a_effacer}
        fichiers = set(db.scalars(select(DocVersion.stored_file_id).where(DocVersion.node_id.in_(ids))))
        self.apps.erase(db, ids)
        for modele in (DocVersion, DocAcl, DocActivity):
            db.query(modele).filter(modele.node_id.in_(ids)).delete(synchronize_session=False)
        # Enfants avant parents (clé étrangère parent_id).
        for node in sorted(a_effacer, key=lambda n: -len(self._path(db, n))):
            db.delete(node)
            db.flush()
        encore = set(db.scalars(select(DocVersion.stored_file_id).where(DocVersion.stored_file_id.in_(fichiers))))
        for stocke in db.scalars(select(StoredFile).where(StoredFile.id.in_(fichiers - encore))):
            self.storage.delete(org_id, stocke.sha256)
            db.delete(stocke)
        db.commit()
        return len(ids)

    # ------------------------------------------------------------------
    # Contenu
    # ------------------------------------------------------------------

    def content(self, db: Session, member: Member, node_id: int, version_id: int | None = None) -> tuple[Path, str, str]:
        """(chemin sur le disque, nom du fichier, type) — après contrôle de
        la Lecture."""
        node = self._node(db, member, node_id)
        if node.kind != KIND_FILE:
            raise not_found()
        self._require(db, member, self._locate(db, member, node), LEVEL_VIEW)
        version = db.get(DocVersion, version_id or node.current_version_id or 0)
        if version is None or version.node_id != node.id:
            raise not_found()
        stocke = db.get(StoredFile, version.stored_file_id)
        nom = node.name if version.id == node.current_version_id else version.filename
        return self.storage.path(node.org_id, stocke.sha256), nom, stocke.mime

    def thumbnail(self, db: Session, member: Member, node_id: int) -> Path:
        node = self._node(db, member, node_id)
        if node.kind != KIND_FILE or not (node.mime or "").startswith("image/"):
            raise not_found()
        self._require(db, member, self._locate(db, member, node), LEVEL_VIEW)
        version = db.get(DocVersion, node.current_version_id or 0)
        stocke = db.get(StoredFile, version.stored_file_id) if version else None
        if stocke is None:
            raise not_found()
        vignette = self.storage.thumbnail_path(node.org_id, stocke.sha256)
        if not vignette.exists() and not make_thumbnail(self.storage.path(node.org_id, stocke.sha256), vignette):
            raise not_found()
        return vignette

    def preview(self, db: Session, member: Member, node_id: int) -> Path:
        """PDF preview of a Word / Excel / PowerPoint file (preview.py),
        made once per content and kept."""
        node = self._node(db, member, node_id)
        if node.kind != KIND_FILE or not can_preview(node.name):
            raise DocError(415, "Pas d'aperçu pour ce type de fichier : téléchargez-le.")
        self._require(db, member, self._locate(db, member, node), LEVEL_VIEW)
        version = db.get(DocVersion, node.current_version_id or 0)
        stocke = db.get(StoredFile, version.stored_file_id) if version else None
        if stocke is None:
            raise not_found()
        apercu = self.storage.preview_path(node.org_id, stocke.sha256)
        if not apercu.exists() and not convert_to_pdf(self.storage.path(node.org_id, stocke.sha256), node.name, apercu):
            raise DocError(503, "Aperçu indisponible pour l'instant : téléchargez le fichier.")
        return apercu

    # ------------------------------------------------------------------
    # Accès (« Qui a accès ? », §4.4 bis)
    # ------------------------------------------------------------------

    def get_access(self, db: Session, member: Member, node_id: int) -> dict:
        node = self._node(db, member, node_id)
        loc = self._locate(db, member, node)
        acl = self._acl(db, {n.id for n in loc.path})
        niveau = self._level(member, loc, acl, self._closed_periods(db, member.org_id))
        if niveau is None:
            raise not_found()
        if node.space == "personal":
            return {
                "level": niveau, "restricted": False, "can_manage": False, "can_restrict": False,
                "personal": True, "inherited_from": None, "inherited": [], "direct": [],
            }
        herites: list[tuple[str, str, str, str]] = []  # (type, id, niveau, origine)
        arret = None
        for ancetre in reversed(loc.path[:-1]):
            for ligne in acl.get(ancetre.id, []):
                herites.append((ligne.principal_type, ligne.principal_id, ligne.level, ancetre.name))
            if ancetre.restricted:
                arret = ancetre
                break
        if arret is None and not node.restricted:
            origine = self._space_label(node.space)
            if node.space == "public":
                herites.append(("group", "everyone", LEVEL_VIEW, origine))
            else:
                for groupe in self.private_editors:
                    herites.append(("group", groupe, LEVEL_EDIT, origine))
        if node.restricted:
            herites = []
        herites.insert(0, ("group", "role:admin", LEVEL_MANAGE, "toujours"))
        directs = [(l.principal_type, l.principal_id, l.level) for l in acl.get(node.id, [])]
        libelles = self.directory.describe(
            db, member.org_id, [(t, i) for t, i, *_ in herites + directs if i != "everyone"]
        )

        def principal(t, i) -> Principal:
            if i == "everyone":
                return Principal("group", "everyone", "Tout le monde", "même sans compte")
            return libelles.get((t, i)) or Principal(t, i, "Inconnu")

        # Un même groupe hérité de plusieurs endroits : on garde le plus fort.
        fusion: dict[tuple[str, str], tuple[str, str]] = {}
        for t, i, niv, origine in herites:
            if (t, i) not in fusion or access.ORDER[niv] > access.ORDER[fusion[(t, i)][0]]:
                fusion[(t, i)] = (niv, origine)
        parent = loc.path[-2].name if len(loc.path) > 1 else self._space_label(node.space)
        return {
            "level": niveau,
            "restricted": node.restricted,
            "can_manage": access.at_least(niveau, LEVEL_MANAGE),
            # Dossier ou fichier (Seb, 15 octobre : le cadenas vaut pour les deux).
            "can_restrict": member.is_admin or member.is_superuser,
            "personal": False,
            "inherited_from": parent,
            "inherited": [
                {**self._principal_dict(principal(t, i)), "level": niv, "from": origine}
                for (t, i), (niv, origine) in fusion.items()
            ],
            "direct": [{**self._principal_dict(principal(t, i)), "level": niv} for t, i, niv in directs],
        }

    @staticmethod
    def _principal_dict(p: Principal) -> dict:
        return {"type": p.type, "id": p.id, "label": p.label, "detail": p.detail}

    def set_access(
        self, db: Session, member: Member, node_id: int, restricted: bool, entries: list[dict]
    ) -> dict:
        node = self._node(db, member, node_id)
        loc = self._locate(db, member, node)
        if node.space == "personal":
            raise DocError(409, "Un élément de l'espace Personnel ne se partage pas : rangez-le dans Privé ou Public.")
        self._require(db, member, loc, LEVEL_MANAGE)
        if restricted != node.restricted:
            # Dossier ou fichier (Seb, 15 octobre).
            if not (member.is_admin or member.is_superuser):
                raise DocError(403, "Seuls les administrateurs restreignent l'accès.")
            node.restricted = restricted
            self._log(db, member, node, "restricted" if restricted else "unrestricted")
        voulus: dict[tuple[str, str], str] = {}
        for entree in entries:
            t, i, niv = entree.get("type"), str(entree.get("id")), entree.get("level")
            # Voir | Modifier seulement : la Gestion reste aux admins (§4.4 bis).
            if t not in ("member", "group") or niv not in (LEVEL_VIEW, LEVEL_EDIT):
                raise DocError(422, "Accès invalide")
            voulus[(t, i)] = niv
        actuels = {(l.principal_type, l.principal_id): l for l in db.scalars(select(DocAcl).where(DocAcl.node_id == node.id))}
        libelles = self.directory.describe(db, member.org_id, list(set(voulus) | set(actuels)))
        for cle, ligne in actuels.items():
            if cle not in voulus:
                db.delete(ligne)
                self._log(db, member, node, "unshared", {"who": getattr(libelles.get(cle), "label", cle[1])})
            elif voulus[cle] != ligne.level:
                ligne.level = voulus[cle]
                self._log(db, member, node, "shared", {"who": getattr(libelles.get(cle), "label", cle[1]), "level": voulus[cle]})
        for cle, niv in voulus.items():
            if cle not in actuels:
                db.add(DocAcl(node_id=node.id, principal_type=cle[0], principal_id=cle[1], level=niv))
                self._log(db, member, node, "shared", {"who": getattr(libelles.get(cle), "label", cle[1]), "level": niv})
        db.commit()
        return self.get_access(db, member, node_id)

    def principals(self, db: Session, member: Member, query: str) -> list[dict]:
        return [self._principal_dict(p) for p in self.directory.search(db, member.org_id, query)]

    # ------------------------------------------------------------------

    def _log(self, db: Session, member: Member, node: DocNode, action: str, detail: dict | None = None) -> None:
        db.add(DocActivity(org_id=node.org_id, node_id=node.id, person_id=member.person_id, action=action, detail=detail))
