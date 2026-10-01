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
    app.dependency_overrides[rbac.session_requise] = lambda: None
    yield
    app.dependency_overrides.pop(rbac.compte_appelant, None)
    app.dependency_overrides.pop(rbac.session_requise, None)


# --- Sessions réelles (tests `rbac_reel`, spec §2.2) ---

MOT_DE_PASSE = "motdepasse-de-test"
_HACHE = None


def entetes_session(compte, mot_de_passe: str = MOT_DE_PASSE) -> dict[str, str]:
    """En-têtes d'une vraie session ouverte sur ce profil : jeton signé +
    profil actif. Donne au besoin un email à la fiche et un mot de passe à
    cet email (hachage scrypt calculé une seule fois : il est lent exprès)."""
    global _HACHE
    from acces import Acces
    from auth import Auth
    from comptes import Comptes
    from securite import mots_de_passe
    from sqlalchemy.orm import object_session

    db = object_session(compte)
    if not compte.email:
        compte.email = f"compte{compte.id}@test.fr"
        db.commit()
    acces = Acces()
    utilisateur = acces.obtenir_ou_creer(db, compte.email)
    if utilisateur.hashed_password is None:
        if mot_de_passe == MOT_DE_PASSE:
            _HACHE = _HACHE or mots_de_passe.hacher(MOT_DE_PASSE)
            utilisateur.hashed_password = _HACHE
        else:
            utilisateur.hashed_password = mots_de_passe.hacher(mot_de_passe)
    db.commit()
    jeton = Auth(Comptes(), acces).ouvrir_session(db, compte)
    return {"X-Compte-Id": str(compte.id), "Authorization": f"Bearer {jeton}"}


def donner_mot_de_passe(db, email: str) -> None:
    """Donne à cette adresse le mot de passe de test (MOT_DE_PASSE)."""
    global _HACHE
    from acces import Acces
    from securite import mots_de_passe

    _HACHE = _HACHE or mots_de_passe.hacher(MOT_DE_PASSE)
    from acces.models import maintenant

    utilisateur = Acces().obtenir_ou_creer(db, email)
    utilisateur.hashed_password = _HACHE
    utilisateur.profil_finalise_le = maintenant()
    db.commit()


@pytest.fixture()
def mails(monkeypatch):
    """Les mails d'accès (invitation, réinitialisation) partent dans cette
    liste au lieu du SMTP : [(destinataire, sujet, corps)]."""
    from auth.mails import MailsAcces

    envoyes = []
    monkeypatch.setattr(MailsAcces, "_envoyer", lambda self, d, sujet, corps: envoyes.append((d, sujet, corps)))
    monkeypatch.setattr(MailsAcces, "disponible", True)
    return envoyes
