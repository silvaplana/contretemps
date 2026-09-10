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
