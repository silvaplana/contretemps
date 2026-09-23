"""Portée d'une requête : quelle saison on regarde, et verrou lecture seule
(voir spec/SPEC.md §2.6 et §6.1bis).

Tout est centralisé ici plutôt que dans chaque route, pour qu'aucune ne
puisse l'oublier :

- **Filtre de lecture** : toute requête SQL passée par l'ORM ne voit, dans
  les tables "racines" (celles qui ont un `saison_id` : comptes, familles,
  cours, conversations, inscriptions, correspondances d'import), que les
  lignes de la saison affichée. Par défaut, la saison courante de l'école
  de chaque ligne ; ou la saison demandée par le navigateur dans l'en-tête
  `X-Saison-Id` (un admin qui consulte une ancienne saison, contrôlé par
  comptes/rbac.py : compte_appelant). Les autres tables (présences,
  vidéos, messages...) sont atteintes à travers leur cours, compte ou
  conversation, donc déjà filtrées de fait.

- **Verrou d'écriture** : avant chaque écriture en base, toute ligne créée,
  modifiée ou supprimée dans une autre saison que la courante est refusée
  (`SaisonEnLectureSeule`, renvoyée en 403 par app/main.py). Les tables
  sans `saison_id` sont rattachées à leur racine par leur clé étrangère
  (voir PARENTS). Les tables de liaison écrites directement en SQL (sans
  objet ORM : cours ↔ profs, cours ↔ élèves, chorégraphie ↔ élèves) sont
  vérifiées par `verifier_modifiable` dans leur service.

- **Toutes saisons** : ce qui doit tout voir ou tout écrire (sauvegarde et
  restauration technique, vidage de l'école, création d'une saison avec
  duplication, total de l'usage vidéo) passe par `toutes_saisons(db)`.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

from sqlalchemy import event, func, inspect, or_, select, text
from sqlalchemy.orm import Session, with_loader_criteria

ENTETE_SAISON = "X-Saison-Id"
# Clé posée dans `session.info` (ou en option d'exécution d'une requête)
# pour désactiver filtre et verrou.
TOUTES_SAISONS = "toutes_saisons"

_saison_demandee: ContextVar[int | None] = ContextVar("saison_demandee", default=None)

# Tables sans `saison_id` : (colonne, table parente) pour remonter jusqu'à
# une table racine. Une table absente d'ici et sans `saison_id` n'est pas
# propre à une saison (écoles, saisons, abonnements aux notifications).
PARENTS: dict[str, tuple[str, str]] = {
    "choregraphies": ("cours_id", "cours"),
    "contacts_eleves": ("eleve_id", "comptes"),
    "conversation_membres": ("conversation_id", "conversations"),
    "cours_horaires_supplementaires": ("cours_id", "cours"),
    "message_deliveries": ("message_id", "messages"),
    "messages": ("conversation_id", "conversations"),
    "presences_eleves": ("seance_id", "seances_presence"),
    "presences_profs": ("seance_id", "seances_presence"),
    "profils_eleves": ("compte_id", "comptes"),
    "roles_compte": ("compte_id", "comptes"),
    "seances_presence": ("cours_id", "cours"),
    "televersements_video": ("cours_id", "cours"),
    "videos": ("cours_id", "cours"),
}

# Colonnes qui peuvent changer même sur une fiche d'une ancienne saison :
# "dernière connexion", mise à jour à la fermeture d'une connexion en cours.
_COLONNES_TOUJOURS_MODIFIABLES = {"comptes": {"derniere_activite_le"}}


class SaisonEnLectureSeule(Exception):
    """Écriture refusée : la ligne visée appartient à une ancienne saison."""

    message = "Cette saison est terminée : elle est en lecture seule."


# --- Saison demandée par le navigateur (en-tête X-Saison-Id) ---


def saison_demandee() -> int | None:
    return _saison_demandee.get()


class MiddlewareSaison:
    """Lit l'en-tête `X-Saison-Id` de chaque requête. Middleware ASGI (pas
    une dépendance FastAPI) : une dépendance synchrone tourne dans un
    autre fil, d'où la valeur ne reviendrait pas jusqu'à la route.

    Ignoré sur les routes de connexion (`/auth/...`) : se connecter se fait
    toujours dans la saison courante (§2.2), quel que soit l'en-tête."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path", "").startswith("/auth/"):
            await self.app(scope, receive, send)
            return
        valeur = None
        for nom, contenu in scope.get("headers", []):
            if nom.decode("latin-1").lower() == ENTETE_SAISON.lower():
                try:
                    valeur = int(contenu.decode("latin-1"))
                except ValueError:
                    valeur = None
        jeton = _saison_demandee.set(valeur)
        try:
            await self.app(scope, receive, send)
        finally:
            _saison_demandee.reset(jeton)


@contextmanager
def toutes_saisons(db: Session):
    """Désactive filtre et verrou pour ce qui est fait dans le bloc."""
    avant = db.info.get(TOUTES_SAISONS)
    db.info[TOUTES_SAISONS] = True
    try:
        yield
    finally:
        if avant is None:
            db.info.pop(TOUTES_SAISONS, None)
        else:
            db.info[TOUTES_SAISONS] = avant


def _desactive(session: Session, options: dict | None = None) -> bool:
    return bool(session.info.get(TOUTES_SAISONS) or (options or {}).get(TOUTES_SAISONS))


# --- Filtre de lecture ---


def _classes_racines() -> list[type]:
    from db.database import Base

    return [
        mapper.class_
        for mapper in Base.registry.mappers
        if "saison_id" in mapper.local_table.c and mapper.local_table.name != "saisons"
    ]


@event.listens_for(Session, "do_orm_execute")
def _filtrer_par_saison(etat) -> None:
    if not (etat.is_select or etat.is_update or etat.is_delete):
        return
    if etat.is_column_load or etat.is_relationship_load:
        # Déjà couvert : l'option posée sur la requête d'origine se propage
        # aux chargements qui en découlent.
        return
    if _desactive(etat.session, etat.execution_options):
        return
    from .models import Saison

    demandee = saison_demandee()
    for classe in _classes_racines():
        if demandee is not None:
            critere = with_loader_criteria(
                classe,
                lambda cls: or_(cls.ecole_id.is_(None), cls.saison_id == demandee),
                include_aliases=True,
            )
        else:
            critere = with_loader_criteria(
                classe,
                lambda cls: or_(
                    cls.ecole_id.is_(None),
                    cls.saison_id
                    == select(func.max(Saison.id)).where(Saison.ecole_id == cls.ecole_id).scalar_subquery(),
                ),
                include_aliases=True,
            )
        etat.statement = etat.statement.options(critere)


# --- Verrou d'écriture ---


def _racine(connexion, table: str, valeurs: dict) -> tuple[int | None, int | None]:
    """(saison_id, ecole_id) de la racine d'une ligne, en remontant ses
    parents. (None, None) si la ligne n'a pas de racine connue (parent pas
    encore enregistré : il est alors vérifié lui-même)."""
    while table in PARENTS:
        colonne, parent = PARENTS[table]
        identifiant = valeurs.get(colonne)
        if identifiant is None:
            return None, None
        colonnes = PARENTS[parent][0] if parent in PARENTS else "saison_id, ecole_id"
        ligne = connexion.execute(
            text(f"SELECT {colonnes} FROM {parent} WHERE id = :id"), {"id": identifiant}
        ).mappings().first()
        if ligne is None:
            return None, None
        table, valeurs = parent, dict(ligne)
    return valeurs.get("saison_id"), valeurs.get("ecole_id")


def _saison_courante(connexion, ecole_id: int, cache: dict) -> int | None:
    if ecole_id not in cache:
        cache[ecole_id] = connexion.execute(
            text("SELECT MAX(id) FROM saisons WHERE ecole_id = :e"), {"e": ecole_id}
        ).scalar()
    return cache[ecole_id]


def verifier_modifiable(db: Session, table: str, identifiant: int) -> None:
    """Refuse (SaisonEnLectureSeule) de toucher à ce qui dépend de la ligne
    `identifiant` de `table` (ex. le cours dont on change les élèves) si
    elle appartient à une ancienne saison. Pour les écritures faites sans
    objet ORM (tables de liaison), que verifier_flush ne voit pas."""
    if _desactive(db):
        return
    connexion = db.connection()
    colonnes = PARENTS[table][0] if table in PARENTS else "saison_id, ecole_id"
    ligne = connexion.execute(
        text(f"SELECT {colonnes} FROM {table} WHERE id = :id"), {"id": identifiant}
    ).mappings().first()
    if ligne is None:
        return
    saison_id, ecole_id = _racine(connexion, table, dict(ligne))
    if saison_id is not None and saison_id != _saison_courante(connexion, ecole_id, {}):
        raise SaisonEnLectureSeule()


def _valeurs(objet, deja_en_base: bool) -> dict:
    """Valeurs des colonnes de l'objet. Pour une ligne modifiée ou
    supprimée, celles d'AVANT la modification : c'est la saison où elle
    se trouve en base qui compte."""
    etat = inspect(objet)
    valeurs = {}
    for attribut in etat.mapper.column_attrs:
        historique = etat.attrs[attribut.key].history
        if deja_en_base and (historique.deleted or historique.unchanged):
            valeur = (historique.deleted or historique.unchanged)[0]
        else:
            valeur = getattr(objet, attribut.key)
        valeurs[attribut.columns[0].name] = valeur
    return valeurs


def _seulement_colonnes_libres(objet, table: str) -> bool:
    libres = _COLONNES_TOUJOURS_MODIFIABLES.get(table)
    if not libres:
        return False
    etat = inspect(objet)
    modifiees = {a.key for a in etat.mapper.column_attrs if etat.attrs[a.key].history.has_changes()}
    return modifiees <= libres


def verifier_flush(session: Session) -> None:
    """Appelé avant chaque écriture (voir automatique.py) : refuse toute
    ligne créée, modifiée ou supprimée hors de la saison courante."""
    if _desactive(session):
        return
    connexion = session.connection()
    courantes: dict[int, int | None] = {}
    a_verifier = [(o, False) for o in session.new]
    a_verifier += [(o, True) for o in session.dirty if session.is_modified(o, include_collections=False)]
    a_verifier += [(o, True) for o in session.deleted]
    with session.no_autoflush:
        for objet, deja_en_base in a_verifier:
            table = getattr(objet, "__tablename__", None)
            if table is None or (table not in PARENTS and "saison_id" not in objet.__table__.c):
                continue
            if deja_en_base and _seulement_colonnes_libres(objet, table):
                continue
            saison_id, ecole_id = _racine(connexion, table, _valeurs(objet, deja_en_base))
            if saison_id is None:
                continue
            if saison_id != _saison_courante(connexion, ecole_id, courantes):
                raise SaisonEnLectureSeule()
