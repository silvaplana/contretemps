"""Tarifs de la saison : les formules (spec/core.md §9.1, étape 7a), les
options et codes promo (§9.2, étape 7b)."""

import pytest
from comptes import Comptes
from conftest import entetes_session
from ecoles import Ecoles
from saisons import saison_courante_id

NOUVELLE = {"nom": "2027-2028", "date_debut": "2027-09-01", "date_fin": "2028-08-31"}
EN_3_FOIS = {
    "name": "Adhésion + 1 cours, en 3 fois", "price": 41500,
    "installments": [
        {"due_on": None, "amount": 13834}, {"due_on": "2027-12-15", "amount": 13833},
        {"due_on": "2028-03-15", "amount": 13833},
    ],
}


@pytest.fixture()
def ecole(db_session):
    return Ecoles().create(db_session, nom="Contretemps", code_postal="83330")


def _formules(client, ecole_id, **entetes):
    return client.get(f"/ecoles/{ecole_id}/tarifs", headers=entetes).json()


def test_creer_modifier_dupliquer_retirer(client, ecole):
    une_fois = client.post(f"/ecoles/{ecole.id}/tarifs/formules", json={"name": "En 1 fois", "price": 41500})
    assert une_fois.status_code == 201
    # Sans échéance : une seule, « À l'inscription », du montant du tarif.
    assert une_fois.json()["installments"] == [{"due_on": None, "amount": 41500}]
    trois = client.post(f"/ecoles/{ecole.id}/tarifs/formules", json=EN_3_FOIS).json()
    assert [i["amount"] for i in trois["installments"]] == [13834, 13833, 13833]

    faux = {**EN_3_FOIS, "price": 40000}
    reponse = client.put(f"/tarifs/formules/{trois['id']}", json=faux)
    assert reponse.status_code == 422 and "échéances" in reponse.json()["detail"]
    assert client.put(f"/tarifs/formules/{trois['id']}", json={**EN_3_FOIS, "active": False}).json()["active"] is False

    copie = client.post(f"/tarifs/formules/{une_fois.json()['id']}/dupliquer").json()
    assert [f["name"] for f in _formules(client, ecole.id)["plans"]] == [
        "En 1 fois", "En 1 fois (copie)", "Adhésion + 1 cours, en 3 fois",
    ]
    assert client.delete(f"/tarifs/formules/{copie['id']}").status_code == 204
    assert len(_formules(client, ecole.id)["plans"]) == 2


def test_la_creation_de_saison_recopie_les_formules(client, db_session, ecole):
    client.post(f"/ecoles/{ecole.id}/tarifs/formules", json=EN_3_FOIS)
    ancienne = saison_courante_id(db_session, ecole.id)
    client.post(f"/ecoles/{ecole.id}/saisons", json=NOUVELLE)
    formule = _formules(client, ecole.id)["plans"][0]
    # Échéances datées décalées d'un an.
    assert [i["due_on"] for i in formule["installments"]] == [None, "2028-12-15", "2029-03-15"]
    # L'ancienne saison se lit, mais ne se modifie plus.
    vieille = _formules(client, ecole.id, **{"X-Saison-Id": str(ancienne)})
    assert vieille["read_only"] is True
    assert client.put(f"/tarifs/formules/{vieille['plans'][0]['id']}", json=EN_3_FOIS).status_code == 403


def test_reprendre_ceux_de_la_saison_precedente(client, db_session, ecole):
    from plans import plans as p

    p.create(db_session, ecole.id, saison_courante_id(db_session, ecole.id), "Solo", 29000)
    db_session.commit()
    # Une saison créée avant les tarifs : vide, « Reprendre » est proposé.
    client.post(f"/ecoles/{ecole.id}/saisons", json=NOUVELLE)
    for plan in _formules(client, ecole.id)["plans"]:
        client.delete(f"/tarifs/formules/{plan['id']}")
    assert _formules(client, ecole.id)["previous"] == {"name": "2026-2027", "plans": 1, "adjustments": 0}
    repris = client.post(f"/ecoles/{ecole.id}/tarifs/reprendre")
    assert [f["name"] for f in repris.json()["plans"]] == ["Solo"]
    assert _formules(client, ecole.id)["previous"] is None
    assert client.post(f"/ecoles/{ecole.id}/tarifs/reprendre").status_code == 409


def test_options_et_codes_promo(client, ecole):
    solo = client.post(f"/ecoles/{ecole.id}/tarifs/formules", json={"name": "Solo", "price": 29000}).json()
    tshirt = client.post(
        f"/ecoles/{ecole.id}/tarifs/options", json={"name": "T-shirt", "amount": 1500, "quantity": 30}
    )
    assert tshirt.status_code == 201
    assert tshirt.json() | {"id": 0} == {
        "id": 0, "name": "T-shirt", "amount": 1500, "unit": "eur", "mode": "check", "code": None, "shown": False,
        "max_uses": None, "until": None, "quantity": 30, "active": True, "position": 1, "plan_ids": [],
    }
    code = {"name": "Rentrée", "amount": -1000, "unit": "pct", "mode": "code", "code": " rentree27 ",
            "max_uses": 50, "until": "2027-09-30", "quantity": 5, "plan_ids": [solo["id"]]}
    promo = client.post(f"/ecoles/{ecole.id}/tarifs/options", json=code).json()
    # Code en majuscules ; la quantité ne vaut que pour une option à cocher.
    assert (promo["code"], promo["quantity"], promo["plan_ids"]) == ("RENTREE27", None, [solo["id"]])

    erreurs = [
        {**code, "code": "Rentree27"},  # même code
        {**code, "code": ""},
        {**code, "amount": -10100},  # plus de 100 %
        {**code, "amount": 0},
        {**code, "plan_ids": [9999]},
    ]
    for faux in erreurs:
        assert client.post(f"/ecoles/{ecole.id}/tarifs/options", json=faux).status_code == 422
    # Le même code reste à lui-même.
    assert client.put(f"/tarifs/options/{promo['id']}", json={**code, "shown": True}).json()["shown"] is True

    # Retirer la formule la retire de l'option, qui vaut alors pour toutes.
    client.delete(f"/tarifs/formules/{solo['id']}")
    options = _formules(client, ecole.id)["adjustments"]
    assert [(o["name"], o["plan_ids"]) for o in options] == [("T-shirt", []), ("Rentrée", [])]
    assert client.delete(f"/tarifs/options/{tshirt.json()['id']}").status_code == 204
    assert [o["name"] for o in _formules(client, ecole.id)["adjustments"]] == ["Rentrée"]


def test_la_creation_de_saison_recopie_les_options(client, db_session, ecole):
    solo = client.post(f"/ecoles/{ecole.id}/tarifs/formules", json={"name": "Solo", "price": 29000}).json()
    client.post(f"/ecoles/{ecole.id}/tarifs/options", json={
        "name": "Rentrée", "amount": -2000, "mode": "code", "code": "RENTREE", "until": "2027-09-30",
        "plan_ids": [solo["id"]],
    })
    ancienne = saison_courante_id(db_session, ecole.id)
    client.post(f"/ecoles/{ecole.id}/saisons", json=NOUVELLE)
    tarifs = _formules(client, ecole.id)
    option = tarifs["adjustments"][0]
    # Reliée à la copie de la formule ; date limite décalée d'un an.
    assert (option["plan_ids"], option["until"]) == ([tarifs["plans"][0]["id"]], "2028-09-30")
    vieille = _formules(client, ecole.id, **{"X-Saison-Id": str(ancienne)})["adjustments"][0]
    assert client.delete(f"/tarifs/options/{vieille['id']}").status_code == 403


@pytest.mark.rbac_reel
def test_reserve_aux_admins_de_l_ecole(client, db_session, ecole):
    prof = Comptes().create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    voisine = Ecoles().create(db_session, nom="Voisine", code_postal="83000")
    admin_voisin = Comptes().create(db_session, ecole_id=voisine.id, role="admin", nom="Z", prenom="W")
    assert client.get(f"/ecoles/{ecole.id}/tarifs", headers=entetes_session(prof)).status_code == 403
    assert client.get(f"/ecoles/{ecole.id}/tarifs", headers=entetes_session(admin_voisin)).status_code == 403


def test_supprimer_la_saison_et_sauvegarde_technique(client, db_session, ecole, tmp_path, monkeypatch):
    import ecoles.stockage
    from ecoles import backup_technique

    monkeypatch.setattr(ecoles.stockage, "DOSSIER_SAUVEGARDES", tmp_path)
    trois = client.post(f"/ecoles/{ecole.id}/tarifs/formules", json=EN_3_FOIS).json()
    client.post(
        f"/ecoles/{ecole.id}/tarifs/options", json={"name": "T-shirt", "amount": 1500, "plan_ids": [trois["id"]]}
    )
    # Sauvegarde puis restauration : la formule, ses échéances et l'option reviennent.
    contenu = backup_technique.generer(db_session, ecole)
    backup_technique.restaurer(db_session, ecole, contenu)
    db_session.expire_all()
    tarifs = _formules(client, ecole.id)
    assert [len(f["installments"]) for f in tarifs["plans"]] == [3]
    assert tarifs["adjustments"][0]["plan_ids"] == [tarifs["plans"][0]["id"]]
    # Supprimer une saison supprime ses formules.
    nouvelle = client.post(f"/ecoles/{ecole.id}/saisons", json=NOUVELLE).json()["saison"]["id"]
    assert client.delete(f"/ecoles/{ecole.id}/saisons/{nouvelle}").status_code == 200
    from plans import SeasonAdjustment, SeasonPlan, SeasonPlanInstallment, season_adjustment_plans
    from sqlalchemy import func, select

    assert db_session.scalar(select(func.count()).select_from(SeasonAdjustment)) == 1
    assert db_session.scalar(select(func.count()).select_from(season_adjustment_plans)) == 1
    assert db_session.scalar(select(func.count()).select_from(SeasonPlan)) == 1
    assert db_session.scalar(select(func.count()).select_from(SeasonPlanInstallment)) == 3
