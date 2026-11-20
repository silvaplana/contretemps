"""Importation automatique de pièces, étape 2 (spec/modules/import-auto-pieces.md) : éteint
par défaut, un import dont la source est un dossier de Docs crée une pièce
À valider par nouveau fichier, reliée au fichier sans le déplacer ; « Voir »,
la poubelle qui garde les pièces, les écoles étanches."""

import io
from datetime import datetime, timezone

import pytest
from conftest import entetes_session

from app import main
from comptes import Comptes, roles
from documents.ports import Member
from ecoles import Ecoles
from registry import activation

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def asc(db_session, monkeypatch, tmp_path):
    monkeypatch.setattr(main.notes_frais_client.stockage, "root", tmp_path / "notes")
    monkeypatch.setattr(main.documents_client.storage, "root", tmp_path / "docs")
    ecole = Ecoles().create(db_session, nom="ASC La Ciotat", code_postal="13600")
    activation.set_enabled(db_session, ecole.id, main.MODULES, "auto_import", True)
    tresorier = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia", email="julia@test.fr")
    Comptes().ajouter_role(db_session, tresorier, roles.TRESORIER)
    qui = Member(person_id=tresorier.id, org_id=ecole.id, display_name="Julia", is_admin=True,
                 groups=frozenset({"role:admin", "role:tresorier"}))
    dossier = main.documents_client.create_folder(db_session, qui, "private", None, "FACTURES")
    main.documents_client.upload(db_session, qui, "private", dossier["id"], "Facture Wix.pdf", io.BytesIO(b"%PDF-1.4 wix"))
    main.documents_client.upload(db_session, qui, "private", dossier["id"], "notes.txt", io.BytesIO(b"pas une piece"))
    return {"ecole": ecole, "tresorier": tresorier, "dossier": dossier["id"], "qui": qui}


def test_eteint_par_defaut(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    assert "auto_import" in activation.disabled(db_session, ecole.id)
    tresorier = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="A", prenom="B", email="b@test.fr")
    Comptes().ajouter_role(db_session, tresorier, roles.TRESORIER)
    assert client.get("/auto-import", headers=entetes_session(tresorier)).status_code == 404


def test_un_import_depuis_docs(client, db_session, asc):
    from notes_frais.models import ENVOYEE, NoteFrais, PieceJustificative

    h = entetes_session(asc["tresorier"])
    regle = client.post("/auto-import", headers=h).json()
    regle = client.put(f"/auto-import/{regle['id']}", headers=h, json={
        **{k: regle[k] for k in ("name", "active", "season_id", "frequency", "at_time")},
        "name": "Factures", "nature": "achat", "source_kind": "docs", "source_ref": asc["dossier"],
        "source_path": "FACTURES",
    }).json()

    run = client.post(f"/auto-import/{regle['id']}/run", headers=h).json()
    assert run == {"created": 1, "message": "1 nouvelle pièce, À valider dans Pièces"}
    note = db_session.query(NoteFrais).one()
    piece = db_session.query(PieceJustificative).one()
    assert note.statut == ENVOYEE and note.nature == "achat"
    # Relié au fichier du dossier, pas de copie, pas de rangement.
    assert piece.linked and piece.doc_node_id is not None and piece.nom == "Facture Wix.pdf"
    from documents.models import DocNode

    assert db_session.get(DocNode, piece.doc_node_id).parent_id == asc["dossier"]

    # Un second passage ne recrée rien.
    assert client.post(f"/auto-import/{regle['id']}/run", headers=h).json()["created"] == 0
    liste = client.get("/auto-import", headers=h).json()
    assert [(r["name"], r["pieces"]) for r in liste["rules"]] == [("Factures", 1)]
    assert [n["id"] for n in client.get(f"/auto-import/{regle['id']}/pieces", headers=h).json()["notes"]] == [note.id]

    # La poubelle efface l'import, jamais la pièce.
    assert client.delete(f"/auto-import/{regle['id']}", headers=h).status_code == 204
    assert client.get("/auto-import", headers=h).json()["rules"] == []
    assert db_session.query(NoteFrais).count() == 1


def test_destination_docs_et_boite_mail_sans_destination(client, db_session, asc):
    from notes_frais.models import PieceJustificative

    h = entetes_session(asc["tresorier"])
    archive = main.documents_client.create_folder(db_session, asc["qui"], "private", None, "ARCHIVES")
    regle = client.post("/auto-import", headers=h, json={
        "name": "Copie", "source_kind": "docs", "source_ref": asc["dossier"], "target_kind": "docs",
        "target_ref": archive["id"],
    }).json()
    assert client.post(f"/auto-import/{regle['id']}/run", headers=h).json()["created"] == 1
    from documents.models import DocNode

    piece = db_session.query(PieceJustificative).one()
    assert db_session.get(DocNode, piece.doc_node_id).parent_id == archive["id"]
    refus = client.put(f"/auto-import/{regle['id']}", headers=h, json={"source_kind": "mail", "target_kind": "none"})
    assert refus.status_code == 422


def test_une_vente_depuis_docs(client, db_session, asc):
    """Les ventes existent dans Pièces (financier.md §8.12) : plus d'attente."""
    from notes_frais.models import NoteFrais

    h = entetes_session(asc["tresorier"])
    regle = client.post("/auto-import", headers=h, json={"nature": "vente", "source_ref": asc["dossier"]}).json()
    assert client.post(f"/auto-import/{regle['id']}/run", headers=h).json()["created"] == 1
    assert db_session.query(NoteFrais).one().nature == "vente"


def test_heure_du_passage():
    from auto_import.models import AutoImportRule
    from auto_import.service import due

    regle = AutoImportRule(active=True, frequency="daily", at_time="07:00", last_run_at=None)
    matin = datetime(2026, 11, 20, 5, 30, tzinfo=timezone.utc)  # 6 h 30 à Paris
    assert not due(regle, matin)
    assert due(regle, datetime(2026, 11, 20, 6, 5, tzinfo=timezone.utc))
    regle.last_run_at = datetime(2026, 11, 20, 6, 5)
    assert not due(regle, datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc))
    assert due(regle, datetime(2026, 11, 21, 6, 5, tzinfo=timezone.utc))
    regle.frequency = "hourly"
    assert due(regle, datetime(2026, 11, 20, 7, 5, tzinfo=timezone.utc))


def test_ecoles_etanches(client, db_session, asc):
    autre = Ecoles().create(db_session, nom="Le Beausset", code_postal="83330")
    activation.set_enabled(db_session, autre.id, main.MODULES, "auto_import", True)
    voisin = Comptes().create(db_session, ecole_id=autre.id, role="admin", nom="X", prenom="Y", email="y@test.fr")
    Comptes().ajouter_role(db_session, voisin, roles.TRESORIER)
    regle = client.post("/auto-import", headers=entetes_session(asc["tresorier"])).json()
    h = entetes_session(voisin)
    assert client.get("/auto-import", headers=h).json()["rules"] == []
    assert client.post(f"/auto-import/{regle['id']}/run", headers=h).status_code == 404


class FauxKDrive:
    """Un kDrive en mémoire, partagé par tous les clients du test."""

    fichiers: dict = {}

    def __init__(self, provider, address, secret, drive_ref):
        pass

    def check(self):
        pass

    def list(self, path=""):
        from drives.providers import Entry

        return [Entry(name=p.rsplit("/", 1)[-1], path=p, is_dir=False) for p in sorted(self.fichiers)
                if p.rsplit("/", 1)[0] == path]

    def read(self, path):
        return self.fichiers[path]

    def write(self, folder, name, content, mime="application/octet-stream"):
        self.fichiers[f"{folder}/{name}"] = content
        return f"{folder}/{name}"


def test_un_drive_en_source_et_en_destination(client, db_session, asc, monkeypatch):
    """Étape 3 : un dossier de kDrive en source, relié sans copie ; puis un
    dossier de kDrive en destination d'une source Docs."""
    from drives import DriveAccount
    from notes_frais.models import PieceJustificative

    monkeypatch.setattr(main.core.drives, "factory", FauxKDrive)
    monkeypatch.setattr(FauxKDrive, "fichiers", {"FACTURES/Orange.pdf": b"%PDF-1.4 orange", "FACTURES/lisez.txt": b"x"})
    drive = main.core.drives.connect(db_session, asc["ecole"].id, "kdrive", "club@ik.me", "code", "812345")
    h = entetes_session(asc["tresorier"])

    lu = client.post("/auto-import", headers=h, json={
        "name": "kDrive", "source_kind": "drive", "source_ref": drive.id, "source_path": "FACTURES"}).json()
    assert client.post(f"/auto-import/{lu['id']}/run", headers=h).json()["created"] == 1
    piece = db_session.query(PieceJustificative).one()
    assert (piece.linked, piece.drive_id, piece.drive_path, piece.doc_node_id) == (True, drive.id, "FACTURES/Orange.pdf", None)
    assert list(FauxKDrive.fichiers) == ["FACTURES/Orange.pdf", "FACTURES/lisez.txt"]  # rien de déplacé
    contenu = client.get(f"/notes-frais/pieces/{piece.id}", headers=h)
    assert contenu.status_code == 200 and contenu.content == b"%PDF-1.4 orange"

    copie = client.post("/auto-import", headers=h, json={
        "name": "Vers le kDrive", "source_kind": "docs", "source_ref": asc["dossier"], "target_kind": "drive",
        "target_ref": drive.id, "target_path": "ARCHIVES"}).json()
    assert client.post(f"/auto-import/{copie['id']}/run", headers=h).json()["created"] == 1
    assert FauxKDrive.fichiers["ARCHIVES/Facture Wix.pdf"] == b"%PDF-1.4 wix"

    # Un drive déconnecté : l'import attend avec un message.
    db_session.delete(db_session.get(DriveAccount, drive.id))
    db_session.commit()
    assert "drive" in client.post(f"/auto-import/{lu['id']}/run", headers=h).json()["message"]


class FausseBoite:
    """Une boîte de réception en mémoire : un mail par entrée."""

    def __init__(self, mails):
        self.mails = mails
        self.lus = []

    def list(self, folder="inbox", before=None, query=""):
        return {"messages": [{k: m[k] for k in ("uid", "subject", "from", "date", "snippet", "hasAttachments")}
                             for m in self.mails], "hasMore": False}

    def peek(self, folder, uid):
        m = next(m for m in self.mails if m["uid"] == uid)
        return {"messageId": f"<{uid}@test>", "attachments": [
            {"index": i, "filename": n, "contentType": t, "size": len(c)} for i, (n, t, c) in enumerate(m["pj"])]}

    def attachment(self, folder, uid, index):
        n, t, c = next(m for m in self.mails if m["uid"] == uid)["pj"][index]
        return c, n, t


def test_une_boite_mail_en_source(client, db_session, asc, monkeypatch):
    """Étape 5 (§4.1) : sans pièce jointe, ignoré ; avec, une pièce si
    l'objet ou l'expéditeur répond ; jamais sans destination ; un prof de
    l'école donne Honoraires."""
    from comptes.models import EmailCompte
    from notes_frais.models import NoteFrais

    prof = Comptes().create(db_session, ecole_id=asc["ecole"].id, role="professeur", nom="Boyer", prenom="Léa", email="lea@test.fr")
    assert db_session.query(EmailCompte).filter_by(compte_id=prof.id).count() == 1
    pdf = ("Facture.pdf", "application/pdf", b"%PDF-1.4 a")
    mail = lambda uid, sujet, de, pj: {"uid": uid, "subject": sujet, "from": [{"name": "", "address": de}],  # noqa: E731
                                       "date": "2026-11-18T09:00:00+00:00", "snippet": "", "hasAttachments": bool(pj), "pj": pj}
    boite = FausseBoite([
        mail(1, "Votre facture Wix", "billing@wix.com", [pdf, ("logo.txt", "text/plain", b"x")]),
        mail(2, "Bonjour", "ami@test.fr", [("photo.pdf", "application/pdf", b"%PDF-1.4 b")]),
        mail(3, "Facture sans pièce jointe", "billing@wix.com", []),
        mail(4, "Mes cours d'octobre", "lea@test.fr", [("Octobre.pdf", "application/pdf", b"%PDF-1.4 c")]),
    ])
    monkeypatch.setattr(main.core.mail_connection, "client", lambda db, org, box=None: boite)
    h = entetes_session(asc["tresorier"])
    regle = client.post("/auto-import", headers=h, json={
        "name": "Boîte", "source_kind": "mail", "source_ref": 1, "target_kind": "docs", "target_ref": asc["dossier"],
        "mail_need_amount": False}).json()

    run = client.post(f"/auto-import/{regle['id']}/run", headers=h).json()
    assert run["created"] == 2
    notes = {n.nature for n in db_session.query(NoteFrais)}
    assert notes == {"achat", "honoraires"}
    assert client.post(f"/auto-import/{regle['id']}/run", headers=h).json()["created"] == 0


def test_versements_helloasso(client, db_session, asc, monkeypatch):
    """Étape 6 (§4.2) : un versement = les paiements versés le même jour ;
    une vente À valider par versement, une ligne par compte d'après la
    formule ; une adhésion en 3 fois compte dans chaque versement qui a versé
    une échéance ; le PDF reconstitué n'est déposé qu'avec une destination."""
    from documents.models import DocNode
    from helloasso.models import HelloAssoRegistration
    from notes_frais.models import Depense, NoteFrais

    def paiement(montant, jour, versement, echeance=None, etat="CashedOut"):
        return {"amount": montant, "date": jour, "state": "Authorized", "means": "Card", "installment": echeance,
                "cash_out_state": etat, "cash_out_date": versement}

    def inscrit(item, nom, formule, paiements):
        db_session.add(HelloAssoRegistration(
            org_id=asc["ecole"].id, season_id=1, item_id=item, order_id=item, first_name=nom, last_name="X",
            tier_name=formule, amount=sum(p["amount"] for p in paiements), state="Processed", payments=paiements))

    inscrit("1", "Ali", "Adhésion adulte", [paiement(10600, "2026-09-20", "2026-10-10")])
    inscrit("2", "Bea", "Adhésion en 3 fois", [
        paiement(10000, "2026-09-21", "2026-10-10", 1), paiement(10000, "2026-10-21", "2026-11-10", 2),
        paiement(10000, "2026-11-21", None, 3, etat="MoneyIn")])
    inscrit("3", "Cid", "Stage", [paiement(2000, "2026-10-25", "2026-11-10")])
    db_session.commit()

    # Seb, 20 novembre : « Regarder maintenant » finissait en 502 ; chaque PDF
    # reconstitué partait à la lecture payante (lente). Jamais pour HelloAsso.
    from notes_frais.service import NotesDeFrais

    monkeypatch.setattr(NotesDeFrais, "lecture_disponible", property(lambda self: True))

    def jamais(*args, **kwargs):
        raise AssertionError("une pièce reconstituée ne se lit pas")

    monkeypatch.setattr(main.notes_frais_client, "lire_ticket", jamais)
    h = entetes_session(asc["tresorier"])
    client.get("/finances/chart", headers=h)  # le plan comptable de l'école
    infos = client.get("/auto-import-helloasso", headers=h).json()
    assert infos["formulas"] == ["Adhésion adulte", "Adhésion en 3 fois", "Stage"]
    comptes = infos["accounts"]
    cotisations = next(c["id"] for c in comptes if c["code"] == "756")
    autre = next(c["id"] for c in comptes if c["code"] == "758")
    regle = client.post("/auto-import", headers=h, json={
        "name": "HelloAsso", "nature": "vente", "source_kind": "helloasso", "target_kind": "docs",
        "target_ref": asc["dossier"],
        "helloasso_accounts": {"Adhésion adulte": cotisations, "Adhésion en 3 fois": cotisations, "Stage": autre}}).json()

    assert client.post(f"/auto-import/{regle['id']}/run", headers=h).json()["created"] == 2
    ventes = db_session.query(NoteFrais).order_by(NoteFrais.id).all()
    assert [v.nature for v in ventes] == ["vente", "vente"]
    lignes = [sorted((d.categorie_id, d.montant_centimes) for d in db_session.query(Depense).filter_by(note_id=v.id))
              for v in ventes]
    assert lignes == [[(cotisations, 20600)], sorted([(cotisations, 10000), (autre, 2000)])]
    noms = {n.name for n in db_session.query(DocNode).filter_by(parent_id=asc["dossier"])}
    assert "Versement HelloAsso 2026-10-10 (reconstituée par l'appli).pdf" in noms
    assert client.post(f"/auto-import/{regle['id']}/run", headers=h).json()["created"] == 0

    # Sans destination : la vente, sans fichier inventé.
    sans = client.post("/auto-import", headers=h, json={"name": "Sans", "nature": "vente", "source_kind": "helloasso"}).json()
    avant = db_session.query(DocNode).count()
    assert client.post(f"/auto-import/{sans['id']}/run", headers=h).json()["created"] == 2
    assert db_session.query(DocNode).count() == avant


def test_pdf_versement_affiche_les_euros_et_son_nom():
    """Le PDF reconstitué montre « € » (pas « · ») et porte un titre lisible
    (sinon la visionneuse affiche un identifiant)."""
    import pymupdf
    from datetime import date

    from auto_import.helloasso_source import Payment, pdf

    data = pdf(date(2026, 2, 9), [Payment("Jules Martin", "Cotisation", 10000, 1, "2025-11-09", date(2026, 2, 9))])
    doc = pymupdf.open(stream=data, filetype="pdf")
    texte = doc[0].get_text()
    assert "100,00 €" in texte and "Jules Martin — Cotisation" in texte
    assert doc.metadata["title"] == "Versement HelloAsso du 09/02/2026 (reconstituée par l'appli)"
