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

from . import access, app_content, assembly
from .app_content import ContentError
from .models import (
    FAMILIES,
    KIND_APP,
    LEVEL_EDIT,
    LEVEL_MANAGE,
    LEVEL_VIEW,
    DocAppTemplate,
    DocAppVersion,
    DocAttendance,
    DocNode,
    DocPublication,
    DocResponse,
    DocSend,
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

    def create(
        self, db: Session, member: Member, space: str, parent_id: int | None, family: str, name: str | None,
        content: dict | None = None,
    ) -> dict:
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
        self.docs._arrive(node, loc)
        db.add(node)
        db.flush()
        self._add_version(db, member, node, content or app_content.empty_content(), "created")
        self.docs._log(db, member, node, "created")
        db.commit()
        return {"id": node.id, "name": node.name}

    def get(self, db: Session, member: Member, node_id: int) -> dict:
        node = self._app_node(db, member, node_id)
        loc = self.docs._locate(db, member, node)
        niveau = self.docs._require(db, member, loc, LEVEL_VIEW)
        version = self.current_version(db, node)
        peut_modifier = access.at_least(niveau, LEVEL_EDIT)
        verrou = self.docs._official_lock(loc.path)
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
            "editable": peut_modifier and node.status in (None, "draft") and verrou is None,
            "frozen_by": verrou.name if verrou is not None else None,
            "content": version.content if version else app_content.empty_content(),
            "version": {"id": version.id, "number": version.number} if version else None,
            "response_count": reponses,
            "publication": self._publication_dict(db, node),
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
            gardees = assembly.check_answer(self.docs, db, node, version.content, gardees, member.person_id, None, test=True)
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
                    "who": noms.get(r.person_id) or r.email or ("Page en ligne" if r.source == "public" else "Anonyme"),
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
        for modele in (DocSend, DocResponse, DocAppVersion, DocAttendance):
            db.query(modele).filter(modele.node_id.in_(ids)).delete(synchronize_session=False)
        # Le nom de la page reste réservé ; la page ne s'affiche plus.
        db.query(DocPublication).filter(DocPublication.node_id.in_(ids)).update(
            {"unpublished_at": utcnow(), "version_id": None}, synchronize_session=False
        )


    # ------------------------------------------------------------------
    # Modèles de l'école (fichier-de-base.md §5)
    # ------------------------------------------------------------------

    def _require_admin(self, member: Member) -> None:
        if not (member.is_admin or member.is_superuser):
            raise self._error(403, "Seuls les admins font et rangent les modèles de l'école.")

    def _template(self, db: Session, member: Member, template_id: int) -> DocAppTemplate:
        modele = db.get(DocAppTemplate, template_id)
        if modele is None or modele.org_id != member.org_id:
            raise self._error(404, "Ce modèle n'existe plus.")
        return modele

    def _template_name(self, db: Session, member: Member, name: str, sauf: int | None = None) -> str:
        from .service import clean_name

        nom = clean_name(name)
        pris = {
            n.lower()
            for n in db.scalars(
                select(DocAppTemplate.name).where(DocAppTemplate.org_id == member.org_id, DocAppTemplate.id != (sauf or 0))
            )
        }
        libre, n = nom, 2
        while libre.lower() in pris:
            libre, n = f"{nom} ({n})", n + 1
        return libre

    @staticmethod
    def _template_dict(modele: DocAppTemplate) -> dict:
        return {
            "id": modele.id,
            "name": modele.name,
            "family": modele.family,
            "hidden": modele.hidden,
            "source_node_id": modele.source_node_id,
            "question_count": len(app_content.questions(modele.content)),
        }

    def make_template(self, db: Session, member: Member, node_id: int, name: str) -> dict:
        """« Faire un modèle » : recopie les deux formulaires, jamais les
        réponses ni le chat."""
        self._require_admin(member)
        node = self._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_VIEW)
        version = self.current_version(db, node)
        contenu = version.content if version else app_content.empty_content()
        if not contenu.get("entry", {}).get("blocks"):
            raise self._error(409, "Le fichier est vide : préparez-le avant d'en faire un modèle.")
        modele = DocAppTemplate(
            org_id=member.org_id, name=self._template_name(db, member, name), family=node.family,
            content=contenu, source_node_id=node.id, created_by=member.person_id,
        )
        db.add(modele)
        self.docs._log(db, member, node, "template", {"name": modele.name})
        db.commit()
        return self._template_dict(modele)

    def templates(self, db: Session, member: Member) -> dict:
        """Les tuiles « de l'école » du + ; les modèles cachés ne sont
        listés qu'aux admins."""
        requete = select(DocAppTemplate).where(DocAppTemplate.org_id == member.org_id)
        admin = member.is_admin or member.is_superuser
        if not admin:
            requete = requete.where(DocAppTemplate.hidden.is_(False))
        modeles = db.scalars(requete.order_by(DocAppTemplate.name)).all()
        return {"items": [self._template_dict(m) for m in modeles], "can_manage": admin}

    def use_template(self, db: Session, member: Member, template_id: int, space: str, parent_id: int | None) -> dict:
        """Toucher la tuile : une copie en Brouillon, déjà remplie."""
        modele = self._template(db, member, template_id)
        if modele.hidden and not (member.is_admin or member.is_superuser):
            raise self._error(404, "Ce modèle n'existe plus.")
        return self.create(db, member, space, parent_id, modele.family, modele.name, content=modele.content)

    def update_template(self, db: Session, member: Member, template_id: int, name: str | None, hidden: bool | None) -> dict:
        self._require_admin(member)
        modele = self._template(db, member, template_id)
        if name is not None:
            modele.name = self._template_name(db, member, name, sauf=modele.id)
        if hidden is not None:
            modele.hidden = hidden
        modele.updated_at = utcnow()
        db.commit()
        return self._template_dict(modele)

    def delete_template(self, db: Session, member: Member, template_id: int) -> None:
        self._require_admin(member)
        db.delete(self._template(db, member, template_id))
        db.commit()


    # ------------------------------------------------------------------
    # Page en ligne (documents.md §5.5, fichier-de-base.md §2.3)
    # ------------------------------------------------------------------

    @staticmethod
    def _publication(db: Session, node: DocNode) -> DocPublication | None:
        return db.scalar(select(DocPublication).where(DocPublication.node_id == node.id).order_by(DocPublication.id.desc()).limit(1))

    def _publication_dict(self, db: Session, node: DocNode) -> dict | None:
        p = self._publication(db, node)
        if p is None:
            return None
        en_ligne = p.unpublished_at is None and p.version_id is not None
        version = db.get(DocAppVersion, p.version_id) if p.version_id else None
        return {
            "slug": p.slug,
            "online": en_ligne,
            "version": version.number if version else None,
            "published_at": p.published_at.isoformat() if p.published_at else None,
            "visits": p.visits,
        }

    def _free_slug(self, db: Session, org_id: int, name: str) -> str:
        base = slugify(name)
        pris = set(db.scalars(select(DocPublication.slug).where(DocPublication.org_id == org_id)))
        libre, n = base, 2
        while libre in pris or libre in RESERVED_SLUGS:
            suffixe = f"-{n}"
            libre, n = base[: 40 - len(suffixe)] + suffixe, n + 1
        return libre

    def publish(self, db: Session, member: Member, node_id: int) -> dict:
        """« Mettre en ligne » : ouvert à tout le monde, donc en Officiel
        seulement (en Validé, on diffuse aux relecteurs : décision de Seb du
        16 octobre, fichier-de-base.md §7)."""
        node = self._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_MANAGE)
        if node.space == "personal":
            raise self._error(409, "Un fichier de l'espace Personnel ne se met pas en ligne.")
        if node.status != "official":
            raise self._error(409, "Passez d'abord le fichier en Officiel pour l'ouvrir à tout le monde.")
        version = self.current_version(db, node)
        if version is None or not version.content.get("entry", {}).get("blocks"):
            raise self._error(409, "La page est vide.")
        if assembly.block_of(version.content) is not None:
            raise self._error(409, "Une convocation part par lien personnel : chacun répond et signe pour lui-même.")
        p = self._publication(db, node)
        if p is None:
            p = DocPublication(org_id=node.org_id, node_id=node.id, slug=self._free_slug(db, node.org_id, node.name))
            db.add(p)
        p.version_id, p.published_by, p.published_at, p.unpublished_at = version.id, member.person_id, utcnow(), None
        self.docs._log(db, member, node, "published", {"slug": p.slug})
        db.commit()
        return self._publication_dict(db, node)

    def unpublish(self, db: Session, member: Member, node_id: int) -> dict | None:
        node = self._app_node(db, member, node_id)
        self.docs._require(db, member, self.docs._locate(db, member, node), LEVEL_MANAGE)
        p = self._publication(db, node)
        if p is not None and p.unpublished_at is None:
            p.unpublished_at = utcnow()
            self.docs._log(db, member, node, "unpublished", {"slug": p.slug})
            db.commit()
        return self._publication_dict(db, node)

    # Routes publiques : pas de membre, l'organisation vient de l'adresse.

    def _online(self, db: Session, org_id: int, slug: str) -> tuple[DocPublication, DocNode, DocAppVersion]:
        p = db.scalar(select(DocPublication).where(DocPublication.org_id == org_id, DocPublication.slug == slug))
        node = db.get(DocNode, p.node_id) if p is not None else None
        version = db.get(DocAppVersion, p.version_id) if p is not None and p.version_id else None
        if p is None or p.unpublished_at is not None or node is None or node.deleted_at is not None or version is None:
            raise self._error(404, "Cette page n'est pas (ou plus) en ligne.")
        return p, node, version

    def page_exists(self, db: Session, org_id: int, slug: str) -> bool:
        from .service import DocError

        try:
            self._online(db, org_id, slug)
            return True
        except DocError:
            return False

    def public_page(self, db: Session, org_id: int, slug: str) -> dict:
        p, node, version = self._online(db, org_id, slug)
        p.visits = (p.visits or 0) + 1
        db.commit()
        return {
            "name": node.name,
            "family": node.family,
            "content": {"schema": version.content.get("schema", 1), "entry": version.content.get("entry", {"blocks": []})},
            # Les réponses arrivent tant que le fichier reste Officiel.
            "accepting": node.family != "inform" and node.status == "official",
        }

    def public_answer(self, db: Session, org_id: int, slug: str, values) -> dict:
        _, node, version = self._online(db, org_id, slug)
        if node.family == "inform" or node.status != "official" or assembly.block_of(version.content) is not None:
            raise self._error(409, "Les réponses sont fermées.")
        try:
            gardees = app_content.check_values(version.content, values, test=False)
        except ContentError as erreur:
            raise self._error(422, str(erreur)) from erreur
        db.add(DocResponse(
            org_id=node.org_id, node_id=node.id, version_id=version.id, status="answered",
            is_test=False, source="public", values=gardees,
        ))
        db.commit()
        return {"ok": True}


RESERVED_SLUGS = {"www", "api", "admin", "app", "docs", "mail", "static"}


def slugify(name: str) -> str:
    """« Convocation AG 2026 » -> « convocation-ag-2026 » : minuscules, sans
    accents, [a-z0-9-], 3 à 40 caractères."""
    import unicodedata

    texte = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    morceaux, courant = [], ""
    for c in texte:
        if c.isalnum():
            courant += c
        elif courant:
            morceaux.append(courant)
            courant = ""
    if courant:
        morceaux.append(courant)
    slug = "-".join(morceaux)[:40].strip("-")
    return slug if len(slug) >= 3 else (slug + "-page").strip("-")
