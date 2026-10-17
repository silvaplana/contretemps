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


def test_tickets_ranges_en_enveloppes(client, ecole, tmp_path):
    """Seb, 16 octobre : un dossier par personne, « depenses » puis une
    enveloppe par note ; une note reprise renvoie ses tickets dans « depenses »."""
    eleve = ecole["eleve"]
    d = _depense(client, eleve)
    fichiers = {"fichier": ("IMG_001.jpg", io.BytesIO(b"jpeg"), "image/jpeg")}
    client.post(f"/notes-frais/depenses/{d['id']}/pieces", files=fichiers, headers=entetes_session(eleve))
    org = tmp_path / "notes" / str(ecole["ecole"].id)
    (personne,) = org.iterdir()
    assert personne.name == f"{eleve.id} Margot Perrin"
    assert [f.name for f in (personne / "depenses").iterdir()] == [f"2026-10-12 Tissu costumes {d['id']}-1.jpg"]

    note = _envoyer(client, eleve, [d["id"]]).json()
    (enveloppe,) = (personne / "notes").iterdir()
    assert enveloppe.name.endswith(f"Costumes gala ({note['id']})")
    assert sorted(f.name for f in enveloppe.iterdir()) == [f"2026-10-12 Tissu costumes {d['id']}-1.jpg", "Note de frais.pdf"]
    assert not list((personne / "depenses").iterdir())
    # Le PDF récapitulatif suit chaque étape (Seb, 17 octobre).
    assert (enveloppe / "Note de frais.pdf").read_bytes().startswith(b"%PDF")

    client.post(f"/notes-frais/notes/{note['id']}/reprendre", headers=entetes_session(eleve))
    assert not list((personne / "notes").iterdir())
    assert len(list((personne / "depenses").iterdir())) == 1
    piece_id = client.get("/notes-frais/moi", headers=entetes_session(eleve)).json()["a_envoyer"][0]["pieces"][0]["id"]
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


def test_note_validee_rangee_dans_financier_reserve_aux_tresoriers(client, ecole):
    eleve, tresorier, admin = ecole["eleve"], ecole["tresorier"], ecole["admin"]
    org = ecole["ecole"].id
    d = _depense(client, eleve)
    fichiers = {"fichier": ("ticket.png", io.BytesIO(b"\x89PNG faux"), "image/png")}
    client.post(f"/notes-frais/depenses/{d['id']}/pieces", files=fichiers, headers=entetes_session(eleve))
    note = _envoyer(client, eleve, [d["id"]]).json()
    assert client.post(f"/notes-frais/notes/{note['id']}/valider", headers=entetes_session(tresorier)).status_code == 200

    def parcourir(qui, dossier=None):
        url = f"/documents/orgs/{org}/spaces/private" + (f"?folder={dossier}" if dossier else "")
        return client.get(url, headers=entetes_session(qui))

    def enfant(qui, dossier, nom):
        items = parcourir(qui, dossier).json()["items"]
        return next((i for i in items if i["name"].startswith(nom)), None)

    saison = next(i for i in parcourir(tresorier).json()["items"] if i["system_kind"] == "period")
    financier = enfant(tresorier, saison["id"], "Financier")
    assert financier["system_kind"] == "reserved"
    notes = enfant(tresorier, financier["id"], "Notes de frais")
    dossier_note = enfant(tresorier, notes["id"], "2026")
    assert "Perrin" in dossier_note["name"] and "Costumes gala" in dossier_note["name"]
    noms = sorted(i["name"] for i in parcourir(tresorier, dossier_note["id"]).json()["items"])
    assert noms[1] == "Note de frais.pdf" and noms[0].endswith(".png")
    # Remboursée : le PDF de Docs reçoit une nouvelle version, pas un doublon.
    assert client.post("/notes-frais/remboursements", json={"note_ids": [note["id"]]}, headers=entetes_session(tresorier)).status_code == 200
    assert len(parcourir(tresorier, dossier_note["id"]).json()["items"]) == 2

    # Un autre admin ne voit ni n'ouvre le dossier Financier.
    assert enfant(admin, saison["id"], "Financier") is None
    assert parcourir(admin, financier["id"]).status_code == 404
    assert client.get(f"/documents/orgs/{org}/spaces/private/search?q=Costumes", headers=entetes_session(admin)).json() == []
    # Ses accès suivent le rôle : on ne les change pas à la main.
    acces = client.put(
        f"/documents/orgs/{org}/nodes/{financier['id']}/access",
        json={"restricted": False, "entries": []},
        headers=entetes_session(tresorier),
    )
    assert acces.status_code == 409
