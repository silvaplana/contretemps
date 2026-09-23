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
from eleves import Eleves
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


# --- Étape 2 : filtre par saison affichée et verrou lecture seule ---

import pytest  # noqa: E402
from presence.models import SeancePresence  # noqa: E402
from saisons.portee import SaisonEnLectureSeule, toutes_saisons  # noqa: E402


def _deux_saisons(db_session):
    """École avec un cours et un élève en 2026-2027, puis une saison
    2027-2028 créée (devenue la courante, vide)."""
    ecole = _ecole(db_session)
    ancienne = saison_courante_id(db_session, ecole.id)
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Jazz")
    eleve, _ = Eleves(comptes=Comptes()).create(db_session, ecole_id=ecole.id, nom="Roux", prenom="Ana")
    nouvelle = Saison(ecole_id=ecole.id, nom="2027-2028", date_debut=dt.date(2027, 9, 1), date_fin=dt.date(2028, 8, 31))
    db_session.add(nouvelle)
    db_session.commit()
    return ecole, ancienne, nouvelle.id, cours, eleve


def test_par_defaut_on_ne_voit_que_la_saison_courante(client, db_session):
    ecole, ancienne, nouvelle, cours, eleve = _deux_saisons(db_session)
    assert client.get("/cours", params={"ecole_id": ecole.id}).json() == []
    assert client.get(f"/cours/{cours.id}").status_code == 404
    assert client.get("/eleves", params={"ecole_id": ecole.id}).json() == []

    nouveau = client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "Salsa"})
    assert nouveau.status_code == 201
    assert [c["nom"] for c in client.get("/cours", params={"ecole_id": ecole.id}).json()] == ["Salsa"]


def test_une_ancienne_saison_se_consulte_avec_l_entete(client, db_session):
    ecole, ancienne, nouvelle, cours, eleve = _deux_saisons(db_session)
    entete = {"X-Saison-Id": str(ancienne)}
    assert [c["nom"] for c in client.get("/cours", params={"ecole_id": ecole.id}, headers=entete).json()] == ["Jazz"]
    assert client.get(f"/cours/{cours.id}", headers=entete).status_code == 200
    assert [e["nom"] for e in client.get("/eleves", params={"ecole_id": ecole.id}, headers=entete).json()] == ["Roux"]


def test_une_ancienne_saison_est_en_lecture_seule(client, db_session):
    ecole, ancienne, nouvelle, cours, eleve = _deux_saisons(db_session)
    entete = {"X-Saison-Id": str(ancienne)}

    refus = client.put(f"/cours/{cours.id}", json={"nom": "Jazz 2"}, headers=entete)
    assert refus.status_code == 403
    assert "lecture seule" in refus.json()["detail"]
    assert client.post("/cours", params={"ecole_id": ecole.id}, json={"nom": "X"}, headers=entete).status_code == 403
    assert client.delete(f"/cours/{cours.id}", headers=entete).status_code == 403
    assert client.post(f"/cours/{cours.id}/seances", json={"date": "2027-01-10"}, headers=entete).status_code == 403
    assert client.post(f"/cours/{cours.id}/eleves/{eleve.id}", headers=entete).status_code == 403
    # Même sans l'en-tête (requête forgée), une ligne enfant d'un ancien
    # cours ne peut pas être créée.
    assert client.post(f"/cours/{cours.id}/seances", json={"date": "2027-01-10"}).status_code == 403

    with toutes_saisons(db_session):
        assert db_session.get(type(cours), cours.id).nom == "Jazz"


def test_le_verrou_s_applique_aussi_hors_des_routes(db_session):
    ecole, ancienne, nouvelle, cours, eleve = _deux_saisons(db_session)
    db_session.add(SeancePresence(cours_id=cours.id, date=dt.date(2027, 1, 10)))
    with pytest.raises(SaisonEnLectureSeule):
        db_session.commit()
    db_session.rollback()

    # Duplication, restauration... : toutes saisons autorisées.
    with toutes_saisons(db_session):
        db_session.add(SeancePresence(cours_id=cours.id, date=dt.date(2027, 1, 10)))
        db_session.commit()


# --- Étape 2 : connexion, bascule vers la nouvelle fiche, familles ---


def _saison_suivante(db_session, ecole):
    saison = Saison(ecole_id=ecole.id, nom="2027-2028", date_debut=dt.date(2027, 9, 1), date_fin=dt.date(2028, 8, 31))
    db_session.add(saison)
    db_session.commit()
    return saison


def _recopier(db_session, ancien, role):
    """Ce que fera la création de saison avec duplication (étape 3)."""
    nouveau = Comptes().create(
        db_session, ecole_id=ancien.ecole_id, role=role, nom=ancien.nom, prenom=ancien.prenom, email=ancien.email
    )
    nouveau.compte_precedent_id = ancien.id
    db_session.commit()
    return nouveau


@pytest.fixture()
def changement_de_saison(db_session):
    ecole = _ecole(db_session)
    comptes = Comptes()
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="j@x.fr")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Ana", email="r@x.fr")
    ancienne = saison_courante_id(db_session, ecole.id)
    _saison_suivante(db_session, ecole)
    nouvel_admin = _recopier(db_session, admin, "admin")
    nouveau_prof = _recopier(db_session, prof, "professeur")
    return {
        "ecole": ecole, "ancienne": ancienne, "admin": admin, "prof": prof, "eleve": eleve,
        "nouvel_admin": nouvel_admin, "nouveau_prof": nouveau_prof,
    }


def test_seules_les_fiches_de_la_saison_courante_se_connectent(client, changement_de_saison):
    c = changement_de_saison
    ecole = c["ecole"]
    admin = client.post("/auth/login", json={"ecole_id": ecole.id, "identifiant": "Julia Dho", "code": ecole.code_acces_admin})
    assert admin.status_code == 200 and admin.json()["id"] == c["nouvel_admin"].id
    eleve = client.post("/auth/login", json={"ecole_id": ecole.id, "identifiant": "Ana Roux", "code": ecole.code_acces_eleve})
    assert eleve.status_code == 401
    # L'en-tête de saison est ignoré à la connexion.
    forge = client.post(
        "/auth/login",
        json={"ecole_id": ecole.id, "identifiant": "Ana Roux", "code": ecole.code_acces_eleve},
        headers={"X-Saison-Id": str(c["ancienne"])},
    )
    assert forge.status_code == 401


def test_fiche_courante(client, changement_de_saison):
    c = changement_de_saison
    assert client.get(f"/comptes/{c['admin'].id}/fiche-courante").json() == {"compte_id": c["nouvel_admin"].id}
    assert client.get(f"/comptes/{c['nouvel_admin'].id}/fiche-courante").json() == {"compte_id": c["nouvel_admin"].id}
    assert client.get(f"/comptes/{c['eleve'].id}/fiche-courante").status_code == 404


@pytest.mark.rbac_reel
def test_une_ancienne_fiche_bascule_ou_est_refusee(client, changement_de_saison):
    c = changement_de_saison
    route = f"/ecoles/{c['ecole'].id}"
    bascule = client.get(route, headers={"X-Compte-Id": str(c["admin"].id)})
    assert bascule.status_code == 409
    assert bascule.json()["detail"] == {"code": "nouvelle_saison", "compte_id": c["nouvel_admin"].id}
    refus = client.get(route, headers={"X-Compte-Id": str(c["eleve"].id)})
    assert refus.status_code == 401
    assert refus.json()["detail"]["code"] == "hors_saison"
    assert client.get(route, headers={"X-Compte-Id": str(c["nouvel_admin"].id)}).status_code == 200


@pytest.mark.rbac_reel
def test_seul_un_admin_consulte_une_ancienne_saison(client, changement_de_saison):
    c = changement_de_saison
    ancienne = {"X-Saison-Id": str(c["ancienne"])}
    admin = client.get(
        f"/ecoles/{c['ecole'].id}/administrateurs",
        headers={"X-Compte-Id": str(c["nouvel_admin"].id), **ancienne},
    )
    assert admin.status_code == 200
    assert [a["id"] for a in admin.json()] == [c["admin"].id]
    prof = client.get(
        f"/ecoles/{c['ecole'].id}", headers={"X-Compte-Id": str(c["nouveau_prof"].id), **ancienne}
    )
    assert prof.status_code == 403


def test_les_familles_ne_traversent_pas_les_saisons(db_session, changement_de_saison):
    c = changement_de_saison
    # Même email qu'une fiche de l'ancienne saison : nouvelle famille.
    frere = Comptes().create(db_session, ecole_id=c["ecole"].id, role="eleve", nom="Roux", prenom="Léo", email="r@x.fr")
    assert frere.famille_id != c["eleve"].famille_id
    # Même email qu'une fiche de la saison courante : même famille.
    assert c["nouvel_admin"].famille_id != c["admin"].famille_id
    enfant = Comptes().create(db_session, ecole_id=c["ecole"].id, role="eleve", nom="Dho", prenom="Tom", email="j@x.fr")
    assert enfant.famille_id == c["nouvel_admin"].famille_id


# --- Étape 2 : sauvegarde technique de toutes les saisons ---


def test_sauvegarde_technique_couvre_toutes_les_saisons(client, db_session, changement_de_saison):
    from cours.models import Cours

    c = changement_de_saison
    ecole_id = c["ecole"].id
    ancien_cours = CoursService().create(db_session, ecole_id=ecole_id, nom="Salsa")  # saison courante
    with toutes_saisons(db_session):
        vieux = Cours(ecole_id=ecole_id, saison_id=c["ancienne"], nom="Jazz", ordre=0)
        db_session.add(vieux)
        db_session.commit()
        vieux_id = vieux.id

    sauvegarde = client.get(f"/ecoles/{ecole_id}/export-technique").content
    assert client.delete(f"/ecoles/{ecole_id}/donnees").status_code == 204
    with toutes_saisons(db_session):
        # Seule la saison courante reste, vide.
        assert db_session.scalars(sa.select(Saison.nom).where(Saison.ecole_id == ecole_id)).all() == ["2027-2028"]
        assert db_session.query(Cours).filter(Cours.ecole_id == ecole_id).count() == 0

    reponse = client.post(
        f"/ecoles/{ecole_id}/restaurer",
        files={"fichier": ("b.xlsx", sauvegarde, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert reponse.status_code == 204
    db_session.expire_all()
    with toutes_saisons(db_session):
        saisons = dict(db_session.execute(sa.select(Saison.id, Saison.nom).where(Saison.ecole_id == ecole_id)).all())
        assert sorted(saisons.values()) == ["2026-2027", "2027-2028"]
        cours = {x.nom: x.saison_id for x in db_session.query(Cours).filter(Cours.ecole_id == ecole_id)}
        assert cours == {"Jazz": c["ancienne"], "Salsa": ancien_cours.saison_id}
        assert db_session.get(Cours, vieux_id).nom == "Jazz"
        nouvel_admin = db_session.get(type(c["nouvel_admin"]), c["nouvel_admin"].id)
        assert nouvel_admin.compte_precedent_id == c["admin"].id
