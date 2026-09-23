"""Saisons, étape 3 : créer une saison (avec duplication) et éditer la
saison courante (voir spec/SPEC.md §2.6 et §5.1.1)."""

import datetime as dt

import pytest
import sqlalchemy as sa
from comptes import Comptes, RoleCompte, roles
from comptes.models import Compte
from cours import CoursService
from cours.models import Cours
from ecoles import Ecoles
from eleves import Eleves
from eleves.models import ContactEleve, ProfilEleve
from inscriptions.saison import saison_des_inscriptions
from presence.models import SeancePresence
from saisons import Saison, saison_courante_id
from saisons.portee import toutes_saisons

NOUVELLE = {"nom": "2027-2028", "date_debut": "2027-09-01", "date_fin": "2028-08-31"}


@pytest.fixture()
def ecole_en_cours(db_session):
    """Owner, professeur-admin, professeur, deux élèves de la même famille
    inscrits à un cours (avec paiement et contact), une séance."""
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    owner = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="j@x.fr")
    prof_admin = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    prof_admin.roles.append(RoleCompte(role=roles.ADMIN))
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Noir", prenom="Léa")
    eleves = Eleves(comptes=comptes)
    ana, _ = eleves.create(
        db_session, ecole_id=ecole.id, nom="Roux", prenom="Ana", email="r@x.fr",
        allergies="Arachide", statut_paiement="paye", montant_paye=300, commentaire_admin="Chèque",
    )
    leo, _ = eleves.create(db_session, ecole_id=ecole.id, nom="Roux", prenom="Léo", email="r@x.fr")
    eleves.ajouter_contact(db_session, ana.id, nom="Roux", prenom="Marc", lien="Père", telephone="06")
    service = CoursService()
    jazz = service.create(
        db_session, ecole_id=ecole.id, nom="Jazz", jour="Lundi", heure_debut="18:00", heure_fin="19:00",
        horaires_supplementaires=[{"jour": "Mercredi", "heure_debut": "14:00", "heure_fin": "15:00"}],
    )
    for p in (prof, prof_admin):
        service.ajouter_professeur(db_session, jazz.id, p.id)
    for e in (ana, leo):
        service.inscrire_eleve(db_session, jazz.id, e.id)
    db_session.add(SeancePresence(cours_id=jazz.id, date=dt.date(2027, 1, 10)))
    db_session.commit()
    return {
        "ecole": ecole, "ancienne": saison_courante_id(db_session, ecole.id), "owner": owner,
        "prof_admin": prof_admin, "prof": prof, "ana": ana, "leo": leo, "jazz": jazz,
    }


def _creer(client, ecole_id, **cases):
    return client.post(f"/ecoles/{ecole_id}/saisons", json={**NOUVELLE, **cases})


def _fiches(db_session, saison_id):
    with toutes_saisons(db_session):
        return {
            (c.prenom, tuple(roles.noms_roles(c))): c
            for c in db_session.scalars(sa.select(Compte).where(Compte.saison_id == saison_id))
        }


def test_validations(client, ecole_en_cours):
    ecole_id = ecole_en_cours["ecole"].id
    assert _creer(client, ecole_id, dupliquer_cours=True).status_code == 409
    assert _creer(client, ecole_id, dupliquer_profs=True, dupliquer_eleves=True).status_code == 409
    assert client.post(f"/ecoles/{ecole_id}/saisons", json={**NOUVELLE, "nom": "2026-2027"}).status_code == 409
    assert client.post(f"/ecoles/{ecole_id}/saisons", json={**NOUVELLE, "nom": " "}).status_code == 409
    fin_avant = {**NOUVELLE, "date_fin": "2027-08-01"}
    assert client.post(f"/ecoles/{ecole_id}/saisons", json=fin_avant).status_code == 409
    assert [s["nom"] for s in client.get(f"/ecoles/{ecole_id}/saisons").json()] == ["2026-2027"]


def test_sans_duplication_seuls_les_admins_sont_recopies(client, db_session, ecole_en_cours):
    e = ecole_en_cours
    reponse = _creer(client, e["ecole"].id)
    assert reponse.status_code == 201
    nouvelle = reponse.json()["saison"]
    assert nouvelle["courante"] is True

    saisons = client.get(f"/ecoles/{e['ecole'].id}/saisons").json()
    assert [(s["nom"], s["courante"]) for s in saisons] == [("2027-2028", True), ("2026-2027", False)]

    fiches = _fiches(db_session, nouvelle["id"])
    # L'owner le reste ; le professeur-admin devient admin pur.
    assert set(fiches) == {("Julia", ("admin", "owner")), ("Ima", ("admin",))}
    assert fiches[("Julia", ("admin", "owner"))].compte_precedent_id == e["owner"].id
    assert client.get("/cours", params={"ecole_id": e["ecole"].id}).json() == []
    # L'ancienne saison est désormais en lecture seule.
    ancienne = {"X-Saison-Id": str(e["ancienne"])}
    assert client.put(f"/cours/{e['jazz'].id}", json={"nom": "X"}, headers=ancienne).status_code == 403


def test_duplication_complete(client, db_session, ecole_en_cours):
    e = ecole_en_cours
    reponse = _creer(client, e["ecole"].id, dupliquer_profs=True, dupliquer_cours=True, dupliquer_eleves=True)
    assert reponse.status_code == 201
    saison_id = reponse.json()["saison"]["id"]

    fiches = _fiches(db_session, saison_id)
    assert set(fiches) == {
        ("Julia", ("admin", "owner")), ("Ima", ("admin", "professeur")), ("Léa", ("professeur",)),
        ("Ana", ("eleve",)), ("Léo", ("eleve",)),
    }
    ana, leo = fiches[("Ana", ("eleve",))], fiches[("Léo", ("eleve",))]
    assert ana.compte_precedent_id == e["ana"].id
    # Même famille entre frère et sœur, mais pas celle de l'ancienne saison.
    assert ana.famille_id == leo.famille_id != e["ana"].famille_id

    profil = db_session.get(ProfilEleve, ana.id)
    assert profil.allergies == "Arachide"
    assert (profil.statut_paiement, profil.montant_paye, profil.commentaire_admin) == ("en_cours", 0, None)
    contacts = db_session.scalars(sa.select(ContactEleve).where(ContactEleve.eleve_id == ana.id)).all()
    assert [(c.prenom, c.lien) for c in contacts] == [("Marc", "Père")]

    cours = client.get("/cours", params={"ecole_id": e["ecole"].id}).json()
    assert [c["nom"] for c in cours] == ["Jazz"]
    jazz = cours[0]
    assert jazz["id"] != e["jazz"].id
    assert [(h["jour"], h["heure_debut"]) for h in jazz["horaires_supplementaires"]] == [("Mercredi", "14:00")]
    profs = {p["prenom"] for p in client.get(f"/cours/{jazz['id']}/professeurs").json()}
    assert profs == {"Léa", "Ima"}
    eleves = {p["prenom"] for p in client.get(f"/cours/{jazz['id']}/eleves").json()}
    assert eleves == {"Ana", "Léo"}
    # Présences non recopiées.
    assert client.get(f"/cours/{jazz['id']}/seances").json() == []
    with toutes_saisons(db_session):
        assert db_session.scalar(sa.select(sa.func.count()).select_from(Cours)) == 2


def test_profs_et_cours_sans_eleves(client, db_session, ecole_en_cours):
    e = ecole_en_cours
    saison_id = _creer(client, e["ecole"].id, dupliquer_profs=True, dupliquer_cours=True).json()["saison"]["id"]
    assert {prenom for prenom, _ in _fiches(db_session, saison_id)} == {"Julia", "Ima", "Léa"}
    jazz = client.get("/cours", params={"ecole_id": e["ecole"].id}).json()[0]
    assert client.get(f"/cours/{jazz['id']}/eleves").json() == []
    assert len(client.get(f"/cours/{jazz['id']}/professeurs").json()) == 2


def test_un_eleve_non_recopie_ne_se_connecte_plus(client, ecole_en_cours):
    e = ecole_en_cours
    ecole = e["ecole"]
    _creer(client, ecole.id, dupliquer_profs=True, dupliquer_cours=True)
    connexion = {"ecole_id": ecole.id, "identifiant": "Ana Roux", "code": ecole.code_acces_eleve}
    assert client.post("/auth/login", json=connexion).status_code == 401
    admin = {"ecole_id": ecole.id, "identifiant": "Julia Dho", "code": ecole.code_acces_admin}
    assert client.post("/auth/login", json=admin).status_code == 200


@pytest.mark.rbac_reel
def test_l_admin_createur_recoit_sa_nouvelle_fiche(client, ecole_en_cours):
    e = ecole_en_cours
    reponse = client.post(
        f"/ecoles/{e['ecole'].id}/saisons", json=NOUVELLE, headers={"X-Compte-Id": str(e["owner"].id)}
    )
    assert reponse.status_code == 201
    nouvelle_fiche = reponse.json()["compte_id"]
    assert nouvelle_fiche not in (None, e["owner"].id)
    # Son ancienne fiche bascule vers la nouvelle.
    apres = client.get(f"/ecoles/{e['ecole'].id}/saisons", headers={"X-Compte-Id": str(e["owner"].id)})
    assert apres.status_code == 409
    assert apres.json()["detail"]["compte_id"] == nouvelle_fiche


@pytest.mark.rbac_reel
def test_un_prof_ne_cree_pas_de_saison(client, ecole_en_cours):
    e = ecole_en_cours
    reponse = client.post(f"/ecoles/{e['ecole'].id}/saisons", json=NOUVELLE, headers={"X-Compte-Id": str(e["prof"].id)})
    assert reponse.status_code == 403


def test_editer_la_saison_courante(client, db_session, ecole_en_cours):
    e = ecole_en_cours
    ecole_id = e["ecole"].id
    _creer(client, ecole_id)
    modif = {"nom": "Saison 27/28", "date_debut": "2027-09-01", "date_fin": "2028-07-14"}
    reponse = client.put(f"/ecoles/{ecole_id}/saisons/courante", json=modif)
    assert reponse.status_code == 200
    assert reponse.json()["nom"] == "Saison 27/28" and reponse.json()["courante"] is True
    noms = [s["nom"] for s in client.get(f"/ecoles/{ecole_id}/saisons").json()]
    assert noms == ["Saison 27/28", "2026-2027"]
    # Le nom d'une autre saison est pris ; dates incohérentes refusées.
    assert client.put(f"/ecoles/{ecole_id}/saisons/courante", json={**modif, "nom": "2026-2027"}).status_code == 409
    assert client.put(
        f"/ecoles/{ecole_id}/saisons/courante", json={**modif, "date_fin": "2027-01-01"}
    ).status_code == 409
    # Les inscriptions suivent les DATES de la saison, pas son nom libre.
    assert saison_des_inscriptions(db_session, ecole_id) == "2027-2028"


def test_libelle_des_inscriptions_par_defaut(db_session):
    ecole = Ecoles().create(db_session, nom="A", code_postal="1")
    saison = db_session.get(Saison, saison_courante_id(db_session, ecole.id))
    attendu = f"{saison.date_debut.year}-{saison.date_debut.year + 1}"
    assert saison_des_inscriptions(db_session, ecole.id) == attendu
