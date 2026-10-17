"""Tables du module documents (voir appbase/spec/modules/documents.md §4).

Aucune clé étrangère vers les tables de l'appli hôte (écoles, comptes,
saisons) : le module ne les connaît pas. `org_id`, `*_person_id` et
`period_id` sont de simples entiers, fournis par les ports (voir ports.py).

Aucune colonne ne s'appelle `saison_id` : ces tables ne sont pas filtrées
par saison (le dossier Permanent n'a pas de saison, et les dossiers des
saisons passées restent lisibles depuis la saison courante). Le verrou des
saisons closes est appliqué par le module lui-même (access.py, règle 0).
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Espaces (§4.0) : Public (tout le monde), Privé (ceux à qui c'est partagé,
# admins et rôles listés), Personnel (le propriétaire seulement).
SPACES = ("public", "private", "personal")

KIND_FOLDER = "folder"
KIND_FILE = "file"
# Fichier de l'appli (fichier de base, spec fichier-de-base.md) : son
# contenu est un JSON de blocs versionné (DocAppVersion), pas un binaire.
KIND_APP = "app"

# Statuts (§5.4, badges §7.1 ter) ; None = pas de badge.
STATUSES = ("draft", "refused", "validated", "official")

# Familles des fichiers de l'appli (§7.1 bis) ; None = fichier importé.
FAMILIES = ("inform", "question", "act")

# Dossiers système (§4.7) : impossibles à renommer, déplacer, supprimer.
SYSTEM_PERMANENT = "permanent"
SYSTEM_PERIOD = "period"
# Dossier réservé à un groupe (§4.7 bis), ex. « Financier » des trésoriers :
# même les admins n'y entrent pas sans faire partie du groupe.
SYSTEM_RESERVED = "reserved"

LEVEL_VIEW = "view"
LEVEL_EDIT = "edit"
LEVEL_MANAGE = "manage"


class StoredFile(Base):
    """Un contenu binaire, rangé sur le disque par son empreinte sha256 :
    deux versions identiques (une copie de dossier d'une saison à l'autre)
    ne prennent pas deux fois la place."""

    __tablename__ = "doc_stored_files"
    __table_args__ = (UniqueConstraint("org_id", "sha256", name="uq_doc_stored_org_sha"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    mime: Mapped[str] = mapped_column(String(120), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocNode(Base):
    """Un élément de l'arborescence : dossier ou fichier."""

    __tablename__ = "doc_nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    space: Mapped[str] = mapped_column(String(10), nullable=False)
    # Espace Personnel : à qui il appartient (personne, voir ports.Member).
    owner_person_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    # None : à la racine de l'espace.
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("doc_nodes.id"), nullable=True, index=True)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Nom en minuscules sans accents, pour la recherche (LIKE, portable
    # SQLite/Postgres, voir le plan §1 règle 5).
    name_search: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    family: Mapped[str | None] = mapped_column(String(10), nullable=True)
    system_kind: Mapped[str | None] = mapped_column(String(10), nullable=True)
    period_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Dossiers seulement : accès restreint, arrête l'héritage (§4.4 règle 3).
    restricted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Fichiers : version courante (et ses caractéristiques, recopiées pour
    # lister sans jointure).
    current_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    # Corbeille (30 jours, puis effacé pour de bon).
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    deleted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)


class DocVersion(Base):
    """Une version d'un fichier. La plus récente est `DocNode.current_version_id`."""

    __tablename__ = "doc_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("doc_nodes.id"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    stored_file_id: Mapped[int] = mapped_column(ForeignKey("doc_stored_files.id"), nullable=False)
    # Nom du fichier envoyé (il peut changer d'une version à l'autre).
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocAcl(Base):
    """Un droit donné sur un nœud à une personne ou à un groupe (§4.4)."""

    __tablename__ = "doc_acl"
    __table_args__ = (
        UniqueConstraint("node_id", "principal_type", "principal_id", name="uq_doc_acl_principal"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("doc_nodes.id"), nullable=False, index=True)
    # "member" (principal_id = id de personne) ou "group" (clé de groupe
    # fournie par le port Groups, ex. "role:professeur", "course:12").
    principal_type: Mapped[str] = mapped_column(String(10), nullable=False)
    principal_id: Mapped[str] = mapped_column(String(60), nullable=False)
    level: Mapped[str] = mapped_column(String(10), nullable=False)


class DocActivity(Base):
    """Journal : qui a fait quoi sur quel nœud (onglet Historique)."""

    __tablename__ = "doc_activity"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("doc_nodes.id"), nullable=False, index=True)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocAppVersion(Base):
    """Une version du contenu d'un fichier de l'appli : les deux formulaires
    (entrée, résultat) en JSON de blocs, jamais de HTML (fichier-de-base.md
    §6). La plus récente (plus grand `number`) est la version courante."""

    __tablename__ = "doc_app_versions"
    __table_args__ = (UniqueConstraint("node_id", "number", name="uq_doc_app_version_number"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("doc_nodes.id"), nullable=False, index=True)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    # "created" (fichier neuf ou copie), "human" (modifié à la main), "ai".
    origin: Mapped[str] = mapped_column(String(10), nullable=False, default="human")
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocResponse(Base):
    """Une réponse au formulaire d'entrée d'un fichier de l'appli : une ligne
    par personne (fichier-de-base.md §6.1). Les valeurs sont rangées sous
    l'identifiant stable de chaque question ; la version dit à quel
    formulaire la personne a répondu."""

    __tablename__ = "doc_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("doc_nodes.id"), nullable=False, index=True)
    version_id: Mapped[int] = mapped_column(ForeignKey("doc_app_versions.id"), nullable=False)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # "answered" ; "pending" et "started" viendront avec la diffusion.
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="answered")
    # Essai depuis l'Aperçu : ne crée rien dans l'appli, effaçable.
    is_test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # "test" pour l'instant ; "link" (lien personnel), "public" ensuite.
    source: Mapped[str] = mapped_column(String(10), nullable=False, default="test")
    values: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocAppTemplate(Base):
    """Modèle de l'école : un fichier de l'appli promu par « Faire un modèle »
    (fichier-de-base.md §5). Une tuile dans le + : la toucher crée une copie
    en Brouillon. Le contenu est recopié au moment de la promotion (jamais
    les réponses) ; le fichier d'origine peut ensuite changer ou disparaître."""

    __tablename__ = "doc_app_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    # Nom de la tuile, au verbe (« Organiser la fête de fin d'année »).
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    family: Mapped[str] = mapped_column(String(10), nullable=False)
    content: Mapped[dict] = mapped_column(JSON, nullable=False)
    source_node_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Caché du + (les admins le voient encore, grisé).
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class DocPublication(Base):
    """Page en ligne d'un fichier de l'appli (documents.md §5.5,
    fichier-de-base.md §2.3) : `https://<slug>.<école>.<appli>…`. Le nom
    (`slug`) n'est jamais réutilisé dans l'organisation, même dépublié, pour
    qu'un vieux lien ne tombe jamais sur une autre page. La page montre la
    version épinglée, jamais le brouillon en cours.

    Pas de clé étrangère : la ligne reste (nom réservé) quand le fichier est
    effacé de la corbeille."""

    __tablename__ = "doc_publications"
    __table_args__ = (UniqueConstraint("org_id", "slug", name="uq_doc_publication_slug"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(40), nullable=False)
    version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    unpublished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    visits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class DocSend(Base):
    """Un envoi de « Diffuser » à une personne choisie (fichier-de-base.md
    §2.3) : son lien personnel (`token`), où il en est (envoyé, ouvert,
    répondu). En Validé, l'envoi va aux relecteurs et leurs réponses sont des
    essais (`test`, décision de Seb du 16 octobre)."""

    __tablename__ = "doc_sends"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    org_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    node_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    person_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel: Mapped[str] = mapped_column(String(10), nullable=False, default="email")
    test: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # "pending" (en cours d'envoi), "sent", "failed".
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sent_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opened_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    response_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
