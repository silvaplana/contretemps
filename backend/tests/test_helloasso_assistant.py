"""HelloAsso and FFST opened to the assistant (helloasso/lectures.py,
helloasso/actions.py, ffst/lectures.py ; Seb, 20 novembre 2026) : lectures
sans carte, actions par carte Faire / Annuler, mêmes droits que les écrans.
Aucun appel réseau."""

import json

import pytest
from comptes import Compte, Comptes, roles
from ecoles import Ecoles

from app import main

pytestmark = pytest.mark.rbac_reel

actions = main.assistant_client.actions


def _paiement(montant, etat, date):
    return {"amount": montant, "date": date, "state": etat, "means": "Card", "installment": 1}


def _inscrit(item_id, prenom, nom, payeur, paiements, reponses=()):
    return {
        "item_id": item_id, "order_id": f"c{item_id}", "first_name": prenom, "last_name": nom,
        "payer_email": payeur, "tier_name": "Adulte", "amount": sum(p["amount"] for p in paiements),
        "discount_code": None, "state": "Processed", "order_date": "2026-09-02T10:00:00",
        "answers": list(reponses), "payments": paiements,
    }


SANTE = {"id": "9", "name": "Allergies", "type": "TextInput", "answer": "Arachide"}
INSCRITS = [
    _inscrit("1", "Léa", "Martin", "lea@test.fr", [_paiement(12000, "Authorized", "2026-09-02T10:00:00")], [SANTE]),
    _inscrit("2", "Tom", "Benali", "tom@test.fr", [
        _paiement(8000, "Authorized", "2026-09-02T10:00:00"), _paiement(8000, "Refused", "2026-10-02T10:00:00"),
    ]),
    _inscrit("3", "Inès", "Navarro", "ines@test.fr", [
        _paiement(8000, "Authorized", "2026-09-02T10:00:00"), _paiement(8000, "Pending", "2099-12-02T10:00:00"),
    ]),
]


@pytest.fixture()
def ecole(db_session, monkeypatch):
    from app.modules import MODULES
    from helloasso.api import Form, Organization
    from registry.activation import set_enabled

    ecole = Ecoles().create(db_session, nom="Sambo La Ciotat", code_postal="13600")
    set_enabled(db_session, ecole.id, MODULES, "helloasso", True)
    set_enabled(db_session, ecole.id, MODULES, "ffst", True)
    comptes = Comptes()
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana", email="ana@test.fr")
    comptes.ajouter_role(db_session, owner, roles.OWNER)
    comptes.ajouter_role(db_session, owner, roles.TRESORIER)
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="julia@test.fr")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Vidal", prenom="Paul", email="paul@test.fr")

    core = main.core
    monkeypatch.setattr(core.helloasso_connection, "connect",
                        lambda client_id, secret: Organization(name="Alliance Sambo", slug="alliance", forms=[]))
    campaigns = core.helloasso_campaigns
    monkeypatch.setattr(campaigns, "_lists", {})
    monkeypatch.setattr(campaigns, "forms", lambda *_: [
        Form("Membership", "adhesion", "Adhésion 2026-2027", "Public"), Form("Event", "stage", "Stage d'été", "Private"),
    ])
    monkeypatch.setattr(campaigns, "form_fields", lambda *_: [])
    monkeypatch.setattr(core.helloasso_sync, "orders", lambda *_: INSCRITS)
    core.helloasso_connection.save(db_session, ecole.id, "3f9c2a", "le-secret")
    db_session.commit()
    return {"id": ecole.id, "owner": owner, "admin": admin, "eleve": eleve}


def _proposer(db, compte, ecole, nom, args=None):
    return actions.propose(db, compte, ecole["id"], compte.id, nom, args or {})


def _faire(db, compte, ecole, carte):
    return actions.execute(db, ecole["id"], compte.id, carte["jeton"])


def _lire(db, compte, ecole, nom, args=None):
    texte, carte = _proposer(db, compte, ecole, nom, args)
    assert carte is None, texte
    return json.loads(texte)


def _saison_imposee(db, ecole):
    """L'administrateur principal choisit la campagne, un admin recopie."""
    texte, carte = _proposer(db, ecole["owner"], ecole, "set_helloasso_season", {"mode": "master", "campaign": "adhésion"})
    assert carte is not None and "Adhésion 2026-2027" in carte["lignes"][0], texte
    assert _faire(db, ecole["owner"], ecole, carte)[0]["ok"]
    texte, carte = _proposer(db, ecole["admin"], ecole, "sync_helloasso")
    assert carte is not None and "Recopier" in carte["lignes"][0]
    assert _faire(db, ecole["admin"], ecole, carte)[0]["ok"]


def _fiches(db, ecole):
    return {c.prenom: c.id for c in db.query(Compte).filter(Compte.ecole_id == ecole["id"])}


def test_outils_reserves_aux_administrateurs(db_session, ecole):
    noms = {t["name"] for t in actions.tools(db_session, ecole["id"], admin=True)}
    assert {"helloasso_campaign", "helloasso_members", "helloasso_money", "set_helloasso_season", "sync_helloasso",
            "mail_helloasso_members", "review_helloasso_files", "set_helloasso_new_members", "ffst_licences"} <= noms
    for nom in ("helloasso_campaign", "helloasso_members", "helloasso_money", "sync_helloasso", "ffst_licences"):
        texte, carte = _proposer(db_session, ecole["eleve"], ecole, nom)
        assert carte is None and "administrateurs" in texte, nom


def test_campagne_choisie_par_l_administrateur_principal(db_session, ecole):
    texte, carte = _proposer(db_session, ecole["admin"], ecole, "set_helloasso_season", {"mode": "master", "campaign": "adhésion"})
    assert carte is None and "principaux" in texte
    lue = _lire(db_session, ecole["admin"], ecole, "helloasso_campaign")
    assert lue["connected"] and lue["mode"] == "Sans HelloAsso" and lue["campaigns"] is None
    assert "secret" not in json.dumps(lue) and "3f9c2a" not in json.dumps(lue)

    _saison_imposee(db_session, ecole)
    lue = _lire(db_session, ecole["owner"], ecole, "helloasso_campaign", {"refresh_list": True})
    assert lue["mode"] == "HelloAsso fait tout" and lue["campaign"]["name"] == "Adhésion 2026-2027"
    assert [c["name"] for c in lue["campaigns"]] == ["Adhésion 2026-2027", "Stage d'été"]
    assert lue["syncedAt"] is not None

    texte, carte = _proposer(db_session, ecole["owner"], ecole, "set_helloasso_season", {"mode": "payment"})
    assert carte is not None and "L'appli fait tout" in carte["lignes"][0]
    assert _faire(db_session, ecole["owner"], ecole, carte)[0]["ok"]
    assert _lire(db_session, ecole["admin"], ecole, "helloasso_campaign")["campaign"] is None


def test_adherents_statuts_et_fiche_sans_sante(db_session, ecole):
    assert _lire(db_session, ecole["admin"], ecole, "helloasso_members")["imposed"] is False
    _saison_imposee(db_session, ecole)
    lus = _lire(db_session, ecole["admin"], ecole, "helloasso_members")
    statuts = {m["firstName"]: m["payment"] for m in lus["lines"]}
    assert statuts == {"Léa": "payé", "Tom": "impayé", "Inès": "à encaisser"}
    assert [m["firstName"] for m in _lire(db_session, ecole["admin"], ecole, "helloasso_members", {"status": "impayé"})["lines"]] == ["Tom"]
    assert "Arachide" not in json.dumps(lus)

    lea = _fiches(db_session, ecole)["Léa"]
    texte, _ = _proposer(db_session, ecole["admin"], ecole, "helloasso_members", {"member_id": lea})
    fiche = json.loads(texte)
    assert fiche["payer"]["email"] == "lea@test.fr" and fiche["payments"][0]["amount"] == 120
    assert "Arachide" not in texte and "Allergies" not in texte


def test_a_encaisser_impayes_et_statistiques(db_session, ecole):
    assert _lire(db_session, ecole["admin"], ecole, "helloasso_money")["campaign"] is False
    _saison_imposee(db_session, ecole)
    argent = _lire(db_session, ecole["admin"], ecole, "helloasso_money")
    assert [m["name"] for m in argent["unpaid"]] == ["Tom Benali"] and argent["unpaid"][0]["unpaid"] == 80
    assert [u["name"] for u in argent["toPayToHelloasso"]["lines"]] == ["Tom Benali", "Inès Navarro"]
    assert argent["toPayToHelloasso"]["overdue"] == 1
    assert argent["statistics"]["members"] == 3 and argent["statistics"]["finances"] is False
    # Le trésorier voit la partie Financier, comme à l'écran.
    assert _lire(db_session, ecole["owner"], ecole, "helloasso_money")["statistics"]["finances"] is True


def test_relancer_les_impayes_par_mail(db_session, ecole, monkeypatch):
    envoyes = []
    monkeypatch.setattr(main.core.helloasso_receiver, "send_mail",
                        lambda db, org_id, a, sujet, texte, html: envoyes.append((a, sujet, texte)) or "club@test.fr")
    _saison_imposee(db_session, ecole)
    texte, carte = _proposer(db_session, ecole["admin"], ecole, "mail_helloasso_members", {"unpaid": True, "subject": "Relance"})
    assert carte is None and "obligatoires" in texte
    texte, carte = _proposer(db_session, ecole["admin"], ecole, "mail_helloasso_members",
                             {"unpaid": True, "subject": "Relance", "message": "Bonjour {prénom},\nun paiement a échoué."})
    assert carte is not None and "Tom Benali (tom@test.fr)" in carte["lignes"][0] and "Relance" in carte["lignes"][0]
    assert envoyes == []  # rien ne part avant « Faire »
    assert _faire(db_session, ecole["admin"], ecole, carte)[0]["ok"]
    assert envoyes == [("tom@test.fr", "Relance", "Bonjour Tom,\nun paiement a échoué.")]
    lignes = {m["firstName"]: m for m in _lire(db_session, ecole["admin"], ecole, "helloasso_members")["lines"]}
    assert lignes["Tom"]["mails"] == 1


def test_valider_un_dossier_et_verifier_les_adherents(db_session, ecole):
    _saison_imposee(db_session, ecole)
    tom = _fiches(db_session, ecole)["Tom"]
    texte, carte = _proposer(db_session, ecole["admin"], ecole, "review_helloasso_files", {"validate_ids": [tom]})
    assert carte is not None and "Valider le dossier de Tom Benali" in carte["lignes"][0]
    assert _faire(db_session, ecole["admin"], ecole, carte)[0]["ok"]
    lignes = {m["firstName"]: m for m in _lire(db_session, ecole["admin"], ecole, "helloasso_members")["lines"]}
    assert lignes["Tom"]["check"] == {"ok": True, "issues": []}
    # Vérification éteinte : refusée.
    texte, carte = _proposer(db_session, ecole["owner"], ecole, "review_helloasso_files", {"check_all": True})
    assert carte is None and "pas allumée" in texte


def test_reglages_nouveaux_adherents(db_session, ecole):
    from helloasso.connection import Connection

    texte, carte = _proposer(db_session, ecole["admin"], ecole, "set_helloasso_new_members", {"notify_new": True})
    assert carte is None and "principaux" in texte
    texte, carte = _proposer(db_session, ecole["owner"], ecole, "set_helloasso_new_members", {"notify_new": True})
    assert carte is not None and "prévenir les administrateurs : oui" in carte["lignes"][0]
    assert _faire(db_session, ecole["owner"], ecole, carte)[0]["ok"]
    ligne = Connection.row(db_session, ecole["id"])
    assert (ligne.notify_new, ligne.check_files) == (True, False)


def test_licences_ffst_en_lecture(db_session, ecole):
    from ffst.models import FfstConnection, FfstSnapshot
    from ffst.site import DRAFTS, LICENSEES

    assert _lire(db_session, ecole["admin"], ecole, "ffst_licences") == {"connected": False}
    db_session.add(FfstConnection(org_id=ecole["id"], login_part1="21", login_part2="13", login_part3="1230",
                                  password_encrypted="x"))
    db_session.add(FfstSnapshot(org_id=ecole["id"], list_name=LICENSEES, rows=[
        {"Nom et Prénom": "MARTIN Léa", "Né(e) le": "01/02/2000", "Type": "Pratiquant", "Licence n°": "123",
         "Adresse": "1 rue des Lilas"},
    ]))
    db_session.add(FfstSnapshot(org_id=ecole["id"], list_name=DRAFTS, rows=[{"Nom et Prénom": "BENALI Tom", "Etat": "Brouillon"}]))
    db_session.commit()
    lu = _lire(db_session, ecole["admin"], ecole, "ffst_licences")
    assert lu["lists"]["licensees"]["lines"] == [{"name": "MARTIN Léa", "born": "01/02/2000", "nature": "Pratiquant", "licence": "123"}]
    assert lu["lists"]["drafts"]["count"] == 1 and lu["readAt"] is not None and "password" not in json.dumps(lu)
    assert _lire(db_session, ecole["admin"], ecole, "ffst_licences", {"list": "drafts", "text": "léa"})["lists"] == {
        "drafts": {"count": 0, "lines": []}
    }
