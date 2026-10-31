"""Module notes de frais (spec/modules/notes-de-frais.md) : saisie, envoi,
reprise, traitement par les trésoriers, alertes, droits — avec les vraies
vérifications de session (`rbac_reel`)."""

import io
from datetime import date

import pytest
from conftest import entetes_session

from app import main
from comptes import Comptes, roles
from ecoles import Ecoles
from notes_frais.ports import TicketLu

pytestmark = pytest.mark.rbac_reel

IBAN = "FR7630006000011234567890189"


class Espion:
    """Remplace mails et notifications : on regarde ce qui serait parti."""

    def __init__(self):
        self.mails = []
        self.notifications = []

    def envoyer(self, db, org_id, a, sujet, texte, html, repondre_a):
        self.mails.append({"a": list(a), "sujet": sujet, "texte": texte, "repondre_a": repondre_a})

    def notifier(self, db, notification_id, titre, corps):
        self.notifications.append((notification_id, titre))


@pytest.fixture()
def espion(monkeypatch, tmp_path):
    espion = Espion()
    ports = main.notes_frais_client.ports
    monkeypatch.setattr(ports, "messager", espion)
    monkeypatch.setattr(ports, "notifieur", espion)
    monkeypatch.setattr(main.notes_frais_client.stockage, "root", tmp_path / "notes")
    monkeypatch.setattr(main.documents_client.storage, "root", tmp_path / "docs")
    return espion


@pytest.fixture()
def ecole(db_session, espion):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    tresorier = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="julia@test.fr")
    comptes.ajouter_role(db_session, tresorier, roles.TRESORIER)
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Roux", prenom="Ana", email="ana@test.fr")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Perrin", prenom="Margot", email="margot@test.fr")
    return {"ecole": ecole, "tresorier": tresorier, "admin": admin, "eleve": eleve}


def _depense(client, qui, montant=4890, **extra):
    corps = {"date": "2026-10-12", "montant_centimes": montant, "description": "Tissu costumes", **extra}
    reponse = client.post("/notes-frais/depenses", json=corps, headers=entetes_session(qui))
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def _envoyer(client, qui, ids, **extra):
    corps = {"depense_ids": ids, "titre": "Costumes gala", "rib": {"iban": IBAN}, **extra}
    return client.post("/notes-frais/notes", json=corps, headers=entetes_session(qui))


def test_parcours_complet(client, ecole, espion):
    eleve, tresorier = ecole["eleve"], ecole["tresorier"]
    d1 = _depense(client, eleve)
    d2 = _depense(client, eleve, montant=1250, description="Paillettes")
    espace = client.get("/notes-frais/moi", headers=entetes_session(eleve)).json()
    assert [d["id"] for d in espace["a_envoyer"]] == [d2["id"], d1["id"]]
    assert espace["a_envoyer"][0]["sans_justificatif"] is True
    assert "Costumes" in [c["libelle"] for c in espace["categories"]]

    reponse = _envoyer(client, eleve, [d1["id"], d2["id"]])
    assert reponse.status_code == 201, reponse.text
    note = reponse.json()
    assert note["total_centimes"] == 6140 and note["statut"] == "envoyee"
    # Mail au trésorier (pas d'adresse de trésorerie : son email), réponse à Margot.
    assert espion.mails[-1]["a"] == ["julia@test.fr"]
    assert espion.mails[-1]["repondre_a"] == "margot@test.fr"
    assert (tresorier.id, "Nouvelle note de frais") in espion.notifications

    a_valider = client.get("/notes-frais/tresorerie", headers=entetes_session(tresorier)).json()
    assert [n["id"] for n in a_valider["notes"]] == [note["id"]]
    assert a_valider["notes"][0]["personne"]["nom"] == "Margot Perrin"
    assert a_valider["notes"][0]["rib"]["iban"] == IBAN

    assert client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(tresorier)).status_code == 200
    assert espion.mails[-1]["a"] == ["margot@test.fr"]
    assert espion.mails[-1]["repondre_a"] == "julia@test.fr"
    # Validée : plus de reprise possible.
    assert client.post(f"/notes-frais/notes/{note['id']}/reprendre", headers=entetes_session(eleve)).status_code == 400

    reponse = client.post("/notes-frais/remboursements", json={"note_ids": [note["id"]]}, headers=entetes_session(tresorier))
    assert reponse.status_code == 200
    terminees = client.get("/notes-frais/tresorerie?filtre=terminees", headers=entetes_session(tresorier)).json()
    assert terminees["notes"][0]["statut"] == "remboursee"
    assert "remboursée" in espion.mails[-1]["sujet"]

    export = client.get("/notes-frais/export.xlsx", headers=entetes_session(tresorier))
    assert export.status_code == 200 and export.content[:2] == b"PK"


def test_reprendre_remet_les_depenses_a_envoyer(client, ecole):
    eleve = ecole["eleve"]
    d = _depense(client, eleve)
    note = _envoyer(client, eleve, [d["id"]]).json()
    # Une dépense envoyée ne se modifie plus.
    assert client.delete(f"/notes-frais/depenses/{d['id']}", headers=entetes_session(eleve)).status_code == 400
    assert client.post(f"/notes-frais/notes/{note['id']}/reprendre", headers=entetes_session(eleve)).status_code == 204
    espace = client.get("/notes-frais/moi", headers=entetes_session(eleve)).json()
    assert [x["id"] for x in espace["a_envoyer"]] == [d["id"]] and espace["notes"] == []


def test_refus_avec_motif_obligatoire(client, ecole, espion):
    eleve, tresorier = ecole["eleve"], ecole["tresorier"]
    note = _envoyer(client, eleve, [_depense(client, eleve)["id"]]).json()
    url = f"/notes-frais/notes/{note['id']}/refuser"
    assert client.post(url, json={"motif": "  "}, headers=entetes_session(tresorier)).status_code == 400
    assert client.post(url, json={"motif": "Ticket illisible"}, headers=entetes_session(tresorier)).status_code == 200
    assert "Ticket illisible" in espion.mails[-1]["texte"]


def test_rib_obligatoire_sauf_don(client, ecole):
    eleve = ecole["eleve"]
    d = _depense(client, eleve)
    sans_rib = client.post("/notes-frais/notes", json={"depense_ids": [d["id"]]}, headers=entetes_session(eleve))
    assert sans_rib.status_code == 400
    don = client.post("/notes-frais/notes", json={"depense_ids": [d["id"]], "don": True}, headers=entetes_session(eleve))
    assert don.status_code == 201 and don.json()["rib"] is None


def test_iban_verifie(client, ecole):
    reponse = client.put("/notes-frais/rib", json={"iban": "FR76 3000 6000 0112 3456 7890 188"}, headers=entetes_session(ecole["eleve"]))
    assert reponse.status_code == 400


def test_seuls_les_tresoriers_traitent(client, ecole):
    eleve, admin = ecole["eleve"], ecole["admin"]
    note = _envoyer(client, eleve, [_depense(client, eleve)["id"]]).json()
    for qui in (eleve, admin):
        assert client.get("/notes-frais/tresorerie", headers=entetes_session(qui)).status_code == 403
        assert client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(qui)).status_code == 403


def test_le_super_user_fait_une_note_dans_l_ecole_choisie(client, db_session, ecole, espion):
    """Le Super User n'a pas de fiche dans l'école : sa note est à son nom
    (son compte), dans l'école où il intervient (en-tête X-Ecole-Id)."""
    su = Comptes().enregistrer_superuser(
        db_session, nom="Richard", prenom="Sébastien", email="su@test.fr", mot_de_passe_hache=None
    )
    sans_ecole = entetes_session(su)
    assert client.get("/notes-frais/moi", headers=sans_ecole).status_code == 403
    entetes = {**sans_ecole, "X-Ecole-Id": str(ecole["ecole"].id)}
    d = client.post(
        "/notes-frais/depenses",
        json={"date": "2026-10-12", "montant_centimes": 2000, "description": "Gaffer"},
        headers=entetes,
    )
    assert d.status_code == 201, d.text
    reponse = client.post(
        "/notes-frais/notes", json={"depense_ids": [d.json()["id"]], "titre": "Gala", "rib": {"iban": IBAN}}, headers=entetes
    )
    assert reponse.status_code == 201, reponse.text
    assert espion.mails[-1]["a"] == ["julia@test.fr"]
    notes = client.get("/notes-frais/tresorerie", headers=entetes_session(ecole["tresorier"])).json()["notes"]
    assert notes[0]["personne"]["nom"] == "Sébastien Richard"
    # Il traite aussi les notes, comme un trésorier.
    assert client.get("/notes-frais/tresorerie", headers=entetes).status_code == 200
    # Une école qui n'existe pas est refusée.
    assert client.get("/notes-frais/moi", headers={**sans_ecole, "X-Ecole-Id": "999"}).status_code == 403


def test_le_tresorier_saisit_et_envoie_pour_quelqu_un(client, ecole, espion):
    """Financier › ⋯ « pour quelqu'un » (décision de Seb, 19 octobre) : la
    dépense et la note sont au nom de la personne choisie."""
    eleve, tresorier, admin = ecole["eleve"], ecole["tresorier"], ecole["admin"]
    personnes = client.get("/notes-frais/personnes", headers=entetes_session(tresorier)).json()
    assert "Margot Perrin" in [p["nom"] for p in personnes]
    margot = next(p["person_id"] for p in personnes if p["nom"] == "Margot Perrin")
    pour = {**entetes_session(tresorier), "X-Pour-Personne": str(margot)}
    d = client.post(
        "/notes-frais/depenses", json={"date": "2026-10-12", "montant_centimes": 1500, "description": "Facture"}, headers=pour
    )
    assert d.status_code == 201, d.text
    reponse = client.post(
        "/notes-frais/notes", json={"depense_ids": [d.json()["id"]], "titre": "Factures", "rib": {"iban": IBAN}}, headers=pour
    )
    assert reponse.status_code == 201, reponse.text
    # Margot la retrouve dans « Mes notes de frais », avec le RIB saisi.
    espace = client.get("/notes-frais/moi", headers=entetes_session(eleve)).json()
    assert [n["titre"] for n in espace["notes"]] == ["Factures"]
    assert espace["rib"]["iban"] == IBAN
    # Rien chez le trésorier lui-même.
    assert client.get("/notes-frais/moi", headers=entetes_session(tresorier)).json()["notes"] == []
    # Réservé aux trésoriers ; la personne doit être de l'école.
    assert client.get("/notes-frais/personnes", headers=entetes_session(admin)).status_code == 403
    assert client.get("/notes-frais/moi", headers={**entetes_session(admin), "X-Pour-Personne": str(margot)}).status_code == 403
    assert client.get("/notes-frais/moi", headers={**entetes_session(tresorier), "X-Pour-Personne": "99999"}).status_code == 404


def test_on_ne_voit_pas_les_depenses_des_autres(client, ecole):
    d = _depense(client, ecole["eleve"])
    assert client.delete(f"/notes-frais/depenses/{d['id']}", headers=entetes_session(ecole["admin"])).status_code == 404


def test_justificatif_visible_de_l_auteur_et_du_tresorier(client, ecole):
    eleve = ecole["eleve"]
    d = _depense(client, eleve)
    fichiers = {"fichier": ("ticket.png", io.BytesIO(b"\x89PNG faux"), "image/png")}
    piece = client.post(f"/notes-frais/depenses/{d['id']}/pieces", files=fichiers, headers=entetes_session(eleve)).json()
    assert client.get(f"/notes-frais/pieces/{piece['id']}", headers=entetes_session(eleve)).content == b"\x89PNG faux"
    assert client.get(f"/notes-frais/pieces/{piece['id']}", headers=entetes_session(ecole["tresorier"])).status_code == 200
    assert client.get(f"/notes-frais/pieces/{piece['id']}", headers=entetes_session(ecole["admin"])).status_code == 404


def test_adresse_de_tresorerie(client, db_session, ecole, espion):
    ecole["ecole"].email_tresorier = "tresorerie@asso.fr"
    db_session.commit()
    eleve = ecole["eleve"]
    _envoyer(client, eleve, [_depense(client, eleve)["id"]])
    assert espion.mails[-1]["a"] == ["tresorerie@asso.fr"]


def test_le_tresorier_qui_a_l_adresse_de_tresorerie_ne_se_previent_pas(client, db_session, ecole, espion):
    """Seb, 16 octobre : sa propre note part aux AUTRES trésoriers."""
    comptes = Comptes()
    ecole["ecole"].email_tresorier = "julia@test.fr"
    db_session.commit()
    comptes.ajouter_role(db_session, ecole["admin"], roles.TRESORIER)
    julia = ecole["tresorier"]
    note = _envoyer(client, julia, [_depense(client, julia)["id"]]).json()
    assert espion.mails[-1]["a"] == ["ana@test.fr"]
    # Un autre trésorier existe : Julia ne valide pas sa propre note.
    assert client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(julia)).status_code == 403
    assert client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(ecole["admin"])).status_code == 200


def test_seul_tresorier_valide_sa_propre_note(client, ecole, espion):
    julia = ecole["tresorier"]
    nb_mails = len(espion.mails)
    note = _envoyer(client, julia, [_depense(client, julia)["id"]]).json()
    assert len(espion.mails) == nb_mails  # personne d'autre à prévenir
    assert client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(julia)).status_code == 200


def test_lecture_du_ticket(client, ecole, monkeypatch):
    class Lecteur:
        actif = True

        def lire(self, db, org_id, contenu, type_mime, categories, nom=""):
            assert "Costumes" in categories
            return TicketLu(date="2026-10-12", montant_centimes=4890, commercant="Mondial Tissus",
                            categorie="costumes", description="Tissu pour costumes")

    monkeypatch.setattr(main.notes_frais_client.ports, "lecteur", Lecteur())
    fichiers = {"fichier": ("ticket.jpg", io.BytesIO(b"jpeg"), "image/jpeg")}
    lu = client.post("/notes-frais/lecture", files=fichiers, headers=entetes_session(ecole["eleve"])).json()
    assert lu["date"] == "2026-10-12" and lu["montant_centimes"] == 4890
    assert lu["categorie_id"] is not None
    assert lu["description"] == "Tissu pour costumes (Mondial Tissus)"


def test_categories_gerees_par_les_tresoriers(client, ecole):
    corps = {"libelles": ["Costumes", "Essence", "Costumes"]}
    assert client.put("/notes-frais/categories", json=corps, headers=entetes_session(ecole["eleve"])).status_code == 403
    reponse = client.put("/notes-frais/categories", json=corps, headers=entetes_session(ecole["tresorier"]))
    assert [c["libelle"] for c in reponse.json()] == ["Costumes", "Essence"]


def test_date_future_refusee(client, ecole):
    corps = {"date": date(2099, 1, 1).isoformat(), "montant_centimes": 100}
    assert client.post("/notes-frais/depenses", json=corps, headers=entetes_session(ecole["eleve"])).status_code == 400


def _photo(client, qui, depense_id, contenu=b"jpeg", nom="IMG_001.jpg", mime="image/jpeg"):
    fichiers = {"fichier": (nom, io.BytesIO(contenu), mime)}
    reponse = client.post(f"/notes-frais/depenses/{depense_id}/pieces", files=fichiers, headers=entetes_session(qui))
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_tickets_sur_le_disque_puis_dans_docs(client, ecole, tmp_path):
    """Seb, 29 octobre : un seul endroit, Docs. Un ticket pas encore envoyé
    attend sur le disque ; à l'envoi il passe dans Docs et quitte le disque ;
    une note reprise le ramène avec ses dépenses."""
    eleve = ecole["eleve"]
    d = _depense(client, eleve)
    _photo(client, eleve, d["id"])
    org = tmp_path / "notes" / str(ecole["ecole"].id)
    (personne,) = org.iterdir()
    assert personne.name == f"{eleve.id} Margot Perrin"
    assert [f.name for f in (personne / "depenses").iterdir()] == [f"2026-10-12 Tissu costumes {d['id']}-1.jpg"]

    note = _envoyer(client, eleve, [d["id"]]).json()
    assert not list((personne / "depenses").iterdir())
    assert not (personne / "notes").exists()
    piece_id = note["depenses"][0]["pieces"][0]["id"]
    assert client.get(f"/notes-frais/pieces/{piece_id}", headers=entetes_session(eleve)).content == b"jpeg"
    assert client.get(f"/notes-frais/pieces/{piece_id}", headers=entetes_session(ecole["tresorier"])).content == b"jpeg"

    assert client.post(f"/notes-frais/notes/{note['id']}/reprendre", headers=entetes_session(eleve)).status_code == 204
    assert [f.name for f in (personne / "depenses").iterdir()] == [f"2026-10-12 Tissu costumes {d['id']}-1.jpg"]
    assert client.get(f"/notes-frais/pieces/{piece_id}", headers=entetes_session(eleve)).content == b"jpeg"


def test_telecharger_les_justificatifs_d_une_note(client, ecole):
    import zipfile

    eleve = ecole["eleve"]
    d1, d2 = _depense(client, eleve), _depense(client, eleve, description="Péage")
    fichiers = {"fichier": ("ticket.png", io.BytesIO(b"\x89PNG faux"), "image/png")}
    client.post(f"/notes-frais/depenses/{d1['id']}/pieces", files=fichiers, headers=entetes_session(eleve))
    note = _envoyer(client, eleve, [d1["id"], d2["id"]]).json()
    url = f"/notes-frais/notes/{note['id']}/justificatifs.zip"
    reponse = client.get(url, headers=entetes_session(ecole["tresorier"]))
    assert reponse.status_code == 200
    assert "Costumes%20gala" in reponse.headers["content-disposition"]
    archive = zipfile.ZipFile(io.BytesIO(reponse.content))
    assert archive.namelist()[0] == "Note de frais.pdf"
    assert archive.read(archive.namelist()[0]).startswith(b"%PDF")
    assert [archive.read(n) for n in archive.namelist()[1:]] == [b"\x89PNG faux"]
    assert client.get(url, headers=entetes_session(eleve)).status_code == 200
    assert client.get(url, headers=entetes_session(ecole["admin"])).status_code == 404


def _parcourir(client, org, qui, dossier=None):
    url = f"/documents/orgs/{org}/spaces/private" + (f"?folder={dossier}" if dossier else "")
    return client.get(url, headers=entetes_session(qui))


def _enfant(client, org, qui, dossier, nom):
    items = _parcourir(client, org, qui, dossier).json()["items"]
    return next((i for i in items if i["name"].startswith(nom)), None)


def test_note_rangee_dans_financier_reserve_aux_tresoriers(client, db_session, ecole):
    eleve, tresorier, admin = ecole["eleve"], ecole["tresorier"], ecole["admin"]
    org = ecole["ecole"].id
    d = _depense(client, eleve)
    _photo(client, eleve, d["id"], b"\x89PNG faux", "ticket.png", "image/png")
    note = _envoyer(client, eleve, [d["id"]]).json()

    saison = next(i for i in _parcourir(client, org, tresorier).json()["items"] if i["system_kind"] == "period")
    financier = _enfant(client, org, tresorier, saison["id"], "Financier")
    assert financier["system_kind"] == "reserved"
    notes = _enfant(client, org, tresorier, financier["id"], "Notes de frais")
    # Rangée dès l'envoi, sans badge : l'état ne se lit que dans l'appli.
    [personne] = _parcourir(client, org, tresorier, notes["id"]).json()["items"]
    assert "Perrin" in personne["name"] and personne["name"].split()[0].isdigit()
    dossier_note = _enfant(client, org, tresorier, personne["id"], "2026")
    assert "Costumes gala" in dossier_note["name"] and dossier_note["status"] is None
    [ticket] = _parcourir(client, org, tresorier, dossier_note["id"]).json()["items"]
    assert ticket["name"].endswith(".png")
    assert client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(tresorier)).status_code == 200
    # Payé : le PDF récapitulatif est fait une seule fois, à côté ; rien ne bouge.
    assert client.post("/notes-frais/remboursements", json={"note_ids": [note["id"]]}, headers=entetes_session(tresorier)).status_code == 200
    [apres] = _parcourir(client, org, tresorier, personne["id"]).json()["items"]
    assert apres["id"] == dossier_note["id"] and apres["status"] is None
    noms = sorted(i["name"] for i in _parcourir(client, org, tresorier, dossier_note["id"]).json()["items"])
    assert noms == [ticket["name"], "Note de frais.pdf"]

    # Le Super User, qui a tous les droits (spec/core.md §6.1), y entre.
    su = Comptes().enregistrer_superuser(
        db_session, nom="Richard", prenom="Sébastien", email="su@test.fr", mot_de_passe_hache=None
    )
    assert _enfant(client, org, su, saison["id"], "Financier")["id"] == financier["id"]
    assert _parcourir(client, org, su, financier["id"]).status_code == 200

    # Un autre admin ne voit ni n'ouvre le dossier Financier.
    assert _enfant(client, org, admin, saison["id"], "Financier") is None
    assert _parcourir(client, org, admin, financier["id"]).status_code == 404
    assert client.get(f"/documents/orgs/{org}/spaces/private/search?q=Costumes", headers=entetes_session(admin)).json() == []
    # Ses accès suivent le rôle : on ne les change pas à la main.
    acces = client.put(
        f"/documents/orgs/{org}/nodes/{financier['id']}/access",
        json={"restricted": False, "entries": []},
        headers=entetes_session(tresorier),
    )
    assert acces.status_code == 409


def test_note_refusee_puis_reprise_retiree_des_docs(client, ecole):
    eleve, tresorier = ecole["eleve"], ecole["tresorier"]
    org = ecole["ecole"].id
    d = _depense(client, eleve)
    _photo(client, eleve, d["id"])
    note = _envoyer(client, eleve, [d["id"]]).json()
    refus = client.post(f"/notes-frais/notes/{note['id']}/refuser", json={"motif": "Ticket illisible"}, headers=entetes_session(tresorier))
    assert refus.status_code == 200

    saison = next(i for i in _parcourir(client, org, tresorier).json()["items"] if i["system_kind"] == "period")
    financier = _enfant(client, org, tresorier, saison["id"], "Financier")
    notes = _enfant(client, org, tresorier, financier["id"], "Notes de frais")
    [personne] = _parcourir(client, org, tresorier, notes["id"]).json()["items"]
    [dossier_note] = _parcourir(client, org, tresorier, personne["id"]).json()["items"]
    assert dossier_note["status"] is None
    assert client.post(f"/notes-frais/notes/{note['id']}/reprendre", headers=entetes_session(eleve)).status_code == 204
    assert _parcourir(client, org, tresorier, personne["id"]).json()["items"] == []


def test_vider_les_notes_de_frais_d_une_ecole(client, db_session, ecole, tmp_path):
    """Commande serveur app/vider_notes_frais.py : notes, dépenses,
    justificatifs et dossier Docs effacés ; catégories gardées."""
    from app.vider_notes_frais import _compter, _dossiers_docs, vider

    eleve, tresorier = ecole["eleve"], ecole["tresorier"]
    org = ecole["ecole"].id
    d = _depense(client, eleve)
    fichiers = {"fichier": ("ticket.png", io.BytesIO(b"\x89PNG faux"), "image/png")}
    client.post(f"/notes-frais/depenses/{d['id']}/pieces", files=fichiers, headers=entetes_session(eleve))
    _envoyer(client, eleve, [d["id"]])
    _depense(client, eleve, montant=100)
    assert _compter(db_session, org) == (1, 2, 1)
    assert _dossiers_docs(db_session, org)
    categories = client.get("/notes-frais/categories", headers=entetes_session(tresorier)).json()

    vider(db_session, org)

    assert _compter(db_session, org) == (0, 0, 0)
    assert _dossiers_docs(db_session, org) == []
    assert client.get("/notes-frais/moi", headers=entetes_session(eleve)).status_code == 200
    assert client.get("/notes-frais/categories", headers=entetes_session(tresorier)).json() == categories


def test_vider_sans_clavier_exige_le_nom_exact(client, db_session, ecole):
    """Action GitHub « Maintenance » (DEPLOY.md §6) : --ecole et --nom."""
    from app.vider_notes_frais import _compter, _effacer

    org = ecole["ecole"]
    _depense(client, ecole["eleve"])
    with pytest.raises(SystemExit):
        _effacer(db_session, [org], str(org.id), "contretemps")
    with pytest.raises(SystemExit):
        _effacer(db_session, [org], "999", org.nom)
    assert _compter(db_session, org.id)[1] == 1
    _effacer(db_session, [org], str(org.id), org.nom)
    assert _compter(db_session, org.id) == (0, 0, 0)


# --- Financier › Pièces : une seule structure « dépense » (financier.md §8.3 bis) ---


class LecteurFacture:
    """Lecture simulée : ce que la photo dirait."""

    actif = True

    def __init__(self, **lu):
        self.lu = lu

    def lire(self, db, org_id, contenu, type_mime, categories, nom=""):
        return TicketLu(**self.lu)


def _etablir(client, qui, nature, contenu=b"jpeg", **champs):
    fichiers = {"fichier": ("IMG_100.jpg", io.BytesIO(contenu), "image/jpeg")} if contenu else None
    reponse = client.post(
        "/notes-frais/etablir", data={**({"nature": nature} if nature else {}), **champs}, files=fichiers,
        headers=entetes_session(qui),
    )
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_rafale_d_achats_lue_rangee_dans_achats(client, ecole, monkeypatch):
    """Une photo = une dépense créée À valider, lue, rangée dans Docs ›
    Achats sous son nom ; « Encore une page » ajoute une page ; on valide."""
    tresorier = ecole["tresorier"]
    org = ecole["ecole"].id
    monkeypatch.setattr(
        main.notes_frais_client.ports, "lecteur",
        LecteurFacture(date="2025-02-09", montant_centimes=3990, commercant="Amazon", description="Câbles"),
    )
    note = _etablir(client, tresorier, "achat")
    assert note["nature"] == "achat" and note["statut"] == "envoyee"
    assert note["fournisseur"] == "Amazon" and note["titre"] == "Amazon" and note["total_centimes"] == 3990
    page = client.post(
        f"/notes-frais/notes/{note['id']}/pages",
        files={"fichier": ("IMG_101.jpg", io.BytesIO(b"page 2"), "image/jpeg")},
        headers=entetes_session(tresorier),
    )
    assert page.status_code == 200 and len(page.json()["depenses"][0]["pieces"]) == 2

    saison = next(i for i in _parcourir(client, org, tresorier).json()["items"] if i["system_kind"] == "period")
    financier = _enfant(client, org, tresorier, saison["id"], "Financier")
    achats = _enfant(client, org, tresorier, financier["id"], "ACHATS")
    mois = _enfant(client, org, tresorier, achats["id"], "02.2025")
    noms = sorted(i["name"] for i in _parcourir(client, org, tresorier, mois["id"]).json()["items"])
    assert noms == ["2025-02-09 Amazon 39,90 (2).jpg", "2025-02-09 Amazon 39,90.jpg"]

    puce = client.get("/notes-frais/tresorerie?filtre=achat", headers=entetes_session(tresorier)).json()
    assert [n["id"] for n in puce["notes"]] == [note["id"]]
    assert puce["compteurs"] == {"frais": 0, "honoraires": 0, "achat": 1, "virements": 0}
    # Rien des achats dans la puce Notes de frais.
    assert client.get("/notes-frais/tresorerie?filtre=frais", headers=entetes_session(tresorier)).json()["notes"] == []

    corrige = client.patch(
        f"/notes-frais/notes/{note['id']}", json={"montant_centimes": 3999, "fournisseur": "Amazon EU"},
        headers=entetes_session(tresorier),
    )
    assert corrige.status_code == 200 and corrige.json()["total_centimes"] == 3999
    assert corrige.json()["titre"] == "Amazon EU"
    valide = client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(tresorier))
    assert valide.status_code == 200 and valide.json()["statut"] == "validee"


def _achats_de_la_saison(client, org, qui, saison):
    dossier = _enfant(client, org, qui, None, f"Saison {saison}")
    financier = dossier and _enfant(client, org, qui, dossier["id"], "Financier")
    achats = financier and _enfant(client, org, qui, financier["id"], "ACHATS")
    if not achats:
        return []
    # Un dossier par mois de la pièce (« 03.2026 », Seb 30/10).
    mois = _parcourir(client, org, qui, achats["id"]).json()["items"]
    assert all(m["name"][2] == "." and len(m["name"]) == 7 for m in mois), mois
    return sorted(i["name"] for m in mois for i in _parcourir(client, org, qui, m["id"]).json()["items"])


def test_vieille_piece_rangee_dans_la_saison_de_sa_date(client, db_session, ecole, monkeypatch):
    """Une pièce de l'an dernier va dans le Financier de sa saison si on peut
    y écrire, pas dans celui de la saison en cours ; si on corrige sa date,
    elle suit."""
    from saisons.models import Saison

    tresorier = ecole["tresorier"]
    org = ecole["ecole"].id
    passee = Saison(ecole_id=org, nom="2025-2026", date_debut=date(2025, 9, 1), date_fin=date(2026, 8, 31))
    db_session.add(passee)
    db_session.commit()
    lecteur = LecteurFacture(date="2026-03-10", montant_centimes=2500, commercant="Leroy Merlin", description="Peinture")
    monkeypatch.setattr(main.notes_frais_client.ports, "lecteur", lecteur)
    # Saison terminée, en lecture seule : dans la saison en cours.
    fermee = _etablir(client, tresorier, "achat")
    assert _achats_de_la_saison(client, org, tresorier, "2025-2026") == []
    client.delete(f"/notes-frais/notes/{fermee['id']}", headers=entetes_session(tresorier))

    # Rouverte aux modifications (bilan de l'an dernier) : dans sa saison.
    passee.ouverte = True
    db_session.commit()
    note = _etablir(client, tresorier, "achat")
    courante = next(
        i["name"].removeprefix("Saison ") for i in _parcourir(client, org, tresorier).json()["items"]
        if i["system_kind"] == "period" and i["name"] != "Saison 2025-2026"
    )
    assert _achats_de_la_saison(client, org, tresorier, "2025-2026") == ["2026-03-10 Leroy Merlin 25,00.jpg"]
    assert _achats_de_la_saison(client, org, tresorier, courante) == []

    corrige = client.patch(
        f"/notes-frais/notes/{note['id']}", json={"date": "2026-10-02"}, headers=entetes_session(tresorier)
    )
    assert corrige.status_code == 200
    assert _achats_de_la_saison(client, org, tresorier, "2025-2026") == []
    assert _achats_de_la_saison(client, org, tresorier, courante) == ["2026-10-02 Leroy Merlin 25,00.jpg"]
    # Le justificatif s'ouvre toujours.
    piece = corrige.json()["depenses"][0]["pieces"][0]
    assert client.get(f"/notes-frais/pieces/{piece['id']}", headers=entetes_session(tresorier)).status_code == 200


def test_rafale_d_honoraires_reconnait_le_prof(client, db_session, ecole, monkeypatch):
    tresorier = ecole["tresorier"]
    prof = Comptes().create(
        db_session, ecole_id=ecole["ecole"].id, role="professeur", nom="Revelles", prenom="Élodie", email="elodie@test.fr"
    )
    client.put("/notes-frais/rib", json={"iban": IBAN, "titulaire": "E REVELLES"}, headers=entetes_session(prof))
    lecteur = LecteurFacture(date="2026-10-15", montant_centimes=48000, commercant="Elodie REVELLES", description="Cours d'octobre")
    monkeypatch.setattr(main.notes_frais_client.ports, "lecteur", lecteur)
    note = _etablir(client, tresorier, "honoraires")
    assert note["personne"]["nom"] == "Élodie Revelles"
    assert note["titre"] == "Honoraires octobre 2026"
    assert note["rib"]["iban"] == IBAN

    # Nom illisible : « Pour qui ? », pas de validation avant d'avoir choisi.
    lecteur.lu = {"montant_centimes": 30000}
    inconnu = _etablir(client, tresorier, "honoraires")
    assert inconnu["personne"] is None
    assert client.post(f"/notes-frais/notes/{inconnu['id']}/valider", headers=entetes_session(tresorier)).status_code == 400
    choisi = client.patch(
        f"/notes-frais/notes/{inconnu['id']}", json={"person_id": prof.id}, headers=entetes_session(tresorier)
    )
    assert choisi.json()["personne"]["nom"] == "Élodie Revelles" and choisi.json()["rib"]["iban"] == IBAN
    assert client.post(f"/notes-frais/notes/{inconnu['id']}/valider", headers=entetes_session(tresorier)).status_code == 200
    # La première attend toujours d'être validée (compteur du Profil).
    assert client.get("/notes-frais/compteurs", headers=entetes_session(tresorier)).json()["a_valider"] == 1


def test_saisir_une_depense_propose_la_nature(client, db_session, ecole, espion, monkeypatch):
    """« + » sans nature (§7 quinquies) : un prof lu sur la pièce = honoraires,
    une autre personne = note de frais (établie, corrigeable par le
    trésorier), personne = achat ; la nature proposée se change tant que
    c'est à valider, et le fichier suit dans Docs ; déjà payée = Payé sans
    bruit."""
    tresorier, membre = ecole["tresorier"], ecole["eleve"]
    org = ecole["ecole"].id
    prof = Comptes().create(db_session, ecole_id=org, role="professeur", nom="Revelles", prenom="Élodie", email="elodie@test.fr")
    lecteur = LecteurFacture(date="2026-10-15", montant_centimes=48000, commercant="Elodie REVELLES", description="Cours")
    monkeypatch.setattr(main.notes_frais_client.ports, "lecteur", lecteur)

    honoraires = _etablir(client, tresorier, None)
    assert honoraires["nature"] == "honoraires" and honoraires["personne"]["person_id"] == prof.id and honoraires["etablie"]

    lecteur.lu = {"date": "2026-10-14", "montant_centimes": 740, "commercant": "Vinci Autoroutes", "description": "Péage Margot Perrin"}
    frais = _etablir(client, tresorier, None)
    assert frais["nature"] == "frais" and frais["personne"]["nom"] == "Margot Perrin" and frais["titre"] == "Frais octobre 2026"
    # Établie par le trésorier : il la valide lui-même, et elle est à son nom pour elle.
    assert client.post(f"/notes-frais/notes/{frais['id']}/valider", headers=entetes_session(tresorier)).status_code == 200
    assert [n["id"] for n in client.get("/notes-frais/moi", headers=entetes_session(membre)).json()["notes"]] == [frais["id"]]

    lecteur.lu = {"date": "2026-10-12", "montant_centimes": 3990, "commercant": "Amazon", "description": "Câbles"}
    achat = _etablir(client, tresorier, None)
    assert achat["nature"] == "achat" and achat["fournisseur"] == "Amazon"
    assert _achats_de_la_saison(client, org, tresorier, "2026-2027") == ["2026-10-12 Amazon 39,90.jpg"]

    # La proposition était fausse : c'est un ticket de Margot ; le fichier va dans son dossier.
    corrige = client.patch(
        f"/notes-frais/notes/{achat['id']}", json={"nature": "frais", "person_id": membre.id}, headers=entetes_session(tresorier)
    )
    assert corrige.status_code == 200, corrige.text
    assert corrige.json()["nature"] == "frais" and corrige.json()["personne"]["nom"] == "Margot Perrin"
    assert corrige.json()["titre"] == "Frais octobre 2026" and corrige.json()["fournisseur"] is None
    assert _achats_de_la_saison(client, org, tresorier, "2026-2027") == []
    saison = _enfant(client, org, tresorier, None, "Saison 2026-2027")
    financier = _enfant(client, org, tresorier, saison["id"], "Financier")
    notes = _enfant(client, org, tresorier, financier["id"], "Notes de frais")
    personne = next(i for i in _parcourir(client, org, tresorier, notes["id"]).json()["items"] if "Perrin" in i["name"])
    dossiers = _parcourir(client, org, tresorier, personne["id"]).json()["items"]
    dossier_note = next(d for d in dossiers if d["name"].endswith(f"({achat['id']})"))
    assert "Frais octobre 2026" in dossier_note["name"]
    assert [i["name"] for i in _parcourir(client, org, tresorier, dossier_note["id"]).json()["items"]] == ["2026-10-12 Amazon 39,90.jpg"]
    # Pas de nature sans personne : « Pour qui ? » avant de valider.
    sans = client.patch(f"/notes-frais/notes/{achat['id']}", json={"nature": "honoraires"}, headers=entetes_session(tresorier))
    assert sans.json()["personne"] is None
    assert client.post(f"/notes-frais/notes/{achat['id']}/valider", headers=entetes_session(tresorier)).status_code == 400
    # Déjà payée avant d'être dans l'appli : « C'est payé » depuis À valider, sans mail au prof.
    client.patch(f"/notes-frais/notes/{achat['id']}", json={"person_id": prof.id}, headers=entetes_session(tresorier))
    virement = _operation(db_session, org, -3990, "2026-10-20", "VIR SEPA REVELLES")
    avant = len(espion.mails)
    paye = client.post(f"/notes-frais/notes/{achat['id']}/payee", json={"operation_id": virement.id}, headers=entetes_session(tresorier))
    assert paye.status_code == 200 and paye.json()["statut"] == "remboursee"
    assert len(espion.mails) == avant

    # Une note envoyée par la personne elle-même ne change pas de nature.
    envoyee = _envoyer(client, membre, [_depense(client, membre)["id"]]).json()
    refuse = client.patch(f"/notes-frais/notes/{envoyee['id']}", json={"nature": "achat"}, headers=entetes_session(tresorier))
    assert refuse.status_code == 400 and not envoyee["etablie"]
    # Validée : la nature ne bouge plus.
    assert client.patch(
        f"/notes-frais/notes/{frais['id']}", json={"nature": "achat"}, headers=entetes_session(tresorier)
    ).status_code == 400


def test_saisir_une_depense_factures_et_preuves_de_virement(client, db_session, ecole, monkeypatch):
    """Dossier de factures 2025-2026 de Seb (étude du 31/10) : une facture
    faite par une personne = honoraires (membre ou extérieur) ; une facture
    de société adressée à un membre = sa note de frais, à l'association =
    achat ; la preuve d'un virement n'est pas une dépense : elle paie une
    pièce, et son IBAN remplit le RIB qui manquait."""
    tresorier, membre = ecole["tresorier"], ecole["eleve"]
    org = ecole["ecole"].id
    boyer = Comptes().create(db_session, ecole_id=org, role="professeur", nom="Boyer", prenom="Sophie", email="sb@test.fr")
    lecteur = LecteurFacture(date="2025-11-30", montant_centimes=94800, commercant="SOPHIE BOYER", emetteur_personne=True,
                             client="Ecole de danse contretemps", description="Cours de danse Novembre 2025")
    monkeypatch.setattr(main.notes_frais_client.ports, "lecteur", lecteur)
    honoraires = _etablir(client, tresorier, None)
    assert honoraires["nature"] == "honoraires" and honoraires["personne"]["person_id"] == boyer.id
    assert honoraires["rib"] is None

    # Intervenant extérieur (Seb : note de frais, pas honoraires), inconnu : son nom prêt pour « Pour qui ? ».
    lecteur.lu = dict(date="2025-10-31", montant_centimes=5600, commercant="Thibault Taniou", emetteur_personne=True,
                      client="Contre Temps Danse", description="Prestation de danse classique")
    taniou = _etablir(client, tresorier, None)
    assert taniou["nature"] == "frais" and taniou["personne"] is None and taniou["fournisseur"] == "Thibault Taniou"

    # Société, facturée à un membre : c'est lui qui a payé.
    lecteur.lu = dict(date="2026-08-10", montant_centimes=14090, commercant="Onlineprinters", emetteur_personne=False,
                      client="Ecole de danse Contretemps, Madame Margot PERRIN", description="Flyers et affiches")
    flyers = _etablir(client, tresorier, None)
    assert flyers["nature"] == "frais" and flyers["personne"]["nom"] == "Margot Perrin"
    # Société, facturée à l'association : achat.
    lecteur.lu = dict(date="2026-01-01", montant_centimes=41760, commercant="MAIF", emetteur_personne=False,
                      client="CONTRETEMPS", description="Assurance 2026")
    assert _etablir(client, tresorier, None)["nature"] == "achat"

    # Preuve du virement à Sophie : page de plus sur sa facture, RIB rempli.
    lecteur.lu = dict(sorte="virement", date="2025-12-05", montant_centimes=94800, beneficiaire="BOYER SOPHIE",
                      iban=IBAN, motif="FACT1125-SOPHIE/CONTRETEMPS")
    preuve = _etablir(client, tresorier, None)
    assert preuve["id"] == honoraires["id"] and preuve["sorte"] == "virement"
    assert preuve["preuve"]["beneficiaire"] == "BOYER SOPHIE" and preuve["preuve"]["interne"] is False
    assert len(preuve["depenses"][0]["pieces"]) == 2 and preuve["rib"]["iban"] == IBAN
    assert client.get("/notes-frais/moi", headers=entetes_session(boyer)).json()["rib"]["iban"] == IBAN
    # Payée avant l'appli : on valide et « J'ai fait le virement » date de la preuve, pas de RIB à demander.
    assert client.post(f"/notes-frais/notes/{honoraires['id']}/valider", headers=entetes_session(tresorier)).status_code == 200
    assert client.post(f"/notes-frais/notes/{honoraires['id']}/virement", headers=entetes_session(tresorier)).json()["statut"] == "viree"

    # Virement vers un compte de l'association, ou sans pièce : rien n'est créé.
    lecteur.lu = dict(sorte="virement", date="2026-08-05", montant_centimes=500000, beneficiaire="ASSOCIATION CONTRETEMPS DU BEAUSSET")
    interne = _etablir(client, tresorier, None)
    assert interne["id"] is None and interne["preuve"]["interne"] is True
    lecteur.lu = dict(sorte="virement", date="2026-02-11", montant_centimes=41765, beneficiaire="AMIF")
    seule = _etablir(client, tresorier, None)
    assert seule["id"] is None and seule["preuve"]["interne"] is False
    puce = client.get("/notes-frais/tresorerie?filtre=achat", headers=entetes_session(tresorier)).json()
    assert [n["fournisseur"] for n in puce["notes"]] == ["MAIF"]


def test_la_banque_decide(client, db_session, ecole, espion):
    """Seb, 31/10 : une ligne du compte du même montant et au même nom est
    rattachée toute seule (photo ou preuve de virement), la pièce reste À
    valider et passe Payé quand un trésorier la valide ; le montant seul
    reste proposé ; une preuve sans pièce montre la ligne ; rattachée à
    tort, « Pas cette ligne » tant que ce n'est pas validé, puis Détacher
    tant que la saison n'est pas clôturée."""
    tresorier = ecole["tresorier"]
    org = ecole["ecole"].id
    boyer = Comptes().create(db_session, ecole_id=org, role="professeur", nom="Boyer", prenom="Sophie", email="sb@test.fr")
    novembre = _operation(db_session, org, -94800, "2025-12-05", "VIR INST FACT1125-SOPHIE BOYER")
    janvier = _operation(db_session, org, -94800, "2026-02-09", "VIR INST FACT0226BOYER/CONTRETE")
    _operation(db_session, org, -41760, "2026-02-11", "VIR INST MAIF")
    _operation(db_session, org, -36400, "2026-08-12", "PRLV CARTE 364")  # montant seul, pas de nom
    entetes = entetes_session(tresorier)

    lecteur = LecteurFacture(date="2025-11-30", montant_centimes=94800, commercant="SOPHIE BOYER", emetteur_personne=True,
                             client="Contretemps", description="Cours de danse Novembre 2025")
    main.notes_frais_client.ports.lecteur = lecteur
    try:
        # Montant + nom : la ligne la plus proche de la facture est rattachée, la pièce reste À valider.
        boyer_11 = _etablir(client, tresorier, None)
        assert boyer_11["statut"] == "envoyee" and boyer_11["operation_id"] == novembre.id and boyer_11["detachable"]
        assert boyer_11["operation"]["libelle"] == "VIR INST FACT1125-SOPHIE BOYER" and boyer_11["paiement_propose"] is None
        # La validation du trésorier la passe Payé, sans prévenir la prof (c'était déjà réglé).
        validee = client.post(f"/notes-frais/notes/{boyer_11['id']}/valider", headers=entetes).json()
        assert validee["statut"] == "remboursee" and validee["operation_id"] == novembre.id
        assert not [n for n in espion.notifications if n[0] == boyer.id]
        lecteur.lu = dict(date="2026-01-31", montant_centimes=94800, commercant="SOPHIE BOYER", emetteur_personne=True,
                          client="Contretemps", description="Cours de danse Janvier 2026")
        boyer_01 = _etablir(client, tresorier, None)
        assert boyer_01["statut"] == "envoyee" and boyer_01["operation_id"] == janvier.id
        # Société : le nom du fournisseur suffit.
        lecteur.lu = dict(date="2026-01-01", montant_centimes=41760, commercant="MAIF", emetteur_personne=False, client="CONTRETEMPS")
        assert _etablir(client, tresorier, None)["operation_id"] is not None
        # Montant seul : proposé, pas rattaché.
        lecteur.lu = dict(date="2026-07-22", montant_centimes=36400, commercant="Picture Impact Production", emetteur_personne=False,
                          client="Contretemps")
        dvd = _etablir(client, tresorier, None)
        assert dvd["operation_id"] is None and dvd["paiement_propose"]["libelle"] == "PRLV CARTE 364"
        # Personne inconnue : la ligne est rattachée quand même, Valider demandera « Pour qui ? ».
        _operation(db_session, org, -5600, "2025-11-10", "VIR TANIOU THIBAULT")
        lecteur.lu = dict(date="2025-10-31", montant_centimes=5600, commercant="Thibault Taniou", emetteur_personne=True, client="Contretemps")
        taniou = _etablir(client, tresorier, None)
        assert taniou["statut"] == "envoyee" and taniou["personne"] is None and taniou["operation_id"] is not None
        assert client.post(f"/notes-frais/notes/{taniou['id']}/valider", headers=entetes).status_code == 400

        # Preuve de virement : sa pièce est là, la ligne du compte aussi → rattachée, à valider.
        ligne_dvd = _operation(db_session, org, -36400, "2026-08-12", "VIR INST FACT2026014 PICTURE IMPACT")
        lecteur.lu = dict(sorte="virement", date="2026-08-12", montant_centimes=36400, beneficiaire="PICTURE IMPACT PRODUCTION",
                          motif="VIR INST FACT2026014 CONTRETEMP")
        preuve = _etablir(client, tresorier, None)
        assert preuve["id"] == dvd["id"] and preuve["statut"] == "envoyee" and preuve["operation_id"] == ligne_dvd.id
        # Preuve sans pièce : la ligne du compte est montrée, rien n'est créé.
        revelles = _operation(db_session, org, -72575, "2025-12-05", "VIR INST FACT1125-STELLINA REVELLES")
        lecteur.lu = dict(sorte="virement", date="2025-12-05", montant_centimes=72575, beneficiaire="REVELLES STELLINA", motif="FACT1125-STELLINA")
        seule = _etablir(client, tresorier, None)
        assert seule["id"] is None and seule["preuve"]["operation"]["id"] == revelles.id
    finally:
        main.notes_frais_client.ports.lecteur = None

    # « Pas cette ligne » avant validation : la pièce reste À valider, la ligne est libre et proposée à nouveau.
    url = f"/notes-frais/notes/{boyer_01['id']}"
    detachee = client.post(f"{url}/detacher", headers=entetes)
    assert detachee.status_code == 200 and detachee.json()["statut"] == "envoyee" and detachee.json()["operation_id"] is None
    assert detachee.json()["paiement_propose"]["id"] == janvier.id
    assert client.post(f"{url}/detacher", headers=entetes).status_code == 400
    # « C'est payé » la reprend ; rattachée à tort une fois payée : Détacher la remet À valider.
    assert client.post(f"{url}/payee", json={"operation_id": janvier.id}, headers=entetes).json()["statut"] == "remboursee"
    assert client.post(f"{url}/detacher", headers=entetes).json()["statut"] == "envoyee"
    assert client.post(f"{url}/payee", json={"operation_id": janvier.id}, headers=entetes).json()["statut"] == "remboursee"
    # Saison clôturée : la banque a décidé, on ne détache plus.
    import datetime as dt

    from finances.models import FinClosing

    db_session.add(FinClosing(org_id=org, season_id=1, start_date=dt.date(2025, 9, 1), end_date=dt.date(2026, 8, 31), result=0, balances=[]))
    db_session.commit()
    assert client.post(f"{url}/detacher", headers=entetes).status_code == 400
    payees = client.get("/notes-frais/tresorerie?filtre=honoraires", headers=entetes).json()["notes"]
    assert all(n["detachable"] is False for n in payees if n["statut"] == "remboursee")
    assert client.post(f"{url}/detacher", headers=entetes_session(ecole["eleve"])).status_code == 403


def test_etablir_reserve_aux_tresoriers_et_supprimer_une_photo_ratee(client, ecole):
    tresorier = ecole["tresorier"]
    reponse = client.post(
        "/notes-frais/etablir", data={"nature": "achat"},
        files={"fichier": ("x.jpg", io.BytesIO(b"x"), "image/jpeg")}, headers=entetes_session(ecole["admin"]),
    )
    assert reponse.status_code == 403
    # Sans lecture : montant à compléter avant de valider.
    note = _etablir(client, tresorier, "achat")
    assert note["total_centimes"] == 0
    assert client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(tresorier)).status_code == 400
    assert client.delete(f"/notes-frais/notes/{note['id']}", headers=entetes_session(tresorier)).status_code == 204
    assert client.get("/notes-frais/tresorerie?filtre=achat", headers=entetes_session(tresorier)).json()["notes"] == []
    # Saisie complète sans photo : validée en même temps.
    saisi = _etablir(client, tresorier, "achat", contenu=None, fournisseur="Mondial Tissus", date="2026-10-20",
                     montant_centimes="12000", valider="true")
    assert saisi["statut"] == "validee" and saisi["total_centimes"] == 12000


def test_note_etablie_par_le_tresorier_pour_quelqu_un_est_validee(client, ecole, espion):
    tresorier, eleve = ecole["tresorier"], ecole["eleve"]
    pour = {**entetes_session(tresorier), "X-Pour-Personne": str(eleve.id)}
    d = client.post("/notes-frais/depenses", json={"date": "2026-10-12", "montant_centimes": 1500}, headers=pour).json()
    nb_mails = len(espion.mails)
    note = client.post("/notes-frais/notes", json={"depense_ids": [d["id"]], "rib": {"iban": IBAN}}, headers=pour).json()
    assert note["statut"] == "validee"
    # Pas de « Nouvelle note de frais » aux trésoriers : c'est déjà fait.
    assert len(espion.mails) == nb_mails


def test_commande_range_les_anciennes_enveloppes_dans_docs(client, db_session, ecole, tmp_path):
    """python -m app.ranger_notes_frais : une note envoyée avant le 29 octobre
    a ses photos sur le disque ; la commande les met dans Docs (ou reprend la
    copie qui y est déjà) et vide le disque."""
    from app.ranger_notes_frais import ranger
    from notes_frais.models import Depense, NoteFrais

    eleve = ecole["eleve"]
    d = _depense(client, eleve)
    _photo(client, eleve, d["id"])
    ancienne = NoteFrais(org_id=ecole["ecole"].id, person_id=eleve.id, titre="Avant", statut="validee")
    db_session.add(ancienne)
    db_session.flush()
    db_session.get(Depense, d["id"]).note_id = ancienne.id
    db_session.commit()
    disque = tmp_path / "notes" / str(ecole["ecole"].id) / f"{eleve.id} Margot Perrin" / "depenses"
    assert len(list(disque.iterdir())) == 1

    assert ranger(db_session, essai=True) == (1, 1)
    assert len(list(disque.iterdir())) == 1
    assert ranger(db_session) == (1, 1)
    assert not list(disque.iterdir())
    assert ranger(db_session) == (0, 0)
    piece_id = client.get("/notes-frais/moi", headers=entetes_session(eleve)).json()["notes"][0]["depenses"][0]["pieces"][0]["id"]
    assert client.get(f"/notes-frais/pieces/{piece_id}", headers=entetes_session(eleve)).content == b"jpeg"


# --- Virements (financier.md §8.3 bis) ---


def _honoraires_a_payer(client, db_session, ecole):
    prof = Comptes().create(
        db_session, ecole_id=ecole["ecole"].id, role="professeur", nom="Martin", prenom="Lucie", email="lucie@test.fr"
    )
    note = _etablir(client, ecole["tresorier"], "honoraires", contenu=None, person_id=str(prof.id), date="2026-10-15",
                    montant_centimes="48000", valider="true")
    return prof, note


def _a_faire(client, qui):
    """Badges des puces de Pièces : ce qui attend une action de qui regarde."""
    return client.get("/notes-frais/tresorerie/compteurs", headers=entetes_session(qui)).json()


def test_aide_au_virement_et_faire_payer_par_quelqu_un(client, db_session, ecole, espion):
    tresorier, admin = ecole["tresorier"], ecole["admin"]
    prof, note = _honoraires_a_payer(client, db_session, ecole)
    assert note["statut"] == "validee" and note["rib"] is None
    url = f"/notes-frais/notes/{note['id']}"
    # Pas de RIB : rien à préparer.
    assert client.post(f"{url}/virement", headers=entetes_session(tresorier)).status_code == 400
    rib = client.put(f"{url}/rib", json={"iban": IBAN, "titulaire": "L MARTIN"}, headers=entetes_session(tresorier))
    assert rib.status_code == 200 and rib.json()["rib"]["iban"] == IBAN
    # Gardé aussi sur la fiche du prof.
    assert client.get("/notes-frais/moi", headers=entetes_session(prof)).json()["rib"]["iban"] == IBAN

    liste = client.get("/notes-frais/virements", headers=entetes_session(tresorier)).json()
    [ligne] = liste["virements"]
    assert ligne["beneficiaire"] == "L MARTIN" and ligne["libelle_virement"] == "Contretemps honoraires oct 2026"
    assert [p["nom"] for p in liste["payeurs"]] == ["Julia Dho"]
    assert _a_faire(client, tresorier) == {"frais": 0, "honoraires": 0, "achat": 0, "virements": 1}

    # « Qui paie » : Ana, qui a l'appli de la banque.
    reglage = client.put("/notes-frais/payeurs", json={"person_ids": [admin.id]}, headers=entetes_session(tresorier))
    assert [p["nom"] for p in reglage.json()] == ["Ana Roux"]
    assert client.post(f"{url}/preparer", json={"payeur_id": tresorier.id}, headers=entetes_session(tresorier)).status_code == 400
    prepare = client.post(f"{url}/preparer", json={"payeur_id": admin.id}, headers=entetes_session(tresorier))
    assert prepare.status_code == 200 and prepare.json()["statut"] == "preparee"
    assert prepare.json()["payeur"]["nom"] == "Ana Roux" and prepare.json()["prepare_par"]["nom"] == "Julia Dho"
    assert (admin.id, "Virement à faire") in espion.notifications
    # Préparé : à faire pour Ana (trésorière adjointe), plus pour Julia.
    assert _a_faire(client, tresorier)["virements"] == 0
    Comptes().ajouter_role(db_session, admin, roles.TRESORIER)
    assert _a_faire(client, admin)["virements"] == 1

    fait = client.post(f"{url}/virement", headers=entetes_session(tresorier))
    assert fait.status_code == 200 and fait.json()["statut"] == "viree"
    assert client.post(f"{url}/virement", headers=entetes_session(tresorier)).status_code == 400
    # Réservé aux trésoriers.
    assert client.get("/notes-frais/virements", headers=entetes_session(ecole["eleve"])).status_code == 403


# --- Vu sur le compte (financier.md §8.3 bis, rapprochement) ---


def _operation(db_session, org_id, montant, jour, libelle):
    import datetime as dt

    from finances.models import FinAccount, FinOperation

    compte = db_session.query(FinAccount).filter_by(org_id=org_id).first()
    if compte is None:
        compte = FinAccount(org_id=org_id, number="401", name="Compte courant", kind="checking")
        db_session.add(compte)
        db_session.flush()
    jour = dt.date.fromisoformat(jour)
    operation = FinOperation(account_id=compte.id, position=0, date=jour, value_date=jour, label=libelle, amount=montant)
    db_session.add(operation)
    db_session.commit()
    return operation


def test_envoye_puis_vu_sur_le_compte_paye(client, db_session, ecole, espion):
    tresorier, admin = ecole["tresorier"], ecole["admin"]
    prof, note = _honoraires_a_payer(client, db_session, ecole)
    url = f"/notes-frais/notes/{note['id']}"
    client.put(f"{url}/rib", json={"iban": IBAN, "titulaire": "L MARTIN"}, headers=entetes_session(tresorier))
    client.put("/notes-frais/payeurs", json={"person_ids": [admin.id]}, headers=entetes_session(tresorier))
    client.post(f"{url}/preparer", json={"payeur_id": admin.id}, headers=entetes_session(tresorier))
    client.post(f"{url}/virement", headers=entetes_session(tresorier))
    # Envoyé, pas encore vu sur le compte : on attend la banque.
    assert _a_faire(client, tresorier)["virements"] == 0

    org = ecole["ecole"].id
    _operation(db_session, org, -48000, "2026-09-01", "VIR SEPA AUTRE")  # trop tôt
    autre = _operation(db_session, org, -48000, "2026-11-02", "VIR SEPA DUPONT")
    bonne = _operation(db_session, org, -48000, "2026-11-03", "VIR SEPA MARTIN LUCIE")
    [ligne] = client.get("/notes-frais/virements", headers=entetes_session(tresorier)).json()["virements"]
    assert ligne["paiement_propose"]["id"] == bonne.id
    # Envoyé et vu sur le compte : reste « C'est payé ».
    assert _a_faire(client, tresorier)["virements"] == 1

    # Mauvais montant ou opération d'une autre pièce : refusé.
    petite = _operation(db_session, org, -100, "2026-11-03", "VIR")
    assert client.post(f"{url}/payee", json={"operation_id": petite.id}, headers=entetes_session(tresorier)).status_code == 400
    paye = client.post(f"{url}/payee", json={"operation_id": bonne.id}, headers=entetes_session(tresorier))
    assert paye.status_code == 200 and paye.json()["statut"] == "remboursee" and paye.json()["operation_id"] == bonne.id
    # Prévenus : celle qui a préparé (ici Julia elle-même : non), et le prof.
    assert (prof.id, "Honoraires payés") in espion.notifications
    [ligne] = client.get("/notes-frais/virements", headers=entetes_session(tresorier)).json()["virements"]
    assert ligne["statut"] == "remboursee" and ligne["paiement_propose"] is None

    # L'opération prise n'est plus proposée à une autre pièce.
    _, autre_note = _honoraires_a_payer_bis(client, db_session, ecole)
    propose = client.get("/notes-frais/tresorerie?filtre=honoraires", headers=entetes_session(tresorier)).json()["notes"]
    assert next(n for n in propose if n["id"] == autre_note["id"])["paiement_propose"]["id"] == autre.id


def _honoraires_a_payer_bis(client, db_session, ecole):
    prof = Comptes().create(
        db_session, ecole_id=ecole["ecole"].id, role="professeur", nom="Pesenti", prenom="Anna", email="anna@test.fr"
    )
    return prof, _etablir(client, ecole["tresorier"], "honoraires", contenu=None, person_id=str(prof.id),
                          date="2026-10-20", montant_centimes="48000", valider="true")


def test_achat_deja_paye_par_carte(client, db_session, ecole, monkeypatch):
    """« Déjà payé ? » : l'achat lu trouve son débit carte (même montant, sans
    le nom : proposé) ; confirmé, il passe Payé sans passer par Virements."""
    tresorier = ecole["tresorier"]
    monkeypatch.setattr(
        main.notes_frais_client.ports, "lecteur",
        LecteurFacture(date="2025-02-09", montant_centimes=3990, commercant="Amazon"),
    )
    carte = _operation(db_session, ecole["ecole"].id, -3990, "2025-02-10", "CB 0902 PAIEMENT INTERNET")
    note = _etablir(client, tresorier, "achat")
    assert note["statut"] == "envoyee" and note["paiement_propose"]["id"] == carte.id
    paye = client.post(f"/notes-frais/notes/{note['id']}/payee", json={"operation_id": carte.id}, headers=entetes_session(tresorier))
    assert paye.json()["statut"] == "remboursee"
    assert client.get("/notes-frais/virements", headers=entetes_session(tresorier)).json()["virements"][0]["id"] == note["id"]


def test_categories_sont_les_comptes_de_charges_du_plan(client, db_session, ecole):
    """Seb, 30/10 : une fois le plan comptable là, les catégories en sont les
    comptes de charges ; une pièce garde sa catégorie (son compte)."""
    tresorier = entetes_session(ecole["tresorier"])
    plan = client.get("/finances/chart", headers=tresorier).json()["accounts"]
    charges = sorted((a["number"], a["label"]) for a in plan if a["nature"] == "depense" and a["active"])
    categories = client.get("/notes-frais/categories", headers=tresorier).json()
    assert [(c["code"], c["libelle"]) for c in categories] == charges
    # Le crayon mène au plan : plus de liste libre.
    assert client.put("/notes-frais/categories", json={"libelles": ["Costumes"]}, headers=tresorier).status_code == 400
    fournitures = next(c for c in categories if c["code"] == "606")
    achat = client.post("/notes-frais/etablir", data={"nature": "achat", "fournisseur": "Castorama", "date": "2026-10-01",
                                                    "montant_centimes": "4500", "categorie_id": str(fournitures["id"])}, headers=tresorier)
    assert achat.status_code == 201, achat.text
    assert achat.json()["depenses"][0]["categorie"]["id"] == fournitures["id"]


# --- Personnes extérieures (§7 quater) ---


def test_personne_exterieure_payee_comme_un_membre(client, db_session, ecole, espion, monkeypatch):
    """Un prof invité, pas membre : ajouté depuis « Pour qui ? » avec son mail
    et son IBAN, reconnu sur la photo de sa facture, payé, prévenu par mail."""
    tresorier = ecole["tresorier"]
    t = entetes_session(tresorier)
    corps = {"nom": "Jacques  Pesanti", "email": "jacques@test.fr", "rib": {"iban": IBAN, "titulaire": "J PESANTI"}}
    assert client.post("/notes-frais/exterieurs", json=corps, headers=entetes_session(ecole["eleve"])).status_code == 403
    ajoute = client.post("/notes-frais/exterieurs", json=corps, headers=t)
    assert ajoute.status_code == 201
    jacques = ajoute.json()
    assert jacques["nom"] == "Jacques Pesanti" and jacques["role"] == "extérieur"

    # « Pour qui ? » : les membres d'abord, puis les extérieurs.
    personnes = client.get("/notes-frais/personnes", headers=t).json()
    assert [p["nom"] for p in personnes][-1] == "Jacques Pesanti" and len(personnes) == 4

    # La photo de sa facture le reconnaît, son RIB est recopié.
    monkeypatch.setattr(
        main.notes_frais_client.ports, "lecteur",
        LecteurFacture(date="2026-10-15", montant_centimes=15000, commercant="Jacques PESANTI", description="Stage de tango"),
    )
    note = _etablir(client, tresorier, "honoraires")
    assert note["personne"]["nom"] == "Jacques Pesanti" and note["rib"]["iban"] == IBAN
    url = f"/notes-frais/notes/{note['id']}"
    assert client.post(f"{url}/valider", headers=t).status_code == 200
    assert client.post(f"{url}/virement", headers=t).status_code == 200
    operation = _operation(db_session, ecole["ecole"].id, -15000, date.today().isoformat(), "VIR SEPA PESANTI")
    assert client.post(f"{url}/payee", json={"operation_id": operation.id}, headers=t).status_code == 200
    [mail] = [m for m in espion.mails if m["a"] == ["jacques@test.fr"]]
    assert mail["sujet"] == "Honoraires payés : Honoraires octobre 2026"

    # Corrigé puis retiré de la liste : plus proposé, la note garde son nom.
    [ligne] = client.get("/notes-frais/exterieurs", headers=t).json()
    assert ligne["email"] == "jacques@test.fr" and ligne["rib"]["iban"] == IBAN
    corps["email"] = "jp@test.fr"
    assert client.put(f"/notes-frais/exterieurs/{ligne['id']}", json=corps, headers=t).status_code == 200
    assert client.get("/notes-frais/exterieurs", headers=t).json()[0]["email"] == "jp@test.fr"
    assert client.delete(f"/notes-frais/exterieurs/{ligne['id']}", headers=t).status_code == 204
    assert "Jacques Pesanti" not in [p["nom"] for p in client.get("/notes-frais/personnes", headers=t).json()]
    [paye] = client.get("/notes-frais/virements", headers=t).json()["virements"]
    assert paye["personne"]["nom"] == "Jacques Pesanti" and paye["statut"] == "remboursee"


def test_demander_son_rib_a_un_exterieur(client, ecole, espion):
    """Mail ou téléphone facultatifs ; sans RIB, un mail le lui demande, la
    réponse va au trésorier."""
    t = entetes_session(ecole["tresorier"])
    sans_mail = client.post("/notes-frais/exterieurs", json={"nom": "Ana Lopez", "telephone": "06 12 34 56 78"}, headers=t)
    assert sans_mail.status_code == 201
    [ana] = client.get("/notes-frais/exterieurs", headers=t).json()
    assert ana["telephone"] == "06 12 34 56 78" and ana["rib"] is None
    assert client.post(f"/notes-frais/exterieurs/{ana['id']}/demander-rib", headers=t).status_code == 400

    corps = {"nom": "Ana Lopez", "email": "ana.lopez@test.fr", "telephone": "06 12 34 56 78"}
    client.put(f"/notes-frais/exterieurs/{ana['id']}", json=corps, headers=t)
    assert client.post(f"/notes-frais/exterieurs/{ana['id']}/demander-rib", headers=t).status_code == 204
    [mail] = espion.mails
    assert mail["a"] == ["ana.lopez@test.fr"] and "RIB" in mail["sujet"]
    assert mail["repondre_a"] == "julia@test.fr" and "Bonjour Ana Lopez" in mail["texte"]
    assert client.post(
        f"/notes-frais/exterieurs/{ana['id']}/demander-rib", headers=entetes_session(ecole["eleve"])
    ).status_code == 403
