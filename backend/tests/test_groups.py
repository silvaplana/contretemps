"""Groupes du core (spec/core.md §5) : le bureau est un groupe « Bureau » et
ses sous-groupes, par école et par saison. Les fonctions suivent la fiche
quand on la fusionne, la supprime, la sauvegarde ou la restaure."""

import pytest
import sqlalchemy as sa
from conftest import entetes_session

from comptes import Comptes, roles
from ecoles import Ecoles
from eleves import Eleves
from groups import Group, GroupMember, board
from saisons.portee import toutes_saisons

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


@pytest.fixture()
def ecole(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Richard", prenom="Seb", email="seb@test.fr")
    comptes.ajouter_role(db_session, owner, roles.OWNER)
    julia_admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="faux@test.fr")
    julia_eleve, _ = Eleves(comptes).create(db_session, ecole.id, nom="DHO", prenom="Julia", email="julia@test.fr")
    return {"ecole": ecole, "owner": owner, "julia_admin": julia_admin, "julia_eleve": julia_eleve}


def test_le_bureau_est_un_groupe_et_ses_sous_groupes(db_session, ecole):
    board.set_functions(db_session, ecole["owner"], ["secretary", "president", "secretary"])
    db_session.commit()

    assert board.functions_of(db_session, ecole["owner"]) == ["president", "secretary"]
    groupes = db_session.scalars(sa.select(Group).where(Group.org_id == ecole["ecole"].id).order_by(Group.id)).all()
    parent = groupes[0]
    assert (parent.name, parent.key, parent.parent_id) == ("Bureau", "board", None)
    assert [(g.name, g.parent_id) for g in groupes[1:]] == [
        ("Président·e", parent.id), ("Vice-président·e", parent.id), ("Secrétaire", parent.id), ("Trésorier·e", parent.id),
    ]
    assert {g.season_id for g in groupes} == {ecole["owner"].saison_id}

    # Remplacer, pas ajouter ; le bureau n'est créé qu'une fois.
    board.set_functions(db_session, ecole["owner"], ["treasurer"])
    board.set_functions(db_session, ecole["julia_admin"], ["president"])
    db_session.commit()
    assert board.board(db_session, ecole["ecole"].id, ecole["owner"].saison_id) == {
        ecole["owner"].id: ["treasurer"], ecole["julia_admin"].id: ["president"],
    }
    assert db_session.scalar(sa.select(sa.func.count()).select_from(Group)) == 5


@pytest.mark.rbac_reel
def test_la_fusion_garde_les_fonctions_du_bureau(client, db_session, ecole):
    board.set_functions(db_session, ecole["julia_admin"], ["president"])
    db_session.commit()

    reponse = client.post(
        f"/comptes/{ecole['julia_eleve'].id}/fusion", json={"autre_id": ecole["julia_admin"].id},
        headers=entetes_session(ecole["owner"]),
    )

    assert reponse.status_code == 200, reponse.text
    db_session.expire_all()
    assert board.functions_of(db_session, ecole["julia_eleve"]) == ["president"]


def test_supprimer_une_fiche_la_retire_du_bureau(db_session, ecole):
    board.set_functions(db_session, ecole["julia_eleve"], ["secretary"])
    db_session.commit()
    eleve_id = ecole["julia_eleve"].id

    Eleves(Comptes()).delete(db_session, eleve_id)

    assert db_session.scalar(sa.select(sa.func.count()).where(GroupMember.member_id == eleve_id)) == 0


def test_la_sauvegarde_technique_garde_le_bureau(client, db_session, ecole):
    ecole_id = ecole["ecole"].id
    board.set_functions(db_session, ecole["julia_admin"], ["president", "treasurer"])
    db_session.commit()
    sauvegarde = client.get(f"/ecoles/{ecole_id}/export-technique").content

    assert client.delete(f"/ecoles/{ecole_id}/donnees").status_code == 204
    assert db_session.scalar(sa.select(sa.func.count()).select_from(GroupMember)) == 0
    reponse = client.post(f"/ecoles/{ecole_id}/restaurer", files={"fichier": ("backup.xlsx", sauvegarde, XLSX)})

    assert reponse.status_code == 204
    db_session.expire_all()
    with toutes_saisons(db_session):
        julia = Comptes().get(db_session, ecole["julia_admin"].id)
        assert board.functions_of(db_session, julia) == ["president", "treasurer"]
