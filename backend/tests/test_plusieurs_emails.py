"""Plusieurs emails par fiche (spec §2.1, §6.2, §6.3, décision du
2026-10-16) : le cas réel de Margot et Lison Béraud, saisies avec l'email
de leur père (qui n'a pas de fiche), Margot ayant ensuite donné le sien."""

import pytest
from acces import Acces
from comptes import Comptes
from conftest import MOT_DE_PASSE, donner_mot_de_passe
from ecoles import Ecoles
from securite import mots_de_passe

PERE = "pere.beraud@x.fr"
MARGOT = "margot@x.fr"
MOT_DE_PASSE_MARGOT = "celui-de-margot"


@pytest.fixture()
def beraud(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    lison = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Béraud", prenom="Lison", email=PERE)
    margot = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Béraud", prenom="Margot", email=PERE)
    autre = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Ana", email="ana@x.fr")
    comptes.update(db_session, margot.id, emails=[PERE, MARGOT])
    donner_mot_de_passe(db_session, PERE)
    acces = Acces().obtenir_ou_creer(db_session, MARGOT)
    acces.mot_de_passe_hache = mots_de_passe.hacher(MOT_DE_PASSE_MARGOT)
    db_session.commit()
    return {"ecole": ecole, "lison": lison, "margot": margot, "autre": autre}


def _login(client, identifiant, mot_de_passe):
    return client.post("/auth/login", json={"identifiant": identifiant, "mot_de_passe": mot_de_passe})


def _entetes(session):
    return {"Authorization": f"Bearer {session['jeton']}", "X-Compte-Id": str(session["compte"]["id"])}


def test_separer_et_normaliser():
    from comptes import separer_emails

    assert separer_emails("A@x.fr; b@x.fr , a@x.fr  c@x.fr") == ["a@x.fr", "b@x.fr", "c@x.fr"]
    assert separer_emails(["B@x.fr", "b@x.fr"]) == ["b@x.fr"]
    assert separer_emails(None) == [] and separer_emails("") == []


def test_la_famille_est_reliee_par_l_email_commun(db_session, beraud):
    db_session.refresh(beraud["lison"])
    db_session.refresh(beraud["margot"])
    assert beraud["margot"].emails == [PERE, MARGOT]
    assert beraud["margot"].famille_id == beraud["lison"].famille_id
    assert beraud["autre"].famille_id != beraud["lison"].famille_id


def test_la_famille_suit_l_email_du_payeur(db_session, beraud):
    """Spec core.md §4.4 : famille = même email du payeur ; vide = le premier
    email de la fiche."""
    comptes = Comptes()
    comptes.update(db_session, beraud["margot"].id, email=MARGOT)
    db_session.refresh(beraud["lison"])
    assert beraud["margot"].famille_id != beraud["lison"].famille_id
    # Son père paie : elle revient dans la famille, avec seulement son email.
    comptes.update(db_session, beraud["margot"].id, payer_email=" Pere.Beraud@x.fr ")
    db_session.refresh(beraud["lison"])
    assert beraud["margot"].payer_email == PERE
    assert beraud["margot"].famille_id == beraud["lison"].famille_id
    with pytest.raises(ValueError):
        comptes.update(db_session, beraud["margot"].id, payer_email=f"{PERE}; {MARGOT}")


def test_un_email_en_commun_ne_suffit_plus(db_session):
    """Avant : de proche en proche par n'importe quel email commun. Une fiche
    avec deux emails est de la famille de son premier (ou de son payeur)."""
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="E", code_postal="83000")
    a = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="A", prenom="A", email="a@x.fr")
    b = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="B", prenom="B", email="b@x.fr")
    deux = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="P", prenom="P", email="a@x.fr, b@x.fr")
    assert a.famille_id == deux.famille_id != b.famille_id


def test_la_reprise_garde_les_memes_familles(db_session):
    """Migration de l'étape 5 : chaque famille d'avant reçoit l'email que
    portent le plus de ses fiches."""
    from comptes.reprise_payeurs import reprendre_payeurs
    from sqlalchemy import update

    from comptes.models import Compte

    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="E", code_postal="83000")
    margot = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="B", prenom="Margot", email=f"{MARGOT}, {PERE}")
    lison = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="B", prenom="Lison", email=PERE)
    zoe = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="B", prenom="Zoé", email=PERE)
    seule = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="R", prenom="Ana", email="ana@x.fr")
    # Comme avant l'étape 5 : les trois sœurs dans une même famille.
    db_session.execute(update(Compte).where(Compte.id.in_([margot.id, zoe.id])).values(famille_id=lison.famille_id))
    db_session.commit()

    assert reprendre_payeurs(db_session.connection()) == 3
    db_session.commit()
    db_session.expire_all()
    assert [c.payer_email for c in (margot, lison, zoe, seule)] == [PERE, PERE, PERE, None]
    comptes.recalculer_familles(db_session, ecole.id)
    assert margot.famille_id == lison.famille_id == zoe.famille_id != seule.famille_id


@pytest.mark.rbac_reel
def test_chacun_se_connecte_avec_son_email(client, beraud):
    par_margot = _login(client, MARGOT, MOT_DE_PASSE_MARGOT)
    assert par_margot.status_code == 200
    assert par_margot.json()["compte"]["id"] == beraud["margot"].id
    assert _login(client, MARGOT, MOT_DE_PASSE).status_code == 401
    # Par le nom : le mot de passe de l'une ou l'autre de ses adresses.
    assert _login(client, "Margot Béraud", MOT_DE_PASSE_MARGOT).json()["compte"]["id"] == beraud["margot"].id
    assert _login(client, "Margot Béraud", MOT_DE_PASSE).json()["compte"]["id"] == beraud["margot"].id


@pytest.mark.rbac_reel
def test_le_selecteur_montre_les_profils_de_l_email_connecte(client, beraud):
    margot = _login(client, MARGOT, MOT_DE_PASSE_MARGOT).json()
    vus = client.get(f"/comptes/{beraud['margot'].id}/famille", headers=_entetes(margot)).json()
    assert [c["id"] for c in vus] == [beraud["margot"].id]

    pere = _login(client, "Lison Béraud", MOT_DE_PASSE).json()
    vus = client.get(f"/comptes/{beraud['lison'].id}/famille", headers=_entetes(pere)).json()
    assert sorted(c["id"] for c in vus) == sorted([beraud["lison"].id, beraud["margot"].id])


@pytest.mark.rbac_reel
def test_avec_son_email_margot_n_entre_pas_chez_sa_soeur(client, beraud):
    margot = _login(client, MARGOT, MOT_DE_PASSE_MARGOT).json()
    vers_lison = client.post(
        "/auth/bascule", json={"vers_compte_id": beraud["lison"].id}, headers=_entetes(margot)
    )
    assert vers_lison.status_code == 401
    assert vers_lison.json()["detail"] == "Mot de passe incorrect"
    entetes = {**_entetes(margot), "X-Compte-Id": str(beraud["lison"].id)}
    assert client.get(f"/comptes/{beraud['lison'].id}/famille", headers=entetes).status_code == 401
    # Avec l'email du père, on bascule de l'une à l'autre.
    pere = _login(client, PERE, MOT_DE_PASSE).json()
    vers_margot = client.post(
        "/auth/bascule", json={"vers_compte_id": beraud["margot"].id}, headers=_entetes(pere)
    )
    assert vers_margot.status_code == 200


@pytest.mark.rbac_reel
def test_statut_d_acces_par_adresse(client, db_session, beraud):
    from conftest import entetes_session

    admin = Comptes().create(db_session, ecole_id=beraud["ecole"].id, role="admin", nom="Dho", prenom="Julia", email="j@x.fr")
    statuts = client.get(f"/ecoles/{beraud['ecole'].id}/acces", headers=entetes_session(admin)).json()
    margot = statuts[str(beraud["margot"].id)]
    assert [a["email"] for a in margot["adresses"]] == [PERE, MARGOT]
    assert statuts[str(beraud["lison"].id)]["adresses"] == []


@pytest.mark.rbac_reel
def test_inviter_une_seule_adresse_de_la_fiche(client, db_session, beraud, mails):
    from conftest import entetes_session

    admin = Comptes().create(db_session, ecole_id=beraud["ecole"].id, role="admin", nom="Dho", prenom="Julia", email="j@x.fr")
    reponse = client.post(
        f"/ecoles/{beraud['ecole'].id}/invitations",
        json={"compte_ids": [beraud["margot"].id], "email": MARGOT},
        headers=entetes_session(admin),
    )
    assert reponse.status_code == 200, reponse.text
    assert [m[0] for m in mails] == [MARGOT]


def test_migration_reprend_les_emails(tmp_path, monkeypatch):
    from pathlib import Path

    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / 'avant.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(config, "d4b6f8a0c2e1")
    moteur = sa.create_engine(url)
    with moteur.begin() as c:
        c.execute(sa.text("INSERT INTO ecoles (id, nom, code_postal, sous_domaine, sauvegarde_active, sauvegarde_periodicite, created_at)"
                          " VALUES (1, 'E', '83000', 'e', 0, 'semaine', CURRENT_TIMESTAMP)"))
        c.execute(sa.text("INSERT INTO saisons (id, ecole_id, nom, date_debut, date_fin)"
                          " VALUES (1, 1, 'S', '2026-09-01', '2027-08-31')"))
        c.execute(sa.text("INSERT INTO familles (id, ecole_id, saison_id, created_at) VALUES (1, 1, 1, CURRENT_TIMESTAMP)"))
        for i, email in ((5, "Pere@X.fr"), (6, "a@x.fr; b@x.fr"), (7, None)):
            c.execute(sa.text(
                "INSERT INTO comptes (id, ecole_id, famille_id, saison_id, nom, prenom, email, created_at)"
                " VALUES (:i, 1, 1, 1, 'N', 'P', :e, CURRENT_TIMESTAMP)"
            ), {"i": i, "e": email})

    command.upgrade(config, "head")
    with moteur.connect() as c:
        lignes = c.execute(sa.text("SELECT compte_id, email FROM emails_compte ORDER BY id")).all()
        assert lignes == [(5, "pere@x.fr"), (6, "a@x.fr"), (6, "b@x.fr")]
    command.downgrade(config, "d4b6f8a0c2e1")
    moteur.dispose()


def test_filet_de_securite_au_demarrage(tmp_path):
    """Sans la migration, les anciennes adresses sont reprises au démarrage."""
    import sqlalchemy as sa
    from comptes.reprise_emails import reprendre_anciens_emails

    moteur = sa.create_engine(f"sqlite:///{tmp_path / 'b.db'}")
    with moteur.begin() as c:
        c.execute(sa.text("CREATE TABLE comptes (id INTEGER PRIMARY KEY, email TEXT, created_at DATETIME)"))
        c.execute(sa.text("CREATE TABLE emails_compte (id INTEGER PRIMARY KEY, compte_id INT, email TEXT, created_at DATETIME)"))
        c.execute(sa.text("INSERT INTO comptes VALUES (1, 'A@x.fr', NULL), (2, NULL, NULL)"))
    reprendre_anciens_emails(moteur)
    reprendre_anciens_emails(moteur)  # une seule fois
    with moteur.connect() as c:
        assert c.execute(sa.text("SELECT compte_id, email FROM emails_compte")).all() == [(1, "a@x.fr")]
    moteur.dispose()


@pytest.mark.rbac_reel
def test_une_ancienne_sauvegarde_garde_les_familles(client, db_session, beraud):
    """Sauvegarde d'avant l'email du payeur : la reprise est refaite."""
    import io

    from conftest import entetes_session
    from openpyxl import load_workbook

    from comptes.models import Compte

    ecole_id = beraud["ecole"].id
    admin = Comptes().create(db_session, ecole_id=ecole_id, role="admin", nom="Dho", prenom="Julia")
    # Margot a mis son email en premier : seul l'email du payeur la garde avec Lison.
    Comptes().update(db_session, beraud["margot"].id, emails=[MARGOT, PERE], payer_email=PERE)
    entetes = entetes_session(admin)
    classeur = load_workbook(io.BytesIO(client.get(f"/ecoles/{ecole_id}/export-technique", headers=entetes).content))
    feuille = classeur["Comptes"]
    colonne = [c.value for c in feuille[1]].index("payer_email") + 1
    feuille.delete_cols(colonne)
    sortie = io.BytesIO()
    classeur.save(sortie)
    xlsx = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    reponse = client.post(f"/ecoles/{ecole_id}/restaurer", files={"fichier": ("b.xlsx", sortie.getvalue(), xlsx)}, headers=entetes)

    assert reponse.status_code == 204, reponse.text
    db_session.expire_all()
    margot, lison = db_session.get(Compte, beraud["margot"].id), db_session.get(Compte, beraud["lison"].id)
    assert margot.payer_email == lison.payer_email == PERE
    Comptes().recalculer_familles(db_session, ecole_id)
    assert margot.famille_id == lison.famille_id
