"""Tests du module comptes (voir spec/SPEC.md §6.2/§6.3)."""

from comptes import Comptes
from ecoles import Ecoles


def test_lister_par_role(client, db_session):
    """Utilisé par Admin > Conversations pour proposer les vrais comptes
    admin de l'école (voir AdminGroupes.jsx)."""
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    comptes = Comptes()
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie-Laure")

    reponse = client.get("/comptes", params={"ecole_id": ecole.id, "role": "admin"})
    assert reponse.status_code == 200
    assert [c["id"] for c in reponse.json()] == [admin.id]


def test_code_recuperation_admin(client, db_session):
    """Voir "Code oublié ?" à l'écran de connexion, et NouvelleEcoleModal :
    "nom de votre 1er animal de compagnie", demandé à la création d'un
    admin."""
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(
        db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia",
        code_recuperation="coocky",
    )
    reponse = client.get(f"/comptes/{admin.id}")
    assert reponse.json()["code_recuperation"] == "coocky"


def test_modifier_email_et_code_recuperation(client, db_session):
    """Profil admin (crayon, voir ProfilScreen.jsx)."""
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(
        db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia",
        email="jd@contretemps.fr", code_recuperation="coocky",
    )

    reponse = client.put(f"/comptes/{admin.id}", json={"code_recuperation": "Rex"})
    assert reponse.status_code == 200
    assert reponse.json()["code_recuperation"] == "Rex"
    assert reponse.json()["email"] == "jd@contretemps.fr"  # pas fourni -> inchangé

    reponse = client.put(f"/comptes/{admin.id}", json={"email": "julia@contretemps.fr"})
    assert reponse.json()["email"] == "julia@contretemps.fr"
    assert reponse.json()["code_recuperation"] == "Rex"  # pas fourni -> inchangé

    assert client.put("/comptes/999", json={"email": "x@x.fr"}).status_code == 404
