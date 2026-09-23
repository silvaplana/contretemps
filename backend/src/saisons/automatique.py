"""Rattachement automatique à une saison et verrou lecture seule (voir
spec/SPEC.md §2.6).

Appliqués par SQLAlchemy à chaque écriture, pour qu'aucun chemin de
création (routes, import Excel, formulaire d'inscription, seed...) ne
puisse oublier la saison :
- une école toute neuve reçoit aussitôt sa première saison ;
- toute nouvelle ligne qui a un `saison_id` vide et un `ecole_id` connu
  (compte, famille, cours, conversation, inscription, correspondance de
  colonne d'import) est rattachée à la saison affichée : celle demandée par
  le navigateur, sinon la courante de son école ;
- puis toute écriture hors de la saison courante est refusée (voir
  portee.py : verifier_flush). Une création pendant la consultation d'une
  ancienne saison est donc refusée, et non rangée en douce dans la
  courante.

Enregistré une seule fois, à l'import de ce module (voir db/__init__.py).
Écouteurs posés sur `Base` et `Session` plutôt que sur chaque modèle :
aucun import des modules métier ici, donc aucun import circulaire.
"""

from __future__ import annotations

from sqlalchemy import event, insert
from sqlalchemy.orm import Session

from db.database import Base

# Saison, saison_courante_id, saison_par_defaut, portee : importés dans les
# fonctions, pas ici — ce module est chargé par db/__init__.py, et
# saisons/models.py importe lui-même db (import circulaire sinon).


@event.listens_for(Base, "after_insert", propagate=True)
def _premiere_saison_d_une_ecole(mapper, connection, cible) -> None:
    if mapper.local_table.name != "ecoles":
        return
    from .models import Saison
    from .saisons import saison_par_defaut

    nom, debut, fin = saison_par_defaut()
    connection.execute(
        insert(Saison).values(ecole_id=cible.id, nom=nom, date_debut=debut, date_fin=fin)
    )


@event.listens_for(Session, "before_flush")
def _rattacher_puis_verifier(session: Session, flush_context, instances) -> None:
    from . import portee
    from .saisons import saison_courante_id

    demandee = portee.saison_demandee()
    courantes: dict[int, int | None] = {}
    with session.no_autoflush:
        for objet in session.new:
            if getattr(objet, "saison_id", 0) is not None:
                continue
            ecole_id = getattr(objet, "ecole_id", None)
            if ecole_id is None:
                continue
            if demandee is not None and not portee._desactive(session):
                objet.saison_id = demandee
                continue
            if ecole_id not in courantes:
                courantes[ecole_id] = saison_courante_id(session, ecole_id)
            objet.saison_id = courantes[ecole_id]
    portee.verifier_flush(session)
