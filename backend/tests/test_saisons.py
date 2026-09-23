"""Tests des saisons, étape 1 : table, rattachement automatique et migration
(voir spec/SPEC.md §2.6 et §6.1bis)."""

import datetime as dt
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles
from messagerie import Conversations
from saisons import Saison, saison_courante_id, saison_par_defaut


def _ecole(db_session, nom="Contretemps"):
    return Ecoles().create(db_session, nom=nom, code_postal="83330")


def test_saison_par_defaut_de_septembre_a_fin_aout():
    assert saison_par_defaut(dt.date(2026, 9, 23)) == ("2026-2027", dt.date(2026, 9, 1), dt.date(2027, 8, 31))
    assert saison_par_defaut(dt.date(2027, 3, 1)) == ("2026-2027", dt.date(2026, 9, 1), dt.date(2027, 8, 31))
    assert saison_par_defaut(dt.date(2027, 8, 1))[0] == "2027-2028"


def test_une_nouvelle_ecole_recoit_sa_premiere_saison(db_session):
    ecole = _ecole(db_session)
    saisons = db_session.scalars(sa.select(Saison).where(Saison.ecole_id == ecole.id)).all()
    assert len(saisons) == 1
    assert saison_courante_id(db_session, ecole.id) == saisons[0].id


def test_les_nouvelles_donnees_vont_dans_la_saison_courante_de_leur_ecole(db_session):
    a = _ecole(db_session, "A")
    b = _ecole(db_session, "B")
    saison_a = saison_courante_id(db_session, a.id)

    compte = Comptes().create(db_session, ecole_id=a.id, role="admin", nom="Dho", prenom="Julia")
    cours = CoursService().create(db_session, ecole_id=a.id, nom="Jazz")
    conversation = Conversations(Comptes(), CoursService()).create_groupe(db_session, a.id, "Groupe", [])
    assert compte.saison_id == saison_a
    assert compte.famille.saison_id == saison_a
    assert cours.saison_id == saison_a
    assert conversation.saison_id == saison_a

    # Nouvelle saison pour A : elle devient la courante (la dernière créée),
    # B n'est pas concernée.
    nouvelle = Saison(ecole_id=a.id, nom="2027-2028", date_debut=dt.date(2027, 9, 1), date_fin=dt.date(2028, 8, 31))
    db_session.add(nouvelle)
    db_session.commit()
    assert saison_courante_id(db_session, a.id) == nouvelle.id
    assert CoursService().create(db_session, ecole_id=a.id, nom="Hip-hop").saison_id == nouvelle.id
    assert CoursService().create(db_session, ecole_id=b.id, nom="Salsa").saison_id == saison_courante_id(
        db_session, b.id
    )
    assert cours.saison_id == saison_a


# --- Migration Alembic (données existantes → saison 2026-2027) ---

BACKEND = Path(__file__).resolve().parents[1]


def test_migration_rattache_les_donnees_existantes_a_2026_2027(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'avant.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))

    command.upgrade(config, "b787f0a65803")
    moteur = sa.create_engine(url)
    with moteur.begin() as c:
        for ecole_id in (1, 2):
            c.execute(sa.text(
                "INSERT INTO ecoles (id, nom, code_postal, code_acces_admin, code_acces_prof,"
                " code_acces_eleve, sauvegarde_active, sauvegarde_periodicite, created_at)"
                f" VALUES ({ecole_id}, 'E{ecole_id}', '83000', 'A', 'P', 'E', 0, 'semaine',"
                " CURRENT_TIMESTAMP)"
            ))
            c.execute(sa.text("INSERT INTO familles (id, ecole_id, created_at)"
                f" VALUES ({ecole_id}, {ecole_id}, CURRENT_TIMESTAMP)"))
            c.execute(sa.text(
                "INSERT INTO comptes (id, ecole_id, famille_id, nom, prenom, created_at)"
                f" VALUES ({ecole_id}, {ecole_id}, {ecole_id}, 'N', 'P', CURRENT_TIMESTAMP)"
            ))
            c.execute(sa.text(f"INSERT INTO cours (id, ecole_id, nom) VALUES ({ecole_id}, {ecole_id}, 'C')"))
        # Superuser : sans école, doit rester sans saison.
        c.execute(sa.text("INSERT INTO comptes (id, nom, prenom, created_at) VALUES (9, 'S', 'U', CURRENT_TIMESTAMP)"))

    command.upgrade(config, "head")

    with moteur.connect() as c:
        saisons = c.execute(sa.text("SELECT id, ecole_id, nom, date_debut, date_fin FROM saisons")).all()
        assert {(e, n, d, f) for _, e, n, d, f in saisons} == {
            (1, "2026-2027", "2026-09-01", "2027-08-31"),
            (2, "2026-2027", "2026-09-01", "2027-08-31"),
        }
        saison_de = {ecole_id: id_ for id_, ecole_id, *_ in saisons}
        for table in ("familles", "cours"):
            lignes = dict(c.execute(sa.text(f"SELECT ecole_id, saison_id FROM {table}")).all())
            assert lignes == saison_de
        comptes = dict(c.execute(sa.text("SELECT id, saison_id FROM comptes")).all())
        assert comptes == {1: saison_de[1], 2: saison_de[2], 9: None}

    command.downgrade(config, "b787f0a65803")
    with moteur.connect() as c:
        assert "saisons" not in sa.inspect(c).get_table_names()
        assert "saison_id" not in [col["name"] for col in sa.inspect(c).get_columns("cours")]
