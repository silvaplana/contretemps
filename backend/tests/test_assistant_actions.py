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


def _superuser(db):
    return Comptes().enregistrer_superuser(db, nom="Richard", prenom="Seb", email="seb@test.fr", mot_de_passe_hache="x")


def test_groupe_avec_les_tresoriers_et_le_super_user(db_session, ecole):
    """Seb, 19 octobre : le Super User n'a pas de fiche d'école, mais on
    l'ajoute aux groupes comme dans l'écran Nouveau groupe."""
    admin, su = ecole["admin"], _superuser(db_session)
    _, carte = _proposer(db_session, admin, ecole, "create_group_chat", {"name": "Trésorerie", "member_ids": [admin.id, su.id]})
    assert carte["lignes"] == ["Créer le groupe « Trésorerie » avec Julia Dho, Seb Richard"]
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert {m.membre_id for m in db_session.query(ConversationMembre)} == {admin.id, su.id}


def test_ajouter_et_retirer_des_membres_d_un_groupe(db_session, ecole):
    admin, prof, eleve = ecole["admin"], ecole["prof"], ecole["eleve"]
    _, carte = _proposer(db_session, admin, ecole, "create_group_chat", {"name": "Bureau", "member_ids": [admin.id]})
    _faire(db_session, admin, ecole, carte)
    _, carte = _proposer(db_session, admin, ecole, "add_group_members", {"group_name": "Bureau", "member_ids": [prof.id, eleve.id]})
    assert carte["lignes"] == ["Ajouter au groupe « Bureau » : Ima Blanc, Margot Perrin"]
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    _, carte = _proposer(db_session, admin, ecole, "remove_group_members", {"group_name": "Bureau", "member_ids": [eleve.id]})
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert {m.membre_id for m in db_session.query(ConversationMembre)} == {admin.id, prof.id}


def test_roles_changes_par_l_administrateur_principal_seulement(db_session, ecole):
    """Seb, 19 octobre : seul un administrateur principal nomme des
    trésoriers ou des administrateurs."""
    owner, prof = ecole["admin"], ecole["prof"]
    autre_admin = Comptes().create(db_session, ecole_id=ecole["id"], role="admin", nom="Silpa", prenom="Jacqueline")
    texte, carte = _proposer(db_session, autre_admin, ecole, "change_roles", {"person_id": prof.id, "admin": True})
    assert carte is None and "administrateurs principaux" in texte

    _, carte = _proposer(db_session, owner, ecole, "change_roles", {"person_id": prof.id, "admin": True, "treasurer": True})
    assert carte["lignes"] == ["Ima Blanc : devient administrateur, devient trésorier"]
    assert not roles.is_admin(prof)  # rien avant le clic
    assert _faire(db_session, owner, ecole, carte)[0]["ok"]
    db_session.refresh(prof)
    assert roles.is_admin(prof) and roles.is_tresorier(prof) and roles.is_prof(prof)

    # Retirer administrateur retire aussi trésorier ; le professeur reste.
    _, carte = _proposer(db_session, owner, ecole, "change_roles", {"person_id": prof.id, "admin": False})
    assert carte["lignes"] == ["Ima Blanc : n'est plus administrateur, n'est plus trésorier"]
    _faire(db_session, owner, ecole, carte)
    db_session.refresh(prof)
    assert not roles.is_admin(prof) and not roles.is_tresorier(prof) and roles.is_prof(prof)

    # Pas sur sa propre ligne, sauf la case Trésorier.
    texte, carte = _proposer(db_session, owner, ecole, "change_roles", {"person_id": owner.id, "main_admin": False})
    assert carte is None
    _, carte = _proposer(db_session, owner, ecole, "change_roles", {"person_id": owner.id, "treasurer": False})
    assert _faire(db_session, owner, ecole, carte)[0]["ok"]


def test_le_super_user_change_les_roles_et_cree_un_administrateur(db_session, ecole):
    su, eleve = _superuser(db_session), ecole["eleve"]
    _, carte = _proposer(db_session, su, ecole, "change_roles", {"person_id": eleve.id, "admin": True, "main_admin": True})
    assert _faire(db_session, su, ecole, carte)[0]["ok"]
    db_session.refresh(eleve)
    assert roles.is_owner(eleve)
    _, carte = _proposer(db_session, su, ecole, "create_admin", {"last_name": "Martin", "first_name": "Paul", "email": "paul@test.fr"})
    assert carte["lignes"] == ["Créer l'administrateur Paul Martin (paul@test.fr)"]
    assert _faire(db_session, su, ecole, carte)[0]["ok"]


def test_coordonnees_de_l_ecole(db_session, ecole):
    admin, prof = ecole["admin"], ecole["prof"]
    texte, carte = _proposer(db_session, admin, ecole, "update_school", {"siret": "123"})
    assert carte is None and "Refusé" in texte  # SIRET faux : refusé avant la carte
    _, carte = _proposer(db_session, prof, ecole, "update_school", {"city": "Le Beausset"})
    assert carte is None
    _, carte = _proposer(db_session, admin, ecole, "update_school", {"city": "Le Beausset", "contact_email": "bureau@test.fr"})
    assert carte["lignes"] == ["Coordonnées de l'école : ville : Le Beausset, email de contact : bureau@test.fr"]
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert Ecoles().get(db_session, ecole["id"]).ville == "Le Beausset"


def test_professeur_cree_modifie_supprime(db_session, ecole):
    admin = ecole["admin"]
    _, carte = _proposer(db_session, admin, ecole, "create_teacher", {"last_name": "Noir", "first_name": "Léa"})
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    lea = main.profs_client.list(db_session, ecole["id"])[-1]
    _, carte = _proposer(db_session, admin, ecole, "update_teacher", {"teacher_id": lea.id, "phone": "0600000000"})
    assert carte["lignes"] == ["Professeur Léa Noir : téléphone : 0600000000"]
    _faire(db_session, admin, ecole, carte)
    assert main.profs_client.get(db_session, lea.id).telephone == "0600000000"
    _, carte = _proposer(db_session, admin, ecole, "delete_teacher", {"teacher_id": lea.id})
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert main.profs_client.get(db_session, lea.id) is None


def test_eleve_et_choregraphie_supprimes(db_session, ecole):
    admin, eleve = ecole["admin"], ecole["eleve"]
    cours = main.cours_client.create(db_session, ecole_id=ecole["id"], nom="Jazz")
    chore = main.choregraphies_client.create(db_session, cours.id, nom="Gala")
    _, carte = _proposer(db_session, admin, ecole, "delete_choreography", {"choreography_id": chore.id})
    assert carte["lignes"] == ["Supprimer la chorégraphie « Gala »"]
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert main.choregraphies_client.get(db_session, chore.id) is None
    _, carte = _proposer(db_session, admin, ecole, "delete_student", {"student_id": eleve.id})
    assert _faire(db_session, admin, ecole, carte)[0]["ok"]
    assert main.eleves_client.get_compte(db_session, eleve.id) is None
