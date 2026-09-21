"""RBAC : require_admin / require_owner (voir spec/SPEC.md §2.4 et
backend/src/comptes/rbac.py). Ici les vraies vérifications sont ACTIVES
(`rbac_reel`, voir conftest.py), contrairement au reste de la suite."""

import pytest
from comptes import Comptes, RoleCompte, rbac, roles
from cours import CoursService
from ecoles import Ecoles
from eleves import Eleves
from fastapi import HTTPException

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def ecole_complete(db_session):
    """Une école avec un compte de chaque sorte, plus une école voisine
    avec son propre admin."""
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    voisine = Ecoles().create(db_session, nom="Voisine", code_postal="83000")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    prof_admin = comptes.create(
        db_session, ecole_id=ecole.id, role="professeur", nom="Pesenti", prenom="Marie"
    )
    prof_admin.roles.append(RoleCompte(role=roles.ADMIN))
    db_session.commit()
    eleve, _ = Eleves(comptes=comptes).create(db_session, ecole_id=ecole.id, nom="Perrin", prenom="Léon")
    contact = Eleves(comptes=comptes).ajouter_contact(
        db_session, eleve.id, nom="Perrin", prenom="Alice", lien="Mère"
    )
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Éveil")
    admin_voisin = comptes.create(db_session, ecole_id=voisine.id, role="admin", nom="Z", prenom="W")
    return {
        "ecole": ecole, "owner": owner, "admin": admin, "prof": prof, "prof_admin": prof_admin,
        "eleve": eleve, "contact": contact, "cours": cours, "admin_voisin": admin_voisin,
    }


def _en_tant_que(compte):
    return {rbac.ENTETE_COMPTE: str(compte.id)}


# Une route protégée par module, de quoi vérifier que chacun est branché.
# (méthode, chemin, corps JSON) — construits à partir de l'école de test.
def _routes_admin(e):
    ecole_id, eleve_id, cours_id = e["ecole"].id, e["eleve"].id, e["cours"].id
    return [
        ("post", f"/cours?ecole_id={ecole_id}", {"nom": "Jazz"}),
        ("put", f"/cours/{cours_id}", {"salle": "Salle 2"}),
        ("post", f"/cours/{cours_id}/eleves/{eleve_id}", None),
        ("post", f"/eleves?ecole_id={ecole_id}", {"nom": "Nouveau", "prenom": "Élève"}),
        ("put", f"/eleves/{eleve_id}", {"allergies": "Aucune"}),
        ("put", f"/contacts/{e['contact'].id}", {"telephone": "0600000000"}),
        ("post", f"/profs?ecole_id={ecole_id}", {"nom": "Nouveau", "prenom": "Prof"}),
        ("put", f"/ecoles/{ecole_id}", {"nom": "Contretemps"}),
        ("get", f"/ecoles/{ecole_id}", None),
        ("get", f"/ecoles/{ecole_id}/export", None),
        ("get", f"/ecoles/{ecole_id}/videos/usage", None),
        ("post", f"/conversations?ecole_id={ecole_id}", {"nom": "Groupe"}),
        ("put", f"/comptes/{e['owner'].id}", {"telephone": "0600000000"}),
    ]


def _appeler(client, methode, chemin, corps, entetes=None):
    kwargs = {"headers": entetes or {}}
    if corps is not None:
        kwargs["json"] = corps
    return getattr(client, methode)(chemin, **kwargs)


@pytest.mark.parametrize("qui", ["owner", "admin", "prof_admin"])
def test_les_admins_de_l_ecole_passent(client, ecole_complete, qui):
    for methode, chemin, corps in _routes_admin(ecole_complete):
        reponse = _appeler(client, methode, chemin, corps, _en_tant_que(ecole_complete[qui]))
        assert reponse.status_code < 400, (qui, methode, chemin, reponse.status_code, reponse.text)


@pytest.mark.parametrize("qui", ["prof", "eleve", "admin_voisin"])
def test_les_autres_sont_refuses(client, ecole_complete, qui):
    """Un prof, un élève, et un admin d'une AUTRE école (écoles étanches)."""
    for methode, chemin, corps in _routes_admin(ecole_complete):
        reponse = _appeler(client, methode, chemin, corps, _en_tant_que(ecole_complete[qui]))
        assert reponse.status_code == 403, (qui, methode, chemin, reponse.status_code)


def test_sans_identite_ou_identite_inconnue_401(client, ecole_complete):
    for methode, chemin, corps in _routes_admin(ecole_complete):
        assert _appeler(client, methode, chemin, corps).status_code == 401, chemin
        inconnu = {rbac.ENTETE_COMPTE: "999999"}
        assert _appeler(client, methode, chemin, corps, inconnu).status_code == 401, chemin


def test_ressource_inexistante_404_pas_403(client, ecole_complete):
    """Un admin qui vise un id qui n'existe pas reçoit 404 : un 403 dirait
    à tort "ça existe, mais pas pour toi"."""
    reponse = client.put("/cours/999999", json={"salle": "X"}, headers=_en_tant_que(ecole_complete["admin"]))
    assert reponse.status_code == 404


def test_les_routes_partagees_restent_ouvertes(client, ecole_complete):
    """Hors onglet Admin (Présence, Chorégraphie, Vidéo, Messagerie...),
    rien ne change dans cette étape : pas d'en-tête requis."""
    ecole_id = ecole_complete["ecole"].id
    assert client.get(f"/cours?ecole_id={ecole_id}").status_code == 200
    assert client.get(f"/eleves?ecole_id={ecole_id}").status_code == 200
    assert client.get(f"/cours/{ecole_complete['cours'].id}/seances").status_code == 200


# --- Fuites corrigées (codes d'accès, code de récupération) ---


def test_la_liste_publique_des_ecoles_ne_donne_plus_les_codes(client, ecole_complete):
    ecoles = client.get("/ecoles").json()
    assert ecoles
    for ecole in ecoles:
        assert set(ecole) == {"id", "nom", "code_postal"}


def test_les_codes_d_acces_restent_lisibles_par_un_admin(client, ecole_complete):
    ecole_id = ecole_complete["ecole"].id
    corps = client.get(f"/ecoles/{ecole_id}", headers=_en_tant_que(ecole_complete["admin"])).json()
    assert corps["code_acces_admin"] == ecole_complete["ecole"].code_acces_admin


def test_le_code_de_recuperation_n_est_jamais_renvoye(client, db_session, ecole_complete):
    owner = ecole_complete["owner"]
    owner.code_recuperation = "rex"
    db_session.commit()
    ecole_id = ecole_complete["ecole"].id
    for corps in [
        client.get(f"/comptes/{owner.id}").json(),
        *client.get("/comptes", params={"ecole_id": ecole_id, "role": "admin"}).json(),
    ]:
        assert "code_recuperation" not in corps
    assert client.get(f"/comptes/{owner.id}").json()["code_recuperation_defini"] is True


# --- require_owner (pas encore de route, voir étape 3 §2.4) ---


def test_require_owner(ecole_complete):
    ecole_id = ecole_complete["ecole"].id
    rbac.require_owner(ecole_complete["owner"], ecole_id)
    for qui in ["admin", "prof_admin", "prof", "admin_voisin"]:
        with pytest.raises(HTTPException) as refus:
            rbac.require_owner(ecole_complete[qui], ecole_id)
        assert refus.value.status_code == 403
