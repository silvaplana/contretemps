"""Tests de l'export École (Admin > École, "Sauvegarder École" — voir
ecoles/excel_export.py pour le fichier humain, ecoles/backup_technique.py
pour le fichier technique/la restauration, receiver.py pour les routes).
"""

import io
import shutil

import openpyxl
import pytest
from comptes import Comptes
from cours import CoursService
from ecoles.stockage import DOSSIER_SAUVEGARDES
from eleves import Eleves
from messagerie import Conversations, Messages


@pytest.fixture()
def _nettoyage_dossier():
    dossiers = []
    yield dossiers
    for dossier in dossiers:
        shutil.rmtree(dossier, ignore_errors=True)


@pytest.fixture()
def scenario(db_session):
    """Une école avec : 2 admins, 1 prof (avec un cours enseigné et des
    heures saisies), 1 élève (avec profil/contact/cours suivi), une
    conversation de groupe avec un message — de quoi couvrir chaque
    onglet des 2 exports."""
    comptes = Comptes()
    cours_service = CoursService()
    eleves_service = Eleves(comptes=comptes)
    conversations = Conversations(comptes=comptes, cours=cours_service)
    messages = Messages(conversations=conversations)

    ecole_id = 1
    from ecoles.models import Ecole

    ecole = Ecole(
        id=ecole_id,
        nom="Contretemps Test",
        code_postal="83330",
        code_acces_admin="ADMIN",
        code_acces_prof="PROF",
        code_acces_eleve="ELEVE",
    )
    db_session.add(ecole)
    db_session.commit()

    admin1 = comptes.create(db_session, ecole_id=ecole_id, role="admin", nom="Dho", prenom="Julia")
    admin2 = comptes.create(db_session, ecole_id=ecole_id, role="admin", nom="Second", prenom="Admin")
    prof = comptes.create(
        db_session, ecole_id=ecole_id, role="professeur", nom="Perrin", prenom="Charlotte",
        email="cp@test.fr", telephone="0600000000",
    )
    cours = cours_service.create(db_session, ecole_id=ecole_id, nom="Éveil", jour="Mercredi")
    cours_service.ajouter_professeur(db_session, cours.id, prof.id)

    compte_eleve, _profil = eleves_service.create(
        db_session, ecole_id=ecole_id, nom="Martin", prenom="Alix",
        email="parent@test.fr", telephone="0611111111",
        date_naissance=None, adresse="1 rue Test", allergies="Arachides",
    )
    eleves_service.ajouter_contact(
        db_session, compte_eleve.id, nom="Martin", prenom="Sophie", lien="Mère",
        telephone="0622222222", email="sophie@test.fr",
    )
    cours_service.inscrire_eleve(db_session, cours.id, compte_eleve.id)

    conv = conversations.create_groupe(db_session, ecole_id, "Groupe test", [("compte", prof.id)])
    messages.envoyer(db_session, conv.id, admin1.id, "Bonjour tout le monde")

    return {
        "ecole": ecole,
        "admin1": admin1,
        "admin2": admin2,
        "prof": prof,
        "eleve": compte_eleve,
        "cours": cours,
        "conversation": conv,
    }


def _classeur(reponse):
    assert reponse.status_code == 200
    return openpyxl.load_workbook(io.BytesIO(reponse.content))


def test_export_humain(client, scenario):
    reponse = client.get(f"/ecoles/{scenario['ecole'].id}/export")
    classeur = _classeur(reponse)
    assert classeur.sheetnames == ["Élèves", "Profs", "Cours"]

    feuille_eleves = classeur["Élèves"]
    en_tetes = [c.value for c in feuille_eleves[1]]
    assert en_tetes[:7] == [
        "Nom adhérent", "Prénom adhérent", "Nom - Prénom parent", "E-Mail", "Adresse", "Téléphone", "Age",
    ]
    assert "Éveil" in en_tetes
    ligne_alix = [c.value for c in feuille_eleves[2]]
    assert ligne_alix[0] == "Martin"
    assert ligne_alix[1] == "Alix"
    assert ligne_alix[2] == "Martin Sophie"
    assert ligne_alix[en_tetes.index("Éveil")] == "X"

    feuille_profs = classeur["Profs"]
    ligne_prof = [c.value for c in feuille_profs[2]]
    assert ligne_prof[0] == "Perrin"
    assert ligne_prof[4] == "Éveil"

    feuille_cours = classeur["Cours"]
    ligne_cours = [c.value for c in feuille_cours[2]]
    assert ligne_cours[0] == "Éveil"
    assert ligne_cours[-1] == 1  # 1 élève inscrit


def test_export_technique(client, scenario):
    reponse = client.get(f"/ecoles/{scenario['ecole'].id}/export-technique")
    classeur = _classeur(reponse)
    for feuille_attendue in ["École", "Comptes", "Cours", "Conversations", "Messages"]:
        assert feuille_attendue in classeur.sheetnames

    feuille_comptes = classeur["Comptes"]
    # En-tête + 4 comptes (2 admins, 1 prof, 1 élève).
    assert feuille_comptes.max_row == 5

    feuille_messages = classeur["Messages"]
    assert feuille_messages.max_row == 2
    assert feuille_messages.cell(row=2, column=4).value == "Bonjour tout le monde"


def test_supprimer_donnees_garde_ecole_et_1er_admin(client, scenario, db_session):
    ecole_id = scenario["ecole"].id
    reponse = client.delete(f"/ecoles/{ecole_id}/donnees")
    assert reponse.status_code == 204

    # École toujours là, avec son nom.
    ecole = client.get(f"/ecoles/{ecole_id}").json()
    assert ecole["nom"] == "Contretemps Test"

    from comptes.models import Compte
    from cours.models import Cours

    comptes_restants = db_session.query(Compte).filter(Compte.ecole_id == ecole_id).all()
    assert len(comptes_restants) == 1
    assert comptes_restants[0].id == scenario["admin1"].id

    assert db_session.query(Cours).filter(Cours.ecole_id == ecole_id).count() == 0


def test_restaurer_recharge_les_donnees_supprimees(client, scenario, db_session):
    ecole_id = scenario["ecole"].id
    sauvegarde = client.get(f"/ecoles/{ecole_id}/export-technique").content

    client.delete(f"/ecoles/{ecole_id}/donnees")

    from comptes.models import Compte

    assert db_session.query(Compte).filter(Compte.ecole_id == ecole_id).count() == 1

    reponse = client.post(
        f"/ecoles/{ecole_id}/restaurer",
        files={"fichier": ("backup.xlsx", sauvegarde, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert reponse.status_code == 204

    # Tout est revenu, MÊMES ids qu'avant (les références internes du
    # fichier — ex. un message vers sa conversation — restent valides).
    comptes_restaures = db_session.query(Compte).filter(Compte.ecole_id == ecole_id).all()
    assert {c.id for c in comptes_restaures} == {
        scenario["admin1"].id, scenario["admin2"].id, scenario["eleve"].id, scenario["prof"].id
    }

    from messagerie.models import Message

    messages = db_session.query(Message).filter(Message.conversation_id == scenario["conversation"].id).all()
    assert len(messages) == 1
    assert messages[0].contenu == "Bonjour tout le monde"


def test_restaurer_fichier_invalide_refuse(client, scenario):
    reponse = client.post(
        f"/ecoles/{scenario['ecole'].id}/restaurer",
        files={"fichier": ("pas_un_xlsx.xlsx", b"ceci n'est pas un excel", "application/octet-stream")},
    )
    assert reponse.status_code == 400


def test_restaurer_echec_ne_perd_pas_les_donnees_existantes(client, scenario, db_session):
    """Bug réel trouvé en test manuel : `vider()` validait (commit) en
    interne — un échec de la réinsertion plus loin laissait la base VIDÉE
    sans être restaurée (aucun rollback possible, déjà validé). Voir
    backup_technique.vider(..., commit=False) appelé depuis restaurer()."""
    ecole_id = scenario["ecole"].id
    # Fichier valide en apparence mais dont une ligne de la feuille
    # "Messages" viole une contrainte NOT NULL (expediteur_id, entier SANS
    # valeur par défaut — PAS une colonne texte : elles sont maintenant
    # tolérées si vides, voir _valeur_restauree et
    # test_video_sans_fichier_survit_a_une_restauration ci-dessous ; PAS
    # non plus une colonne AVEC valeur par défaut ORM, ex. Cours.ordre,
    # que SQLAlchemy substitue silencieusement même reçue à `None`) —
    # échoue au moment de la réinsertion, PAS avant.
    sauvegarde = client.get(f"/ecoles/{ecole_id}/export-technique").content
    classeur = openpyxl.load_workbook(io.BytesIO(sauvegarde))
    feuille_messages = classeur["Messages"]
    colonne_expediteur = [c.value for c in feuille_messages[1]].index("expediteur_id") + 1
    feuille_messages.cell(row=2, column=colonne_expediteur).value = None
    tampon = io.BytesIO()
    classeur.save(tampon)

    reponse = client.post(
        f"/ecoles/{ecole_id}/restaurer",
        files={"fichier": ("corrompu.xlsx", tampon.getvalue(), "application/octet-stream")},
    )
    assert reponse.status_code == 400

    from comptes.models import Compte
    from cours.models import Cours

    db_session.rollback()  # même session que le test, resynchronise après le rollback serveur
    assert db_session.query(Compte).filter(Compte.ecole_id == ecole_id).count() == 4
    assert db_session.query(Cours).filter(Cours.ecole_id == ecole_id).count() == 1


def test_video_sans_fichier_survit_a_une_restauration(client, db_session):
    """Une vidéo "pas encore uploadée" a `lien_fichier=""` (NOT NULL, voir
    videos/models.py) — openpyxl relit une cellule vide comme `None`, pas
    `""` : sans repli dans `_valeur_restauree`, la réinsertion violait la
    contrainte NOT NULL (trouvé en test manuel, données de seed réelles)."""
    from comptes import Comptes
    from cours import CoursService
    from ecoles.models import Ecole
    from videos.models import Video

    comptes = Comptes()
    cours_service = CoursService()
    ecole = Ecole(
        id=2, nom="Sans Fichier", code_postal="83000",
        code_acces_admin="A", code_acces_prof="P", code_acces_eleve="E",
    )
    db_session.add(ecole)
    db_session.commit()
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="A", prenom="B")
    cours = cours_service.create(db_session, ecole_id=ecole.id, nom="Éveil")
    db_session.add(Video(cours_id=cours.id, nom="Sans fichier", lien_fichier="", uploaded_by=admin.id))
    db_session.commit()

    sauvegarde = client.get(f"/ecoles/{ecole.id}/export-technique").content
    reponse = client.post(
        f"/ecoles/{ecole.id}/restaurer",
        files={"fichier": ("backup.xlsx", sauvegarde, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
    )
    assert reponse.status_code == 204

    video_restauree = db_session.query(Video).filter(Video.cours_id == cours.id).one()
    assert video_restauree.lien_fichier == ""


def test_programmer_sauvegarde(client, scenario):
    ecole_id = scenario["ecole"].id
    reponse = client.put(
        f"/ecoles/{ecole_id}/sauvegarde-programmee",
        json={"active": True, "periodicite": "semaine", "jour_semaine": 2, "heure": "03:00"},
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert corps["sauvegarde_active"] is True
    assert corps["sauvegarde_periodicite"] == "semaine"
    assert corps["sauvegarde_jour_semaine"] == 2
    assert corps["sauvegarde_heure"] == "03:00"

    # Toujours là en relisant l'école (voir spec utilisateur : partagé
    # entre admins/appareils, en base, pas en localStorage).
    assert client.get(f"/ecoles/{ecole_id}").json()["sauvegarde_active"] is True


def test_lister_sauvegardes_vide_par_defaut(client, scenario, _nettoyage_dossier):
    ecole_id = scenario["ecole"].id
    _nettoyage_dossier.append(DOSSIER_SAUVEGARDES / str(ecole_id))
    reponse = client.get(f"/ecoles/{ecole_id}/sauvegardes")
    assert reponse.status_code == 200
    assert reponse.json() == []


XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _roles_par_compte(db_session, ecole_id):
    from comptes import roles
    from comptes.models import Compte

    db_session.expire_all()
    return {
        c.id: roles.noms_roles(c)
        for c in db_session.query(Compte).filter(Compte.ecole_id == ecole_id).all()
    }


def test_supprimer_donnees_garde_les_roles_de_l_admin_conserve(client, scenario, db_session):
    """Les rôles vivent dans leur propre table (§6.3bis) : l'admin conservé
    doit garder les siens, sinon il perdrait ses droits sur l'école."""
    ecole_id = scenario["ecole"].id
    client.delete(f"/ecoles/{ecole_id}/donnees")
    assert _roles_par_compte(db_session, ecole_id) == {scenario["admin1"].id: ["admin", "owner"]}


def test_restaurer_retrouve_les_roles(client, scenario, db_session):
    ecole_id = scenario["ecole"].id
    avant = _roles_par_compte(db_session, ecole_id)
    sauvegarde = client.get(f"/ecoles/{ecole_id}/export-technique").content
    client.delete(f"/ecoles/{ecole_id}/donnees")
    client.post(f"/ecoles/{ecole_id}/restaurer", files={"fichier": ("b.xlsx", sauvegarde, XLSX)})
    assert _roles_par_compte(db_session, ecole_id) == avant


def test_restaurer_une_sauvegarde_d_avant_les_roles_cumulables(client, scenario, db_session):
    """Un fichier sauvegardé avant le 2026-09-21 a une colonne "role" dans
    l'onglet Comptes et pas d'onglet RolesComptes : il doit toujours se
    restaurer, avec la même conversion que la migration (Owner = le plus
    ancien admin)."""
    ecole_id = scenario["ecole"].id
    classeur = openpyxl.load_workbook(
        io.BytesIO(client.get(f"/ecoles/{ecole_id}/export-technique").content)
    )
    ancien_role = {
        scenario["admin1"].id: "admin", scenario["admin2"].id: "admin",
        scenario["prof"].id: "professeur", scenario["eleve"].id: "eleve",
    }
    feuille = classeur["Comptes"]
    colonne_role = feuille.max_column + 1
    feuille.cell(row=1, column=colonne_role, value="role")
    for ligne in range(2, feuille.max_row + 1):
        compte_id = feuille.cell(row=ligne, column=1).value
        feuille.cell(row=ligne, column=colonne_role, value=ancien_role[compte_id])
    del classeur["RolesComptes"]
    fichier = io.BytesIO()
    classeur.save(fichier)

    client.delete(f"/ecoles/{ecole_id}/donnees")
    reponse = client.post(
        f"/ecoles/{ecole_id}/restaurer", files={"fichier": ("ancien.xlsx", fichier.getvalue(), XLSX)}
    )
    assert reponse.status_code == 204
    assert _roles_par_compte(db_session, ecole_id) == {
        scenario["admin1"].id: ["admin", "owner"],
        scenario["admin2"].id: ["admin"],
        scenario["prof"].id: ["professeur"],
        scenario["eleve"].id: ["eleve"],
    }
