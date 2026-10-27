"""Tableau des administrateurs (spec §2.4) : lister, créer, modifier,
supprimer — avec les vraies vérifications de droits (`rbac_reel`)."""

import pytest
from conftest import entetes_session
from comptes import Comptes, RegleRoles, RoleCompte, rbac, roles
from ecoles import Ecoles
from messagerie import Conversations, Messages
from messagerie.models import ConversationMembre, Message
from cours import CoursService
from notifications.models import PushSubscription

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def ecole(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    voisine = Ecoles().create(db_session, nom="Voisine", code_postal="83000")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    admin = comptes.create(
        db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana"
    )
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Léon")
    prof_voisin = comptes.create(db_session, ecole_id=voisine.id, role="professeur", nom="Z", prenom="W")
    owner_voisin = comptes.create(db_session, ecole_id=voisine.id, role="admin", nom="V", prenom="U")
    return {
        "ecole": ecole, "owner": owner, "admin": admin, "prof": prof, "eleve": eleve,
        "prof_voisin": prof_voisin, "owner_voisin": owner_voisin,
    }


def _en_tant_que(compte):
    return entetes_session(compte)


def _roles(db_session, compte):
    db_session.expire_all()
    return roles.noms_roles(Comptes().get(db_session, compte.id))


# --- Lister ---


def test_tout_admin_voit_la_liste_sans_code_de_recuperation(client, ecole):
    for qui in ["owner", "admin"]:
        reponse = client.get(
            f"/ecoles/{ecole['ecole'].id}/administrateurs", headers=_en_tant_que(ecole[qui])
        )
        assert reponse.status_code == 200
        lignes = {l["id"]: l for l in reponse.json()}
        assert set(lignes) == {ecole["owner"].id, ecole["admin"].id}
        assert lignes[ecole["owner"].id]["est_owner"] is True
        assert lignes[ecole["admin"].id]["est_owner"] is False


@pytest.mark.parametrize("qui", ["prof", "eleve", "owner_voisin"])
def test_les_non_admins_ne_voient_pas_la_liste(client, ecole, qui):
    reponse = client.get(f"/ecoles/{ecole['ecole'].id}/administrateurs", headers=_en_tant_que(ecole[qui]))
    assert reponse.status_code == 403


# --- Créer ---


def test_owner_cree_un_nouvel_admin(client, db_session, ecole):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"nom": "Neuf", "prenom": "Admin", "email": "n@x.fr"},
        headers=_en_tant_que(ecole["owner"]),
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["est_owner"] is False and corps["est_prof"] is False
    assert _roles(db_session, type("C", (), {"id": corps["id"]})) == ["admin"]


def test_owner_cree_directement_un_owner(client, ecole):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"nom": "Neuf", "prenom": "Owner", "owner": True},
        headers=_en_tant_que(ecole["owner"]),
    )
    assert reponse.json()["est_owner"] is True


def test_owner_promeut_un_professeur_qui_reste_professeur(client, db_session, ecole):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"compte_id": ecole["prof"].id},
        headers=_en_tant_que(ecole["owner"]),
    )
    assert reponse.status_code == 201
    assert reponse.json()["est_prof"] is True
    assert _roles(db_session, ecole["prof"]) == ["admin", "professeur"]


def test_promouvoir_refuse_un_compte_d_une_autre_ecole(client, ecole):
    for cible in ["prof_voisin", "owner_voisin"]:
        reponse = client.post(
            f"/ecoles/{ecole['ecole'].id}/administrateurs",
            json={"compte_id": ecole[cible].id},
            headers=_en_tant_que(ecole["owner"]),
        )
        assert reponse.status_code == 404, cible


def test_promouvoir_deux_fois_refuse(client, ecole):
    corps = {"compte_id": ecole["prof"].id}
    url = f"/ecoles/{ecole['ecole'].id}/administrateurs"
    client.post(url, json=corps, headers=_en_tant_que(ecole["owner"]))
    assert client.post(url, json=corps, headers=_en_tant_que(ecole["owner"])).status_code == 409


@pytest.mark.parametrize(
    "corps",
    [
        {"nom": "Sans"},  # prénom manquant
        {"compte_id": 1, "nom": "X"},  # mélange des 2 façons
    ],
)
def test_creation_invalide_422(client, ecole, corps):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs", json=corps, headers=_en_tant_que(ecole["owner"])
    )
    assert reponse.status_code == 422


def test_un_admin_non_owner_ne_cree_pas_d_admin(client, ecole):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"nom": "X", "prenom": "Y"},
        headers=_en_tant_que(ecole["admin"]),
    )
    assert reponse.status_code == 403


# --- Modifier ---


def test_owner_modifie_un_admin_pur(client, db_session, ecole):
    reponse = client.put(
        f"/administrateurs/{ecole['admin'].id}",
        json={"prenom": "Anna", "email": "anna@x.fr"},
        headers=_en_tant_que(ecole["owner"]),
    )
    assert reponse.status_code == 200
    assert reponse.json()["prenom"] == "Anna"
    db_session.refresh(ecole["admin"])
    assert ecole["admin"].email == "anna@x.fr"


def test_owner_donne_puis_retire_le_statut_owner(client, db_session, ecole):
    url = f"/administrateurs/{ecole['admin'].id}"
    entetes = _en_tant_que(ecole["owner"])
    assert client.put(url, json={"owner": True}, headers=entetes).json()["est_owner"] is True
    assert client.put(url, json={"owner": False}, headers=entetes).json()["est_owner"] is False
    assert _roles(db_session, ecole["admin"]) == ["admin"]


def test_nom_d_un_professeur_admin_se_modifie_ailleurs(client, db_session, ecole):
    ecole["prof"].roles.append(RoleCompte(role=roles.ADMIN))
    db_session.commit()
    url = f"/administrateurs/{ecole['prof'].id}"
    entetes = _en_tant_que(ecole["owner"])
    assert client.put(url, json={"nom": "Autre"}, headers=entetes).status_code == 409
    # Mais son statut d'administrateur principal, si.
    assert client.put(url, json={"owner": True}, headers=entetes).status_code == 200


def test_un_owner_ne_touche_pas_a_sa_propre_ligne(client, ecole):
    url = f"/administrateurs/{ecole['owner'].id}"
    entetes = _en_tant_que(ecole["owner"])
    assert client.put(url, json={"owner": False}, headers=entetes).status_code == 403
    assert client.delete(url, headers=entetes).status_code == 403


def test_un_admin_non_owner_ne_modifie_rien(client, ecole):
    reponse = client.put(
        f"/administrateurs/{ecole['owner'].id}", json={"prenom": "X"}, headers=_en_tant_que(ecole["admin"])
    )
    assert reponse.status_code == 403


def test_un_owner_d_une_autre_ecole_ne_modifie_rien(client, ecole):
    reponse = client.put(
        f"/administrateurs/{ecole['admin'].id}", json={"prenom": "X"},
        headers=_en_tant_que(ecole["owner_voisin"]),
    )
    assert reponse.status_code == 403


def test_viser_un_non_admin_404(client, ecole):
    reponse = client.put(
        f"/administrateurs/{ecole['prof'].id}", json={"prenom": "X"}, headers=_en_tant_que(ecole["owner"])
    )
    assert reponse.status_code == 404


# --- Supprimer ---


def test_supprimer_un_professeur_admin_lui_laisse_son_role_de_professeur(client, db_session, ecole):
    ecole["prof"].roles.append(RoleCompte(role=roles.ADMIN))
    ecole["prof"].roles.append(RoleCompte(role=roles.OWNER))
    db_session.commit()
    reponse = client.delete(f"/administrateurs/{ecole['prof'].id}", headers=_en_tant_que(ecole["owner"]))
    assert reponse.status_code == 204
    assert _roles(db_session, ecole["prof"]) == ["professeur"]


def test_supprimer_un_admin_pur_garde_son_historique(client, db_session, ecole):
    """Compte, appartenances et abonnements supprimés ; ses messages
    restent (décision utilisateur du 2026-09-21)."""
    comptes = Comptes()
    conversations = Conversations(comptes=comptes, cours=CoursService())
    conv = conversations.create_groupe(
        db_session, ecole["ecole"].id, "Équipe", [("compte", ecole["admin"].id)]
    )
    Messages(conversations=conversations).envoyer(db_session, conv.id, ecole["admin"].id, "Bonjour")
    db_session.add(PushSubscription(compte_id=ecole["admin"].id, endpoint="https://x", cle_p256dh="a", cle_auth="b"))
    db_session.commit()
    admin_id = ecole["admin"].id

    reponse = client.delete(f"/administrateurs/{admin_id}", headers=_en_tant_que(ecole["owner"]))
    assert reponse.status_code == 204

    db_session.expire_all()
    assert comptes.get(db_session, admin_id) is None
    assert db_session.query(ConversationMembre).filter_by(membre_type="compte", membre_id=admin_id).count() == 0
    assert db_session.query(PushSubscription).filter_by(compte_id=admin_id).count() == 0
    assert db_session.query(RoleCompte).filter_by(compte_id=admin_id).count() == 0
    messages = db_session.query(Message).filter_by(expediteur_id=admin_id).all()
    assert [m.contenu for m in messages] == ["Bonjour"]


# --- Règles des rôles, au niveau du service ---


def test_retirer_le_dernier_owner_refuse(db_session, ecole):
    with pytest.raises(RegleRoles):
        Comptes().retirer_role(db_session, ecole["owner"], roles.OWNER)
    with pytest.raises(RegleRoles):
        Comptes().retirer_role(db_session, ecole["owner"], roles.ADMIN)


def test_owner_exige_admin_et_tous_les_roles_se_cumulent(db_session, ecole):
    with pytest.raises(RegleRoles):
        Comptes().ajouter_role(db_session, ecole["prof"], roles.OWNER)
    # Une personne = une fiche (spec/core.md §4) : élève, professeur et
    # administrateur à la fois.
    Comptes().ajouter_role(db_session, ecole["eleve"], roles.PROFESSEUR)
    Comptes().ajouter_role(db_session, ecole["eleve"], roles.ADMIN)
    assert roles.noms_roles(ecole["eleve"]) == ["admin", "professeur", "eleve"]


def test_supprimer_depuis_admin_profs_le_dernier_owner_refuse(client, db_session):
    """Un professeur-admin Owner supprimé depuis Admin > Profs : refusé
    s'il est le dernier Owner, l'école ne doit jamais en manquer."""
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Solo", code_postal="83000")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Seul", prenom="Owner")
    comptes.ajouter_role(db_session, prof, roles.ADMIN)
    comptes.ajouter_role(db_session, prof, roles.OWNER)
    # Admin créé APRÈS : l'école a déjà un Owner, il n'en devient pas un.
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Autre", prenom="Admin")
    assert not roles.is_owner(admin)

    reponse = client.delete(f"/profs/{prof.id}", headers=_en_tant_que(admin))
    assert reponse.status_code == 409
    assert comptes.get(db_session, prof.id) is not None


# --- Trésorier (notes de frais §6) ---


def test_owner_coche_tresorier_y_compris_pour_lui_meme(client, ecole, db_session):
    for cible in ("admin", "owner"):
        reponse = client.put(
            f"/administrateurs/{ecole[cible].id}", json={"tresorier": True}, headers=_en_tant_que(ecole["owner"])
        )
        assert reponse.status_code == 200, reponse.text
        assert reponse.json()["est_tresorier"] is True
    # Sur sa propre ligne, seule la case Trésorier se modifie.
    reponse = client.put(f"/administrateurs/{ecole['owner'].id}", json={"nom": "X"}, headers=_en_tant_que(ecole["owner"]))
    assert reponse.status_code == 403


def test_un_simple_admin_ne_nomme_pas_de_tresorier(client, ecole):
    reponse = client.put(f"/administrateurs/{ecole['owner'].id}", json={"tresorier": True}, headers=_en_tant_que(ecole["admin"]))
    assert reponse.status_code == 403


def test_tresorier_toujours_admin(db_session, ecole):
    comptes = Comptes()
    with pytest.raises(RegleRoles):
        comptes.ajouter_role(db_session, ecole["prof"], roles.TRESORIER)
    comptes.ajouter_role(db_session, ecole["admin"], roles.TRESORIER)
    assert roles.role_principal(r.role for r in ecole["admin"].roles) == roles.ADMIN
    # Retirer admin retire aussi trésorier.
    prof_admin = ecole["prof"]
    comptes.ajouter_role(db_session, prof_admin, roles.ADMIN)
    comptes.ajouter_role(db_session, prof_admin, roles.TRESORIER)
    comptes.retirer_role(db_session, prof_admin, roles.ADMIN)
    assert _roles(db_session, prof_admin) == ["professeur"]


# --- Bureau (spec/core.md §6.4) : fonctions sans droits ---


def test_owner_donne_les_fonctions_du_bureau_y_compris_a_lui_meme(client, ecole):
    for cible, fonctions in (("admin", ["secretary"]), ("owner", ["president", "treasurer"])):
        reponse = client.put(
            f"/administrateurs/{ecole[cible].id}", json={"bureau_functions": fonctions}, headers=_en_tant_que(ecole["owner"])
        )
        assert reponse.status_code == 200, reponse.text
        assert reponse.json()["bureau_functions"] == fonctions
    liste = client.get(f"/ecoles/{ecole['ecole'].id}/administrateurs", headers=_en_tant_que(ecole["admin"])).json()
    assert {a["id"]: a["bureau_functions"] for a in liste}[ecole["admin"].id] == ["secretary"]


def test_fonction_tresorier_ne_donne_pas_le_financier(client, ecole):
    reponse = client.put(
        f"/administrateurs/{ecole['admin'].id}", json={"bureau_functions": ["treasurer"]}, headers=_en_tant_que(ecole["owner"])
    )
    assert reponse.json()["est_tresorier"] is False


def test_fonctions_du_bureau_controlees(client, ecole):
    entetes = _en_tant_que(ecole["owner"])
    url = f"/administrateurs/{ecole['admin'].id}"
    assert client.put(url, json={"bureau_functions": ["roi"]}, headers=entetes).status_code == 422
    # Doublons retirés, ordre fixe (président d'abord).
    reponse = client.put(url, json={"bureau_functions": ["secretary", "president", "secretary"]}, headers=entetes)
    assert reponse.json()["bureau_functions"] == ["president", "secretary"]
    assert client.put(url, json={"bureau_functions": []}, headers=entetes).json()["bureau_functions"] == []


def test_un_simple_admin_change_les_groupes_mais_pas_le_financier(client, ecole):
    """Groupes (spec/core.md §5.1) : tout admin les change, sauf ceux qui
    donnent un droit (🔒 Accès au Financier : administrateur principal)."""
    url = f"/administrateurs/{ecole['owner'].id}"
    entetes = _en_tant_que(ecole["admin"])
    reponse = client.put(url, json={"bureau_functions": ["president"], "prof": True}, headers=entetes)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["bureau_functions"] == ["president"] and reponse.json()["est_prof"] is True
    assert client.put(url, json={"tresorier": True}, headers=entetes).status_code == 403
    assert client.put(url, json={"bureau_functions": [], "tresorier": True}, headers=entetes).status_code == 403
    assert client.put(url, json={"prof": True}, headers=_en_tant_que(ecole["owner_voisin"])).status_code == 403
    assert client.put(url, json={"prof": True}, headers=_en_tant_que(ecole["prof"])).status_code == 403


def test_groupes_faits_a_la_main(client, ecole):
    ecole_id = ecole["ecole"].id
    entetes = _en_tant_que(ecole["admin"])
    benevoles = client.post(f"/ecoles/{ecole_id}/groupes", json={"name": "  Bénévoles "}, headers=entetes)
    assert benevoles.status_code == 201, benevoles.text
    assert benevoles.json()["name"] == "Bénévoles"
    assert client.post(f"/ecoles/{ecole_id}/groupes", json={"name": "bénévoles"}, headers=entetes).status_code == 409
    assert client.post(f"/ecoles/{ecole_id}/groupes", json={"name": " "}, headers=entetes).status_code == 409
    assert client.post(f"/ecoles/{ecole_id}/groupes", json={"name": "X"}, headers=_en_tant_que(ecole["prof"])).status_code == 403
    assert client.get(f"/ecoles/{ecole_id}/groupes", headers=entetes).json() == [benevoles.json()]

    gid = benevoles.json()["id"]
    reponse = client.put(f"/administrateurs/{ecole['admin'].id}", json={"groups": [gid]}, headers=entetes)
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["groups"] == [gid]
    # Un groupe d'une autre école est refusé.
    autre = client.post(f"/ecoles/{ecole['owner_voisin'].ecole_id}/groupes", json={"name": "Z"}, headers=_en_tant_que(ecole["owner_voisin"])).json()
    assert client.put(f"/administrateurs/{ecole['admin'].id}", json={"groups": [autre["id"]]}, headers=entetes).status_code == 409
    assert client.put(f"/administrateurs/{ecole['admin'].id}", json={"groups": []}, headers=entetes).json()["groups"] == []
