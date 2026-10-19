"""Actions que les modules ouvrent à l'assistant (assistant/actions.py et les
actions.py des modules) : proposées sur une carte, faites seulement au clic,
avec les droits de la personne. Vrais droits (`rbac_reel`)."""

import datetime as dt

import pytest

from app import main
from assistant.modifications import Refus
from comptes import Comptes, roles
from cours.models import Cours
from ecoles import Ecoles
from messagerie.models import Conversation, ConversationMembre
from notes_frais.models import NoteFrais

pytestmark = pytest.mark.rbac_reel

actions = main.assistant_client.actions


class Muet:
    def envoyer(self, *args):
        pass

    def notifier(self, *args):
        pass


@pytest.fixture()
def ecole(db_session, monkeypatch, tmp_path):
    ports = main.notes_frais_client.ports
    monkeypatch.setattr(ports, "messager", Muet())
    monkeypatch.setattr(ports, "notifieur", Muet())
    monkeypatch.setattr(main.notes_frais_client.stockage, "root", tmp_path / "notes")
    monkeypatch.setattr(main.documents_client.storage, "root", tmp_path / "docs")
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="julia@test.fr")
    comptes.ajouter_role(db_session, admin, roles.TRESORIER)
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima", email="ima@test.fr")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Margot", email="margot@test.fr")
    return {"id": ecole.id, "admin": admin, "prof": prof, "eleve": eleve}


def _proposer(db, compte, ecole, nom, args):
    return actions.propose(db, compte, ecole["id"], compte.id, nom, args)


def _faire(db, compte, ecole, carte):
    return actions.execute(db, ecole["id"], compte.id, carte["jeton"])


def test_outils_montres_selon_le_role():
    assert [t["name"] for t in actions.tools(admin=False)] == ["submit_expense_report"]
    assert {"create_group_chat", "delete_course"} <= {t["name"] for t in actions.tools(admin=True)}


def test_groupe_cree_renomme_supprime(db_session, ecole):
    admin, prof = ecole["admin"], ecole["prof"]
    texte, carte = _proposer(db_session, admin, ecole, "create_group_chat", {"name": "Bureau", "member_ids": [prof.id]})
    assert carte["libelle"] == "Messagerie" and carte["lignes"] == ["Créer le groupe « Bureau » avec Ima Blanc"]
    assert db_session.query(Conversation).count() == 0  # rien avant le clic
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    groupe = db_session.query(Conversation).one()
    assert groupe.nom == "Bureau"
    assert db_session.query(ConversationMembre).one().membre_id == prof.id
    # Une carte ne sert qu'une fois, et seulement à la personne qui l'a reçue.
    with pytest.raises(Refus):
        _faire(db_session, admin, ecole, carte)

    _, carte = _proposer(db_session, admin, ecole, "rename_group_chat", {"group_name": "bureau", "new_name": "Bureau 2026"})
    with pytest.raises(Refus):
        _faire(db_session, prof, ecole, carte)
    _, carte = _proposer(db_session, admin, ecole, "rename_group_chat", {"group_name": "bureau", "new_name": "Bureau 2026"})
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert db_session.get(Conversation, groupe.id).nom == "Bureau 2026"

    texte, carte = _proposer(db_session, admin, ecole, "delete_group_chat", {"group_name": "Bureau"})
    assert carte is None and "« Bureau 2026 »" in texte  # le refus donne les groupes existants
    _, carte = _proposer(db_session, admin, ecole, "delete_group_chat", {"group_name": "Bureau 2026"})
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert db_session.query(Conversation).count() == 0


def test_membres_d_un_groupe_ajoutes_et_retires(db_session, ecole):
    admin, prof, eleve = ecole["admin"], ecole["prof"], ecole["eleve"]
    _, carte = _proposer(db_session, admin, ecole, "create_group_chat", {"name": "Bureau", "member_ids": [prof.id]})
    _faire(db_session, admin, ecole, carte)
    groupe = db_session.query(Conversation).one()

    args = {"group_name": "bureau", "add_member_ids": [eleve.id], "remove_member_ids": [prof.id]}
    texte, carte = _proposer(db_session, prof, ecole, "update_group_chat_members", args)
    assert carte is None and texte.startswith("Refusé")  # admins seulement
    _, carte = _proposer(db_session, admin, ecole, "update_group_chat_members", args)
    assert carte["lignes"] == ["Groupe « Bureau » : ajouter Margot Perrin ; retirer Ima Blanc"]
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    membres = db_session.query(ConversationMembre).filter_by(conversation_id=groupe.id).all()
    assert [m.membre_id for m in membres] == [eleve.id]

    # Retirer quelqu'un qui n'est pas dans le groupe : refusé avant la carte.
    texte, carte = _proposer(db_session, admin, ecole, "update_group_chat_members", {"group_name": "Bureau", "remove_member_ids": [prof.id]})
    assert carte is None and "n'est pas membre" in texte


def test_cours_cree_puis_supprime_par_un_admin_seulement(db_session, ecole):
    admin, prof = ecole["admin"], ecole["prof"]
    args = {"name": "Salsa débutants", "day": "Mardi", "start": "19:00", "end": "20:00", "room": "Grande salle"}
    texte, carte = _proposer(db_session, prof, ecole, "create_course", args)
    assert carte is None and texte.startswith("Refusé")
    _, carte = _proposer(db_session, admin, ecole, "create_course", args)
    assert carte["lignes"] == ["Créer le cours « Salsa débutants », Mardi 19:00-20:00, salle Grande salle"]
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    cours = db_session.query(Cours).one()
    assert (cours.jour, cours.heure_debut, cours.salle) == ("Mardi", "19:00", "Grande salle")

    _, carte = _proposer(db_session, admin, ecole, "delete_course", {"course_id": cours.id})
    assert carte["lignes"] == ["Supprimer le cours « Salsa débutants » (0 élève inscrit)"]
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert db_session.query(Cours).count() == 0


def test_note_de_frais_pour_quelqu_un(db_session, ecole):
    admin, prof = ecole["admin"], ecole["prof"]
    args = {
        "title": "Costumes gala",
        "expenses": [{"date": "2026-10-12", "amount_euros": 48.9, "description": "Tissu"}],
        "for_person": "margot perrin",
    }
    # Pas de RIB pour Margot : refusé, sauf en don.
    texte, carte = _proposer(db_session, admin, ecole, "submit_expense_report", args)
    assert carte is None and "pas de RIB" in texte
    # Un prof n'est pas trésorier : pas pour quelqu'un d'autre.
    texte, carte = _proposer(db_session, prof, ecole, "submit_expense_report", {**args, "donation": True})
    assert carte is None and "trésoriers" in texte

    _, carte = _proposer(db_session, admin, ecole, "submit_expense_report", {**args, "donation": True})
    assert carte["lignes"] == [
        "Envoyer la note « Costumes gala » pour Margot Perrin aux trésoriers : 48,90 € (Tissu 48,90 € le 12/10), don à l'association"
    ]
    assert db_session.query(NoteFrais).count() == 0
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    note = db_session.query(NoteFrais).one()
    assert note.titre == "Costumes gala" and note.don and note.person_id != admin.id


def test_date_future_refusee(db_session, ecole):
    demain = (dt.date.today() + dt.timedelta(days=1)).isoformat()
    texte, carte = _proposer(db_session, ecole["prof"], ecole, "submit_expense_report", {
        "title": "x", "expenses": [{"date": demain, "amount_euros": 5, "description": "Café"}], "donation": True,
    })
    assert carte is None and "futur" in texte
