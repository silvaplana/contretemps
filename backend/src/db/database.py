"""Moteur SQLAlchemy et session partagés par tous les modules métier.

N'appartient à aucun module métier — comme `app/`, c'est de la plomberie
commune (voir backend/README.md et le pattern déjà en place dans
test-python). Chaque module importe `Base` pour déclarer ses tables
(`<module>/models.py`) et `get_db` pour obtenir une session dans ses routes.

DATABASE_URL (voir .env.example) :
- vide/absent -> SQLite local (fichier `contretemps.db`, zéro install,
  pratique en dev quand Postgres n'est pas disponible sur la machine)
- sinon -> l'URL fournie (Postgres en prod, voir spec/SPEC.md section 1)

Le code métier (models.py, receiver.py...) ne dépend jamais du moteur
utilisé : SQLAlchemy abstrait la différence, seule cette configuration
change.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./contretemps.db")

# SQLite a besoin de cette option en usage multi-thread (le serveur ASGI
# gère chaque requête dans son propre thread) ; Postgres n'en a pas besoin.
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Session:
    """Dépendance FastAPI : une session par requête, toujours refermée."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
