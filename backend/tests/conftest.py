"""Fixtures partagées : base isolée (SQLite mémoire, pas le fichier de
dev), via override de la dépendance get_db (pattern standard FastAPI).
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
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
