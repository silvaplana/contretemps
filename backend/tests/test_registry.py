"""Enregistrement des modules (spec/core.md §9 bis)."""

import pytest

import registry
from app.modules import MODULES
from registry import Module


def _module(key, requires=()):
    return Module(key=key, label=key, mount=lambda app, core: None, requires=requires)


def test_la_liste_de_contretemps_est_valide():
    registry.check(MODULES)


def test_un_module_doit_venir_apres_ceux_dont_il_a_besoin():
    with pytest.raises(RuntimeError, match="documents"):
        registry.check([_module("expense_notes", requires=("documents",)), _module("documents")])
    registry.check([_module("documents"), _module("expense_notes", requires=("documents",))])


def test_un_module_ne_se_liste_qu_une_fois():
    with pytest.raises(RuntimeError, match="deux fois"):
        registry.check([_module("videos"), _module("videos")])


def test_l_assistant_recoit_les_actions_des_modules():
    from app import main

    noms = set(main.assistant_client.actions.by_name)
    attendus = {action.name for liste in registry.actions(MODULES, main.core).values() for action in liste}
    assert attendus and attendus <= noms


# --- Modules allumés ou éteints par école (§9 bis.3) ---


def _etats(client, ecole_id, entetes=None):
    return {m["key"]: m["enabled"] for m in client.get(f"/ecoles/{ecole_id}/modules", headers=entetes or {}).json()}


def _ecoles(db):
    from ecoles import Ecoles

    return Ecoles().create(db, nom="Contretemps", code_postal="83330"), Ecoles().create(db, nom="Voisine", code_postal="83000")


def test_tous_les_modules_sont_allumes_par_defaut(client, db_session):
    ecole, _ = _ecoles(db_session)
    assert _etats(client, ecole.id) == {m.key: True for m in MODULES}


def test_eteindre_n_eteint_que_cette_ecole_et_rallumer_retrouve_tout(client, db_session):
    ecole, voisine = _ecoles(db_session)
    assert client.put(f"/ecoles/{ecole.id}/modules/messaging", json={"enabled": False}).status_code == 200
    assert _etats(client, ecole.id)["messaging"] is False
    assert _etats(client, voisine.id)["messaging"] is True
    client.put(f"/ecoles/{ecole.id}/modules/messaging", json={"enabled": True})
    assert all(_etats(client, ecole.id).values())


def test_on_n_eteint_pas_un_module_dont_un_autre_a_besoin(client, db_session):
    ecole, _ = _ecoles(db_session)
    reponse = client.put(f"/ecoles/{ecole.id}/modules/documents", json={"enabled": False})
    assert reponse.status_code == 409 and "Assistant" in reponse.json()["detail"]
    for cle in ("assistant", "expense_notes", "documents"):
        assert client.put(f"/ecoles/{ecole.id}/modules/{cle}", json={"enabled": False}).status_code == 200
    # Allumer les notes de frais rallume Documents, dont elles ont besoin.
    client.put(f"/ecoles/{ecole.id}/modules/expense_notes", json={"enabled": True})
    etats = _etats(client, ecole.id)
    assert etats["expense_notes"] and etats["documents"] and not etats["assistant"]
    assert client.put(f"/ecoles/{ecole.id}/modules/inconnu", json={"enabled": False}).status_code == 404
    # Inscriptions et Financier raisonnent par saison.
    reponse = client.put(f"/ecoles/{ecole.id}/modules/seasons", json={"enabled": False})
    assert reponse.status_code == 409 and "Financier" in reponse.json()["detail"]


def test_l_assistant_ne_propose_pas_les_actions_d_un_module_eteint(db_session):
    from app import main
    from registry.activation import set_enabled

    ecole, voisine = _ecoles(db_session)
    set_enabled(db_session, ecole.id, MODULES, "messaging", False)
    actions = main.assistant_client.actions
    assert "create_group_chat" not in {t["name"] for t in actions.tools(db_session, ecole.id, admin=True)}
    assert "create_group_chat" in {t["name"] for t in actions.tools(db_session, voisine.id, admin=True)}
    texte, carte = actions.propose(db_session, None, ecole.id, 1, "create_group_chat", {})
    assert carte is None and texte.startswith("Refusé")


@pytest.mark.rbac_reel
def test_les_routes_d_un_module_eteint_repondent_introuvable(client, db_session):
    from comptes import Comptes
    from conftest import entetes_session
    from registry.activation import set_enabled

    ecole, voisine = _ecoles(db_session)
    prof = Comptes().create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    voisin = Comptes().create(db_session, ecole_id=voisine.id, role="professeur", nom="Z", prenom="W")
    assert client.get(f"/conversations?ecole_id={ecole.id}", headers=entetes_session(prof)).status_code == 200
    set_enabled(db_session, ecole.id, MODULES, "messaging", False)
    db_session.expire_all()
    assert client.get(f"/conversations?ecole_id={ecole.id}", headers=entetes_session(prof)).status_code == 404
    assert client.get(f"/conversations?ecole_id={voisine.id}", headers=entetes_session(voisin)).status_code == 200
    # La liste des modules reste lisible ; seul l'Administrateur principal
    # (ou le Super User) change un module, un admin ordinaire non.
    assert _etats(client, ecole.id, entetes_session(prof))["messaging"] is False
    principal = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana")
    for compte, attendu in ((prof, 403), (admin, 403), (principal, 200)):
        reponse = client.put(
            f"/ecoles/{ecole.id}/modules/messaging", json={"enabled": True}, headers=entetes_session(compte)
        )
        assert reponse.status_code == attendu
