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

        def lire(self, db, org_id, contenu, type_mime, categories):
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

    def lire(self, db, org_id, contenu, type_mime, categories):
        return TicketLu(**self.lu)


def _etablir(client, qui, nature, contenu=b"jpeg", **champs):
    fichiers = {"fichier": ("IMG_100.jpg", io.BytesIO(contenu), "image/jpeg")} if contenu else None
    reponse = client.post(
        "/notes-frais/etablir", data={"nature": nature, **champs}, files=fichiers, headers=entetes_session(qui)
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
    achats = _enfant(client, org, tresorier, financier["id"], "Achats")
    noms = sorted(i["name"] for i in _parcourir(client, org, tresorier, achats["id"]).json()["items"])
    assert noms == ["2025-02-09 Amazon 39,90 (2).jpg", "2025-02-09 Amazon 39,90.jpg"]

    puce = client.get("/notes-frais/tresorerie?filtre=achat", headers=entetes_session(tresorier)).json()
    assert [n["id"] for n in puce["notes"]] == [note["id"]]
    assert puce["compteurs"] == {"frais": 0, "honoraires": 0, "achat": 1}
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

    # « Qui paie » : Ana, qui a l'appli de la banque.
    reglage = client.put("/notes-frais/payeurs", json={"person_ids": [admin.id]}, headers=entetes_session(tresorier))
    assert [p["nom"] for p in reglage.json()] == ["Ana Roux"]
    assert client.post(f"{url}/preparer", json={"payeur_id": tresorier.id}, headers=entetes_session(tresorier)).status_code == 400
    prepare = client.post(f"{url}/preparer", json={"payeur_id": admin.id}, headers=entetes_session(tresorier))
    assert prepare.status_code == 200 and prepare.json()["statut"] == "preparee"
    assert prepare.json()["payeur"]["nom"] == "Ana Roux" and prepare.json()["prepare_par"]["nom"] == "Julia Dho"
    assert (admin.id, "Virement à faire") in espion.notifications

    fait = client.post(f"{url}/virement", headers=entetes_session(tresorier))
    assert fait.status_code == 200 and fait.json()["statut"] == "viree"
    assert client.post(f"{url}/virement", headers=entetes_session(tresorier)).status_code == 400
    # Réservé aux trésoriers.
    assert client.get("/notes-frais/virements", headers=entetes_session(admin)).status_code == 403
