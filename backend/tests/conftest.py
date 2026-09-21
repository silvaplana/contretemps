"""Fixtures partagées : base isolée (SQLite mémoire, pas le fichier de
dev), via override de la dépendance get_db (pattern standard FastAPI).
"""

import os

# Secret de signature des jetons Superuser fixé pour les tests : sans ça,
# securite/jetons.py en générerait un dans un FICHIER à côté de la base
# de dev (voir _chemin_fichier_secret). Avant tout import de l'appli.
os.environ.setdefault("SECRET_JETONS", "secret-des-tests-uniquement")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app.main import app  # noqa: E402
from comptes import rbac  # noqa: E402
from db import Base, get_db  # noqa: E402
from securite import limiteur  # noqa: E402


@pytest.fixture()
def db_session():
    # StaticPool : une seule connexion partagée par toutes les sessions —
    # sinon chaque connexion SQLite ":memory:" est une base à part, vide.
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    # Une session ouverte tout au long du test, pour que les fixtures de
    # test (ex. créer une école + un compte avant d'appeler l'API) voient
    # les mêmes données que les routes appelées via `client`.
    session = TestingSessionLocal()
    yield session
    session.close()
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


@pytest.fixture(autouse=True)
def _droits_neutralises(request, monkeypatch):
    """RBAC (comptes/rbac.py, spec §2.4) neutralisé par défaut : la plupart
    des tests portent sur autre chose que les droits (créer un cours,
    importer des élèves...) et n'ont pas à fabriquer un admin appelant.
    Les tests marqués `@pytest.mark.rbac_reel` gardent les vraies
    vérifications — voir tests/test_rbac.py, qui teste chaque refus."""
    # Compteurs d'essais du Superuser (en mémoire, voir securite/limiteur.py) :
    # repartir de zéro à chaque test.
    limiteur.reinitialiser()
    if request.node.get_closest_marker("rbac_reel"):
        yield
        return
    monkeypatch.setattr(rbac, "require_admin", lambda appelant, ecole_id: None)
    monkeypatch.setattr(rbac, "require_owner", lambda appelant, ecole_id: None)
    monkeypatch.setattr(rbac, "require_superuser", lambda appelant: None)
    app.dependency_overrides[rbac.compte_appelant] = lambda: None
    yield
    app.dependency_overrides.pop(rbac.compte_appelant, None)
