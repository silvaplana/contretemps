"""Groupes du core (spec/core.md §5) : le bureau est un groupe « Bureau » et
ses sous-groupes, par école et par saison. Les fonctions suivent la fiche
quand on la fusionne, la supprime, la sauvegarde ou la restaure."""

import pytest
import sqlalchemy as sa
from conftest import entetes_session

from comptes import Comptes, RoleCompte, roles
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


def test_les_profs_sont_un_groupe_et_gardent_leur_role(db_session, ecole):
    comptes = Comptes()
    prof = comptes.create(db_session, ecole_id=ecole["ecole"].id, role="professeur", nom="Noir", prenom="Léa")

    groupe = db_session.scalar(sa.select(Group).where(Group.key == "teachers"))
    assert (groupe.name, groupe.org_id, groupe.season_id) == ("Profs", ecole["ecole"].id, prof.saison_id)
    assert db_session.scalar(sa.select(sa.func.count()).where(GroupMember.member_id == prof.id)) == 1
    assert db_session.scalar(sa.select(sa.func.count()).select_from(RoleCompte).where(RoleCompte.compte_id == prof.id)) == 0
    # Vu de l'appli, rien ne change : le rôle, le rang, les listes.
    assert roles.is_prof(prof) and prof.noms_roles == ["professeur"] and prof.role_principal == "professeur"
    assert roles.rang(prof) == roles.RANG[roles.PROFESSEUR]
    assert [c.id for c in comptes.list_par_role(db_session, ecole["ecole"].id, "professeur")] == [prof.id]

    # Cumul avec admin, puis retrait du rôle Professeur.
    comptes.ajouter_role(db_session, ecole["julia_admin"], roles.PROFESSEUR)
    assert ecole["julia_admin"].noms_roles == ["admin", "professeur"]
    comptes.retirer_role(db_session, ecole["julia_admin"], roles.PROFESSEUR)
    assert ecole["julia_admin"].noms_roles == ["admin"]
    # Un prof seul garde au moins un rôle.
    with pytest.raises(Exception, match="au moins un rôle"):
        comptes.retirer_role(db_session, prof, roles.PROFESSEUR)


@pytest.mark.rbac_reel
def test_la_fusion_de_deux_profs_garde_un_seul_prof(client, db_session, ecole):
    comptes = Comptes()
    ecole_id = ecole["ecole"].id
    lea = comptes.create(db_session, ecole_id=ecole_id, role="professeur", nom="Noir", prenom="Léa")
    doublon = comptes.create(db_session, ecole_id=ecole_id, role="professeur", nom="NOIR", prenom="Léa")

    reponse = client.post(f"/comptes/{lea.id}/fusion", json={"autre_id": doublon.id}, headers=entetes_session(ecole["owner"]))

    assert reponse.status_code == 200, reponse.text
    db_session.expire_all()
    assert [c.id for c in comptes.list_par_role(db_session, ecole_id, "professeur")] == [lea.id]


def test_une_ancienne_sauvegarde_remet_les_profs_dans_le_groupe(client, db_session, ecole):
    """Sauvegarde d'avant le groupe : une ligne « professeur » dans RolesComptes."""
    from openpyxl import load_workbook
    import io

    ecole_id = ecole["ecole"].id
    prof = Comptes().create(db_session, ecole_id=ecole_id, role="professeur", nom="Noir", prenom="Léa")
    classeur = load_workbook(io.BytesIO(client.get(f"/ecoles/{ecole_id}/export-technique").content))
    feuille = classeur["RolesComptes"]
    en_tetes = [c.value for c in feuille[1]]
    ligne = {"compte_id": prof.id, "role": "professeur", "created_at": None}
    feuille.append([ligne.get(nom) for nom in en_tetes])
    for nom in ("Groupes", "MembresGroupes"):
        del classeur[nom]
    sortie = io.BytesIO()
    classeur.save(sortie)

    reponse = client.post(f"/ecoles/{ecole_id}/restaurer", files={"fichier": ("backup.xlsx", sortie.getvalue(), XLSX)})

    assert reponse.status_code == 204, reponse.text
    db_session.expire_all()
    with toutes_saisons(db_session):
        assert [c.id for c in Comptes().list_par_role(db_session, ecole_id, "professeur")] == [prof.id]
        assert roles.noms_roles(Comptes().get(db_session, prof.id)) == ["professeur"]


def test_une_nouvelle_saison_recopie_les_groupes_faits_a_la_main(client, db_session, ecole):
    from groups import custom

    ecole_id = ecole["ecole"].id
    ancienne = ecole["owner"].saison_id
    benevoles = custom.create(db_session, ecole_id, ancienne, "Bénévoles")
    custom.create(db_session, ecole_id, ancienne, "Vide")
    custom.set_groups(db_session, ecole["owner"], [benevoles.id])
    db_session.commit()

    reponse = client.post(
        f"/ecoles/{ecole_id}/saisons", json={"nom": "2027-2028", "date_debut": "2027-09-01", "date_fin": "2028-08-31"}
    )

    assert reponse.status_code == 201, reponse.text
    nouvelle = reponse.json()["saison"]["id"]
    groupes = custom.groups(db_session, ecole_id, nouvelle)
    assert [g.name for g in groupes] == ["Bénévoles", "Vide"]
    membres = db_session.scalars(sa.select(GroupMember.member_id).where(GroupMember.group_id == groupes[0].id)).all()
    with toutes_saisons(db_session):
        assert [Comptes().get(db_session, m).compte_precedent_id for m in membres] == [ecole["owner"].id]
