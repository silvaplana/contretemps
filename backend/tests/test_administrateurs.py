"""Tableau des administrateurs (spec §2.4) : lister, créer, modifier,
supprimer — avec les vraies vérifications de droits (`rbac_reel`)."""

import pytest
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
        db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana", code_recuperation="rex"
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
    return {rbac.ENTETE_COMPTE: str(compte.id)}


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
        assert lignes[ecole["admin"].id]["code_recuperation_defini"] is True
        assert all("code_recuperation" not in l for l in lignes.values())


@pytest.mark.parametrize("qui", ["prof", "eleve", "owner_voisin"])
def test_les_non_admins_ne_voient_pas_la_liste(client, ecole, qui):
    reponse = client.get(f"/ecoles/{ecole['ecole'].id}/administrateurs", headers=_en_tant_que(ecole[qui]))
    assert reponse.status_code == 403


# --- Créer ---


def test_owner_cree_un_nouvel_admin(client, db_session, ecole):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"nom": "Neuf", "prenom": "Admin", "email": "n@x.fr", "code_recuperation": "chat"},
        headers=_en_tant_que(ecole["owner"]),
    )
    assert reponse.status_code == 201
    corps = reponse.json()
    assert corps["est_owner"] is False and corps["est_prof"] is False
    assert _roles(db_session, type("C", (), {"id": corps["id"]})) == ["admin"]


def test_owner_cree_directement_un_owner(client, ecole):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"nom": "Neuf", "prenom": "Owner", "code_recuperation": "chat", "owner": True},
        headers=_en_tant_que(ecole["owner"]),
    )
    assert reponse.json()["est_owner"] is True


def test_owner_promeut_un_professeur_qui_reste_professeur(client, db_session, ecole):
    reponse = client.post(
        f"/ecoles/{ecole['ecole'].id}/administrateurs",
        json={"professeur_id": ecole["prof"].id, "code_recuperation": "chat"},
        headers=_en_tant_que(ecole["owner"]),
    )
    assert reponse.status_code == 201
    assert reponse.json()["est_prof"] is True
    assert _roles(db_session, ecole["prof"]) == ["admin", "professeur"]


def test_promouvoir_refuse_un_non_professeur_ou_un_professeur_d_une_autre_ecole(client, ecole):
    for cible in ["eleve", "prof_voisin"]:
        reponse = client.post(
            f"/ecoles/{ecole['ecole'].id}/administrateurs",
            json={"professeur_id": ecole[cible].id, "code_recuperation": "chat"},
            headers=_en_tant_que(ecole["owner"]),
        )
        assert reponse.status_code == 404, cible


def test_promouvoir_deux_fois_refuse(client, ecole):
    corps = {"professeur_id": ecole["prof"].id, "code_recuperation": "chat"}
    url = f"/ecoles/{ecole['ecole'].id}/administrateurs"
    client.post(url, json=corps, headers=_en_tant_que(ecole["owner"]))
    assert client.post(url, json=corps, headers=_en_tant_que(ecole["owner"])).status_code == 409


@pytest.mark.parametrize(
    "corps",
    [
        {"nom": "Sans", "code_recuperation": "chat"},  # prénom manquant
        {"nom": "X", "prenom": "Y", "code_recuperation": ""},  # code vide
        {"professeur_id": 1, "nom": "X", "code_recuperation": "chat"},  # mélange des 2 façons
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
        json={"nom": "X", "prenom": "Y", "code_recuperation": "chat"},
        headers=_en_tant_que(ecole["admin"]),
    )
    assert reponse.status_code == 403


# --- Modifier ---


def test_owner_modifie_un_admin_pur(client, db_session, ecole):
    reponse = client.put(
        f"/administrateurs/{ecole['admin'].id}",
        json={"prenom": "Anna", "code_recuperation": "felix"},
        headers=_en_tant_que(ecole["owner"]),
    )
    assert reponse.status_code == 200
    assert reponse.json()["prenom"] == "Anna"
    db_session.refresh(ecole["admin"])
    assert ecole["admin"].code_recuperation == "felix"


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
    # Mais son code de récupération, si.
    assert client.put(url, json={"code_recuperation": "chat"}, headers=entetes).status_code == 200


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


def test_owner_exige_admin_et_eleve_non_cumulable(db_session, ecole):
    with pytest.raises(RegleRoles):
        Comptes().ajouter_role(db_session, ecole["prof"], roles.OWNER)
    with pytest.raises(RegleRoles):
        Comptes().ajouter_role(db_session, ecole["eleve"], roles.ADMIN)


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
