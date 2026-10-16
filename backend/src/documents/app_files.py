"""Fichiers de l'appli (fichier de base, spec fichier-de-base.md) : création
avec sa nature, contenu JSON versionné, essais et réponses.

Branché sur `Documents` (service.py) par composition : les droits, l'état,
la corbeille et la copie restent ceux de tous les fichiers.
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import access, app_content
from .app_content import ContentError
from .models import (
    FAMILIES,
    KIND_APP,
    LEVEL_EDIT,
    LEVEL_MANAGE,
    LEVEL_VIEW,
    DocAppVersion,
    DocNode,
    DocResponse,
    utcnow,
)
from .ports import Member

if TYPE_CHECKING:
    from .service import Documents

# Les enregistrements successifs d'une même personne restent une seule
# version pendant ce délai (l'éditeur enregistre tout seul en cours de
# frappe) ; au-delà, une nouvelle version est créée.
MERGE_WINDOW = timedelta(minutes=10)

DEFAULT_NAMES = {"inform": "Nouveau fichier à lire", "question": "Nouvelles questions", "act": "Nouvelle inscription"}


class AppFiles:
    def __init__(self, docs: Documents) -> None:
        self.docs = docs

    def _error(self, status: int, message: str):
        from .service import DocError

        return DocError(status, message)

    def _app_node(self, db: Session, member: Member, node_id: int) -> DocNode:
        node = self.docs._node(db, member, node_id)
        if node.kind != KIND_APP:
            from .service import not_found

            raise not_found()
        return node

    @staticmethod
    def current_version(db: Session, node: DocNode) -> DocAppVersion | None:
        return db.scalar(
            select(DocAppVersion).where(DocAppVersion.node_id == node.id).order_by(DocAppVersion.number.desc()).limit(1)
        )

    def _add_version(self, db: Session, member: Member, node: DocNode, content: dict, origin: str) -> DocAppVersion:
        numero = (db.scalar(select(func.max(DocAppVersion.number)).where(DocAppVersion.node_id == node.id)) or 0) + 1
        version = DocAppVersion(node_id=node.id, number=numero, content=content, origin=origin, created_by=member.person_id)
        db.add(version)
        db.flush()
        node.updated_by, node.updated_at = member.person_id, utcnow()
        return version

    # ------------------------------------------------------------------

    def create(self, db: Session, member: Member, space: str, parent_id: int | None, family: str, name: str | None) -> dict:
        if family not in FAMILIES:
            raise self._error(422, "Choisissez Informer, Questionner ou Agir.")
        from .service import clean_name

        loc = self.docs._target(db, member, space, parent_id)
        nom = clean_name(name or DEFAULT_NAMES[family])
        nom = self.docs._free_name(db, member, loc, nom) or nom
        node = self.docs._new_node(
            member.org_id, loc.space, parent_id, KIND_APP, nom, member.person_id, family=family, status="draft"
        )
        node.owner_person_id = loc.owner_person_id
        db.add(node)
        db.flush()
        self._add_version(db, member, node, app_content.empty_content(), "created")
        self.docs._log(db, member, node, "created")
        db.commit()
        return {"id": node.id, "name": node.name}

    def get(self, db: Session, member: Member, node_id: int) -> dict:
        node = self._app_node(db, member, node_id)
        loc = self.docs._locate(db, member, node)
        niveau = self.docs._require(db, member, loc, LEVEL_VIEW)
        version = self.current_version(db, node)
        peut_modifier = access.at_least(niveau, LEVEL_EDIT)
        reponses = 0
        if peut_modifier:
            reponses = db.scalar(select(func.count()).select_from(DocResponse).where(DocResponse.node_id == node.id)) or 0
        return {
            "id": node.id,
            "name": node.name,
            "space": node.space,
            "parent_id": node.parent_id,
            "status": node.status,
            "family": node.family,
            "level": niveau,
            "can_edit": peut_modifier,
            "can_manage": access.at_least(niveau, LEVEL_MANAGE),
            # Le contenu se modifie en Brouillon seulement (§4), et pas sous
            # un dossier Officiel.
            "editable": peut_modifier and node.status in (None, "draft") and self.docs._official_lock(loc.path) is None,
            "frozen_by": (lambda v: v.name if v is not None else None)(self.docs._official_lock(loc.path)),
            "content": version.content if version else app_content.empty_content(),
            "version": {"id": version.id, "number": version.number} if version else None,
            "response_count": reponses,
            "updated_at": node.updated_at.isoformat() if node.updated_at else None,
        }

    def save(
        self, db: Session, member: Member, node_id: int, content, family: str | None = None,
        base_version: int | None = None, origin: str = "human",
    ) -> dict:
        node = self._app_node(db, member, node_id)
        loc = self.docs._locate(db, member, node)
        self.docs._require(db, member, loc, LEVEL_EDIT)
        self.docs._require_unfrozen(loc.path)
        if node.status not in (None, "draft"):
            raise self._error(409, "Repassez le fichier en Brouillon pour le modifier.")
        nature = family or node.family
        if nature not in FAMILIES:
            raise self._error(422, "Nature inconnue")
        try:
            propre = app_content.check_content(content, nature)
        except ContentError as erreur:
            raise self._error(422, str(erreur)) from erreur
        courante = self.current_version(db, node)
        if base_version is not None and courante is not None and courante.number != base_version:
            raise self._error(409, "Ce fichier vient d'être modifié ailleurs. Rechargez-le pour voir la dernière version.")
        if nature != node.family:
            self.docs._log(db, member, node, "family", {"from": node.family, "to": nature})
            node.family = nature
        maintenant = utcnow()
        fusion = (
            courante is not None
            and courante.origin == origin == "human"
            and courante.created_by == member.person_id
            and maintenant - (courante.updated_at or courante.created_at) < MERGE_WINDOW
            and not self._has_responses(db, courante)
        )
        if fusion:
            courante.content = propre
            courante.updated_at = maintenant
            node.updated_by, node.updated_at = member.person_id, maintenant
            version = courante
        else:
            version = self._add_version(db, member, node, propre, origin)
            self.docs._log(db, member, node, "edited", {"version": version.number})
        db.commit()
        return {"version": {"id": version.id, "number": version.number}, "family": node.family}

    @staticmethod
    def _has_responses(db: Session, version: DocAppVersion) -> bool:
        return db.scalar(select(func.count()).select_from(DocResponse).where(DocResponse.version_id == version.id)) > 0

    # ------------------------------------------------------------------
    # Réponses
    # ------------------------------------------------------------------

    def try_answer(self, db: Session, member: Member, node_id: int, values) -> dict:
        """« Essayer » (Aperçu) : une vraie réponse, marquée essai, qui ne
        crée rien dans l'appli (fichier-de-base.md §2.2)."""
        node = self._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_EDIT)
        version = self.current_version(db, node)
        if node.family == "inform" or version is None or not app_content.questions(version.content):
            raise self._error(409, "Rien à remplir : ce fichier se lit seulement.")
        try:
            gardees = app_content.check_values(version.content, values, test=True)
        except ContentError as erreur:
            raise self._error(422, str(erreur)) from erreur
        reponse = DocResponse(
            org_id=member.org_id, node_id=node.id, version_id=version.id, person_id=member.person_id,
            status="answered", is_test=True, source="test", values=gardees,
        )
        db.add(reponse)
        db.commit()
        return {"id": reponse.id}

    def responses(self, db: Session, member: Member, node_id: int) -> dict:
        node = self._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_EDIT)
        lignes = list(
            db.scalars(select(DocResponse).where(DocResponse.node_id == node.id).order_by(DocResponse.created_at, DocResponse.id))
        )
        noms = self.docs.directory.person_names(db, member.org_id, {r.person_id for r in lignes if r.person_id})
        return {
            "items": [
                {
                    "id": r.id,
                    "who": noms.get(r.person_id) or r.email or "Anonyme",
                    "is_test": r.is_test,
                    "source": r.source,
                    "status": r.status,
                    "values": r.values,
                    "version_id": r.version_id,
                    "at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in lignes
            ]
        }

    def clear_tests(self, db: Session, member: Member, node_id: int) -> dict:
        node = self._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_EDIT)
        n = (
            db.query(DocResponse)
            .filter(DocResponse.node_id == node.id, DocResponse.is_test.is_(True))
            .delete(synchronize_session=False)
        )
        db.commit()
        return {"erased": n}

    # ------------------------------------------------------------------
    # Appelé par Documents (copie, effacement)
    # ------------------------------------------------------------------

    def copy_content(self, db: Session, member: Member, source: DocNode, copie: DocNode) -> None:
        """Copie : la dernière version seulement, sans les réponses."""
        version = self.current_version(db, source)
        contenu = version.content if version else app_content.empty_content()
        self._add_version(db, member, copie, contenu, "created")

    @staticmethod
    def erase(db: Session, ids: set[int]) -> None:
        for modele in (DocResponse, DocAppVersion):
            db.query(modele).filter(modele.node_id.in_(ids)).delete(synchronize_session=False)
