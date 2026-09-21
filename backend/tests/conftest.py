"""Fixtures partagées : base isolée (SQLite mémoire, pas le fichier de
dev), via override de la dépendance get_db (pattern standard FastAPI).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from comptes import rbac
from db import Base, get_db


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
    if request.node.get_closest_marker("rbac_reel"):
        yield
        return
    monkeypatch.setattr(rbac, "require_admin", lambda appelant, ecole_id: None)
    monkeypatch.setattr(rbac, "require_owner", lambda appelant, ecole_id: None)
    app.dependency_overrides[rbac.compte_appelant] = lambda: None
    yield
    app.dependency_overrides.pop(rbac.compte_appelant, None)
