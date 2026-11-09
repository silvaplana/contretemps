"""Commande app.supprimer_eleves_saison : efface les fiches qui ne sont
qu'élèves dans une saison (élèves fictives de démonstration restées dans
2025-2026 de la vraie école, Seb, 9 novembre 2026)."""

import pytest
import sqlalchemy as sa
from comptes import Comptes, RoleCompte, roles
from comptes.models import Compte
from cours import CoursService
from ecoles import Ecoles
from eleves import Eleves
from saisons import Saison, saison_courante_id
from saisons.portee import toutes_saisons

from app import supprimer_eleves_saison as commande


@pytest.fixture()
def sauvegardes(tmp_path, monkeypatch):
    import ecoles.stockage

    monkeypatch.setattr(ecoles.stockage, "DOSSIER_SAUVEGARDES", tmp_path)
    return tmp_path


@pytest.fixture()
def ecole(db_session, client):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    # Une saison passée, ouverte, avec deux élèves, une prof-élève et une admin.
    passee = client.post(
        f"/ecoles/{ecole.id}/saisons",
        json={"nom": "2025-2026", "date_debut": "2025-09-01", "date_fin": "2026-08-31"},
    ).json()["saison"]["id"]
    eleves = Eleves(comptes=comptes)
    with toutes_saisons(db_session):
        cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Jazz")
        cours.saison_id = passee
        a, _ = eleves.create(db_session, ecole_id=ecole.id, nom="Roussel", prenom="Pauline")
        b, _ = eleves.create(db_session, ecole_id=ecole.id, nom="Roux", prenom="Valentine")
        prof, _ = eleves.create(db_session, ecole_id=ecole.id, nom="Blanc", prenom="Ima")
        prof.roles.append(RoleCompte(role=roles.ADMIN))
        for fiche in (a, b, prof, a.famille, b.famille, prof.famille):
            fiche.saison_id = passee
        db_session.commit()
        CoursService().inscrire_eleve(db_session, cours.id, a.id)
    # Une élève de la saison en cours, qui ne doit pas bouger.
    courante, _ = eleves.create(db_session, ecole_id=ecole.id, nom="Dupont", prenom="Léa")
    db_session.commit()
    return {"ecole": ecole, "passee": passee, "garder": [prof.id, courante.id], "effacer": [a.id, b.id]}


def _ids(db):
    with toutes_saisons(db):
        return set(db.scalars(sa.select(Compte.id)))


def test_a_blanc_rien_n_est_efface(db_session, ecole, sauvegardes, capsys):
    avant = _ids(db_session)
    commande.executer(db_session, ecole["ecole"].id, "2025-2026", "Contretemps", pour_de_vrai=False)
    assert _ids(db_session) == avant
    assert "2 fiches" in capsys.readouterr().out
    assert not list(sauvegardes.iterdir())


def test_efface_seulement_les_eleves_de_la_saison(db_session, ecole, sauvegardes):
    commande.executer(db_session, ecole["ecole"].id, "2025-2026", "Contretemps", pour_de_vrai=True)
    restants = _ids(db_session)
    assert not restants & set(ecole["effacer"])
    assert set(ecole["garder"]) <= restants
    # Une sauvegarde complète de l'école est écrite juste avant.
    assert len(list(sauvegardes.rglob("*_techBackup.xlsx"))) == 1
    # Plus aucune inscription à un cours pour les fiches effacées.
    membres = set(db_session.scalars(sa.text("SELECT member_id FROM group_members")))
    assert not membres & set(ecole["effacer"])


def test_nom_ou_saison_faux_rien_n_est_efface(db_session, ecole, sauvegardes):
    avant = _ids(db_session)
    with pytest.raises(SystemExit):
        commande.executer(db_session, ecole["ecole"].id, "2025-2026", "Autre", pour_de_vrai=True)
    with pytest.raises(SystemExit):
        commande.executer(db_session, ecole["ecole"].id, "2024-2025", "Contretemps", pour_de_vrai=True)
    assert _ids(db_session) == avant


def test_la_saison_en_cours_est_refusee(db_session, ecole, sauvegardes):
    nom = db_session.get(Saison, saison_courante_id(db_session, ecole["ecole"].id)).nom
    with pytest.raises(SystemExit):
        commande.executer(db_session, ecole["ecole"].id, nom, "Contretemps", pour_de_vrai=True)
