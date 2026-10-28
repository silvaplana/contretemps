"""Saison courante choisie par ses dates, saison passée créée après coup et
ancienne saison ouverte aux modifications (voir spec/SPEC.md §2.6)."""

import pytest
from conftest import entetes_session
from cours.models import Cours
from inscriptions.email_envoi import EmailEnvoi
from saisons import Saison, saison_courante_id
from saisons import portee
from saisons.portee import SaisonEnLectureSeule

PASSEE = {"nom": "2025-2026", "date_debut": "2025-09-01", "date_fin": "2026-08-31"}


@pytest.fixture()
def ecole(db_session):
    from comptes import Comptes, RoleCompte, roles
    from ecoles import Ecoles

    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="j@x.fr")
    admin = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    admin.roles.append(RoleCompte(role=roles.ADMIN))
    db_session.commit()
    return {"ecole": ecole, "courante": saison_courante_id(db_session, ecole.id), "owner": owner, "admin": admin}


def _creer_passee(client, ecole_id, **autres):
    return client.post(f"/ecoles/{ecole_id}/saisons", json={**PASSEE, **autres})


def test_une_saison_passee_creee_apres_ne_devient_pas_courante(client, db_session, ecole):
    ecole_id = ecole["ecole"].id
    reponse = _creer_passee(client, ecole_id, dupliquer_profs=True, dupliquer_cours=True, dupliquer_eleves=True)
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["saison"]["courante"] is False
    assert corps["saison"]["ouverte"] is True
    # Rien n'est recopié, l'admin garde sa fiche.
    assert corps["compte_id"] is None
    assert saison_courante_id(db_session, ecole_id) == ecole["courante"]
    assert [s["nom"] for s in client.get(f"/ecoles/{ecole_id}/saisons").json()] == ["2026-2027", "2025-2026"]


def test_des_dates_qui_chevauchent_une_saison_sont_refusees(client, ecole):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/saisons",
        json={"nom": "Bis", "date_debut": "2026-01-01", "date_fin": "2026-12-31"},
    )
    assert reponse.status_code == 409
    assert "2026-2027" in reponse.json()["detail"]


def test_on_ecrit_dans_une_saison_ouverte_pas_dans_une_fermee(client, db_session, ecole):
    ecole_id = ecole["ecole"].id
    passee_id = _creer_passee(client, ecole_id).json()["saison"]["id"]
    db_session.add(Cours(ecole_id=ecole_id, saison_id=passee_id, nom="Jazz"))
    db_session.commit()

    assert client.put(f"/ecoles/{ecole_id}/saisons/{passee_id}/ouverture", json={"ouverte": False}).status_code == 200
    db_session.add(Cours(ecole_id=ecole_id, saison_id=passee_id, nom="Salsa"))
    with pytest.raises(SaisonEnLectureSeule):
        db_session.commit()
    db_session.rollback()


def test_la_saison_courante_ne_s_ouvre_ni_ne_se_ferme(client, ecole):
    ecole_id = ecole["ecole"].id
    reponse = client.put(f"/ecoles/{ecole_id}/saisons/{ecole['courante']}/ouverture", json={"ouverte": False})
    assert reponse.status_code == 409


@pytest.mark.rbac_reel
def test_seuls_l_administrateur_principal_et_le_super_user_ouvrent_une_saison(client, ecole):
    ecole_id = ecole["ecole"].id
    reponse = client.post(f"/ecoles/{ecole_id}/saisons", json=PASSEE, headers=entetes_session(ecole["owner"]))
    passee_id = reponse.json()["saison"]["id"]
    url = f"/ecoles/{ecole_id}/saisons/{passee_id}/ouverture"
    assert client.put(url, json={"ouverte": False}, headers=entetes_session(ecole["admin"])).status_code == 403
    reponse = client.put(url, json={"ouverte": False}, headers=entetes_session(ecole["owner"]))
    assert reponse.status_code == 200
    assert reponse.json()["ouverte"] is False


def test_editer_une_saison_ouverte(client, ecole):
    ecole_id = ecole["ecole"].id
    passee_id = _creer_passee(client, ecole_id).json()["saison"]["id"]
    url = f"/ecoles/{ecole_id}/saisons/{passee_id}"
    modif = {"nom": "Saison 25/26", "date_debut": "2025-08-25", "date_fin": "2026-07-14"}
    reponse = client.put(url, json=modif)
    assert reponse.status_code == 200
    assert reponse.json()["nom"] == "Saison 25/26" and reponse.json()["courante"] is False
    # Elle ne peut pas passer après la saison en cours.
    apres = {"nom": "Saison 25/26", "date_debut": "2027-09-01", "date_fin": "2028-08-31"}
    assert client.put(url, json=apres).status_code == 409
    # Refermée, elle ne se modifie plus.
    client.put(f"{url}/ouverture", json={"ouverte": False})
    assert client.put(url, json=modif).status_code == 409


def test_aucun_mail_dans_une_ancienne_saison(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.exemple.fr")
    monkeypatch.setenv("SMTP_USER", "u")
    monkeypatch.setenv("SMTP_PASSWORD", "p")

    def interdit(*args, **kwargs):
        raise AssertionError("aucun mail ne doit partir")

    monkeypatch.setattr("inscriptions.email_envoi.smtplib.SMTP", interdit)
    jeton = portee._saison_demandee.set({"id": 1})
    try:
        portee.marquer_ancienne_saison()
        EmailEnvoi().envoyer_confirmation("a@x.fr", "Sujet", "Corps", [])
    finally:
        portee._saison_demandee.reset(jeton)


def test_la_courante_est_celle_qui_commence_le_plus_tard(db_session, ecole):
    import datetime as dt

    ecole_id = ecole["ecole"].id
    passee = Saison(
        ecole_id=ecole_id, nom="2024-2025", date_debut=dt.date(2024, 9, 1), date_fin=dt.date(2025, 8, 31)
    )
    db_session.add(passee)
    db_session.commit()
    assert passee.id > ecole["courante"]
    assert saison_courante_id(db_session, ecole_id) == ecole["courante"]
