"""Une personne = une fiche (spec/core.md §4) : fusionner deux fiches, et
compléter une fiche existante plutôt que d'en créer une autre."""

import pytest
from conftest import entetes_session

from comptes import Comptes, roles
from cours import CoursService
from ecoles import Ecoles
from eleves import Eleves
from eleves.models import ProfilEleve
from messagerie.models import ConversationMembre, Message

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def ecole(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Richard", prenom="Seb", email="seb@test.fr")
    comptes.ajouter_role(db_session, owner, roles.OWNER)
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana", email="ana@test.fr")
    julia_admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="faux@test.fr")
    comptes.ajouter_role(db_session, julia_admin, roles.TRESORIER)
    julia_eleve, _ = Eleves(comptes).create(db_session, ecole.id, nom="DHO", prenom="Julia", email="julia@test.fr", allergies="Pollen")
    cours = CoursService().create(db_session, ecole.id, nom="Jazz")
    CoursService().inscrire_eleve(db_session, cours.id, julia_eleve.id)
    return {"ecole": ecole, "owner": owner, "admin": admin, "julia_admin": julia_admin, "julia_eleve": julia_eleve, "cours": cours}


def _fusionner(client, qui, garde, autre):
    return client.post(f"/comptes/{garde.id}/fusion", json={"autre_id": autre.id}, headers=entetes_session(qui))


def test_fusionner_julia_admin_et_eleve(client, db_session, ecole):
    garde, autre = ecole["julia_eleve"], ecole["julia_admin"]
    dm = client.post(
        "/dm", params={"ecole_id": ecole["ecole"].id, "compte_a_id": ecole["owner"].id, "compte_b_id": autre.id},
        headers=entetes_session(ecole["owner"]),
    ).json()
    client.post(
        f"/conversations/{dm['id']}/messages",
        json={"expediteur_id": autre.id, "contenu": "Bonjour"},
        headers=entetes_session(ecole["owner"]),
    )
    autre_id = autre.id

    reponse = _fusionner(client, ecole["owner"], garde, autre)

    assert reponse.status_code == 200, reponse.text
    corps = reponse.json()
    assert set(corps["roles"]) == {"admin", "tresorier", "eleve"}
    assert set(corps["emails"]) == {"julia@test.fr", "faux@test.fr"}
    db_session.expire_all()
    assert Comptes().get(db_session, autre_id) is None
    assert db_session.get(ProfilEleve, garde.id).allergies == "Pollen"
    assert [c.id for c in CoursService().cours_de_leleve(db_session, garde.id)] == [ecole["cours"].id]
    assert db_session.query(Message).filter_by(expediteur_id=garde.id).count() == 1
    membres = {m.membre_id for m in db_session.query(ConversationMembre).filter_by(conversation_id=dm["id"])}
    assert membres == {ecole["owner"].id, garde.id}


def test_fusion_d_une_fiche_admin_reservee_a_l_administrateur_principal(client, ecole):
    assert _fusionner(client, ecole["admin"], ecole["julia_eleve"], ecole["julia_admin"]).status_code == 403
    assert _fusionner(client, ecole["julia_eleve"], ecole["julia_eleve"], ecole["julia_admin"]).status_code == 403


def test_fusion_de_deux_fiches_non_admin_par_un_admin(client, db_session, ecole):
    comptes = Comptes()
    prof = comptes.create(db_session, ecole_id=ecole["ecole"].id, role="professeur", nom="Cilpa", prenom="Jacqueline")
    eleve = comptes.create(db_session, ecole_id=ecole["ecole"].id, role="eleve", nom="Cilpa", prenom="Jacqueline")
    reponse = _fusionner(client, ecole["admin"], prof, eleve)
    assert reponse.status_code == 200, reponse.text
    assert set(reponse.json()["roles"]) == {"professeur", "eleve"}
    assert _fusionner(client, ecole["admin"], prof, prof).status_code == 409


def test_une_fiche_papier_complete_la_fiche_d_un_prof(db_session, ecole):
    comptes = Comptes()
    prof = comptes.create(db_session, ecole_id=ecole["ecole"].id, role="professeur", nom="Cilpa", prenom="Jacqueline")
    compte, _ = Eleves(comptes).create(db_session, ecole["ecole"].id, nom="Cilpa", prenom="Jacqueline", email="jc@test.fr")
    assert compte.id == prof.id
    assert roles.noms_roles(compte) == ["professeur", "eleve"]
    assert compte.emails == ["jc@test.fr"]


def test_une_fiche_papier_ne_donne_jamais_une_adresse_nouvelle_a_un_admin(db_session, ecole):
    """Sinon l'adresse saisie obtiendrait les droits de l'admin : on crée
    une fiche à part, que l'Administrateur principal fusionnera."""
    assert ecole["julia_eleve"].id != ecole["julia_admin"].id
    assert ecole["julia_admin"].emails == ["faux@test.fr"]
