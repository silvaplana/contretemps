"""Import auto pièces, étape 2 (spec/modules/import-auto-pieces.md) : éteint
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


def test_ventes_attendent(client, db_session, asc):
    h = entetes_session(asc["tresorier"])
    regle = client.post("/auto-import", headers=h, json={"nature": "vente", "source_ref": asc["dossier"]}).json()
    assert "ventes" in client.post(f"/auto-import/{regle['id']}/run", headers=h).json()["message"]


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
