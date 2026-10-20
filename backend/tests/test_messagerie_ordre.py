"""Conversation list ordered like WhatsApp (spec/modules/messagerie-instantanee.md
§4.8): a conversation with no message yet ranks by its creation date."""

from comptes import Comptes
from ecoles import Ecoles


def test_conversation_donne_sa_date_de_creation(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    prof = Comptes().create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    conv = client.post(
        "/conversations",
        params={"ecole_id": ecole.id},
        json={"nom": "Trésorier", "membres": [{"membre_type": "compte", "membre_id": prof.id}]},
    ).json()
    assert conv["created_at"]
    liste = client.get("/conversations", params={"ecole_id": ecole.id, "compte_id": prof.id}).json()
    assert liste[0]["created_at"] == conv["created_at"]


def test_migration_passe_si_la_colonne_existe_deja(tmp_path, monkeypatch):
    # create_all runs before `alembic upgrade head` in deploy.sh: on a fresh
    # base the column may already be there when the migration runs.
    from pathlib import Path

    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / 'deja.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))

    command.upgrade(config, "2b7d9e1f3a5c")
    with sa.create_engine(url).begin() as connexion:
        connexion.execute(sa.text("ALTER TABLE conversations ADD COLUMN created_at DATETIME"))
    command.upgrade(config, "head")
    colonnes = {c["name"] for c in sa.inspect(sa.create_engine(url)).get_columns("conversations")}
    assert "created_at" in colonnes
