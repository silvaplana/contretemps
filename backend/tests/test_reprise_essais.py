"""Reprise des élèves à l'essai de Sambo Admin (spec/modules/essai.md §9
étape 3) : sur une copie de sa base, faite ici avec son schéma."""

import sqlite3
from datetime import date

import pytest
from ecoles import Ecoles

# Les tables d'essai de Sambo Admin (silvaplana/test-python,
# backend/src/database/database.py, migrations 1 à 3).
SCHEMA = """
CREATE TABLE trial_students (
    id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, last_name TEXT NOT NULL, birth_date TEXT,
    gender TEXT, email TEXT, phone TEXT, parent_name TEXT,
    medical_attestation INTEGER NOT NULL DEFAULT 0, medical_certificate_file TEXT,
    parental_consent INTEGER NOT NULL DEFAULT 0, waiver_accepted INTEGER NOT NULL DEFAULT 0,
    signature_png BLOB, signed_at TEXT, signed_ip TEXT, terms_version TEXT, qr_token TEXT UNIQUE,
    qr_created_at TEXT, course1_date TEXT, course1_mode TEXT, course2_date TEXT, course2_mode TEXT,
    comment TEXT NOT NULL DEFAULT '', source TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    age INTEGER, family_id TEXT
);
CREATE TABLE trial_signatures (
    id INTEGER PRIMARY KEY, family_id TEXT NOT NULL, signer_name TEXT NOT NULL, role TEXT NOT NULL,
    png BLOB NOT NULL, signed_at TEXT NOT NULL, signed_ip TEXT
);
"""


@pytest.fixture()
def sambo():
    base = sqlite3.connect(":memory:")
    base.row_factory = sqlite3.Row
    base.executescript(SCHEMA)
    eleve = (
        "INSERT INTO trial_students (first_name, last_name, birth_date, email, parent_name, medical_certificate_file, "
        "waiver_accepted, signature_png, signed_at, signed_ip, qr_token, course1_date, course1_mode, comment, source, "
        "created_at, updated_at, age, family_id) VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, 'web', ?, ?, ?, ?)"
    )
    t = "2026-10-01T18:00:00+00:00"
    # Une famille de 2 (la mère et son fils de 10 ans), signatures dans trial_signatures.
    base.execute(eleve, ("Karima", "Benali", None, "k@exemple.fr", None, "c1.jpg", None, None, "1.2.3.4", "jeton-karima", "2026-10-02", "qr", "", t, t, None, "fam1"))
    base.execute(eleve, ("Yanis", "Benali", None, "k@exemple.fr", "Karima Benali", "c2.jpg", None, None, "1.2.3.4", "jeton-yanis", None, None, "Revient samedi", t, t, 10, "fam1"))
    base.execute("INSERT INTO trial_signatures (family_id, signer_name, role, png, signed_at, signed_ip) VALUES ('fam1', 'Karima', 'first', x'89', ?, '1.2.3.4')", (t,))
    # Un des premiers inscrits : date de naissance, signature sur sa ligne, pas de famille.
    base.execute(eleve, ("Lou", "Petit", "2014-03-01", "lou@exemple.fr", "Anne Petit", None, b"\x89PNG", t, None, "jeton-lou", None, None, "", "2026-09-20T10:00:00", t, None, None))
    # Ajouté à la main, sans QR code ni e-mail.
    base.execute(eleve, ("Marc", "Roux", None, None, None, None, None, None, None, None, "2026-10-05", "manual", "", "2026-10-05T19:00:00Z", t, None, None))
    return base


def test_reprise_des_inscrits_de_sambo_admin(client, db_session, sambo):
    from app.reprise_essais import reprendre
    from trials import TrialSettings, TrialSignature, TrialStudent, TrialTerms

    ecole = Ecoles().create(db_session, nom="Alliance Sambo Combat La Ciotat", code_postal="13600")

    # Essai à blanc : rien d'écrit.
    assert reprendre(db_session, ecole.id, sambo, essai=True)[-1] == "4 inscrit(s) repris, 0 déjà là, 2 signature(s)."
    assert db_session.query(TrialStudent).count() == 0

    reprendre(db_session, ecole.id, sambo)
    eleves = {e.first_name: e for e in db_session.query(TrialStudent)}
    assert set(eleves) == {"Karima", "Yanis", "Lou", "Marc"}
    karima, yanis, lou, marc = eleves["Karima"], eleves["Yanis"], eleves["Lou"], eleves["Marc"]
    # Même QR code : celui envoyé par Sambo Admin marche au scan.
    assert karima.token == "jeton-karima" and karima.family == yanis.family == "fam1"
    assert (karima.course1_date, karima.course1_mode, karima.age) == (date(2026, 10, 2), "qr", None)
    assert (yanis.age, yanis.parent_name, yanis.comment) == (10, "Karima Benali", "Revient samedi")
    assert karima.certificate_at is not None and lou.certificate_at is None
    assert lou.age == 12 and lou.family == f"sambo-{3}"
    assert marc.email == "" and marc.token and marc.course1_mode == "manual"

    signatures = {s.signer_name: s for s in db_session.query(TrialSignature)}
    assert set(signatures) == {"Karima", "Anne Petit"}
    assert signatures["Anne Petit"].children == ["Lou Petit"] and signatures["Karima"].children == []

    # La page d'essai, encore vide, reçoit les textes de Sambo Admin.
    reglages = db_session.query(TrialSettings).one()
    assert reglages.min_age == 9 and len(reglages.schedule) == 4 and reglages.contacts[0]["name"] == "Roland"
    terms = db_session.get(TrialTerms, reglages.terms_id)
    assert "[club]" in terms.waiver and karima.terms_id == terms.id

    scan = client.post(f"/ecoles/{ecole.id}/trials/checkin", json={"code": "https://silvaplana.cloud/sambo-admin/?essai=jeton-yanis"})
    assert scan.json()["status"] == "added"

    # Relancée : rien de neuf.
    assert reprendre(db_session, ecole.id, sambo)[-1] == "0 inscrit(s) repris, 4 déjà là, 0 signature(s)."
    assert db_session.query(TrialStudent).count() == 4
