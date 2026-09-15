"""Tests du 2e email d'inscription — à l'administrateur (voir
inscriptions.py:_notifier_admin, spec/SPEC-inscription.md). Le
singleton `Inscriptions` (voir app.main:inscriptions_client) est déjà
construit à l'import de l'appli : `email.envoyer_confirmation` est
monkeypatché DIRECTEMENT (même patron que
test_inscriptions_paiement_helloasso.py) plutôt que via des variables
d'env SMTP_*, qui ne seraient lues qu'à la construction."""

import shutil

import pytest
from app.main import inscriptions_client
from cours import CoursService
from ecoles import Ecoles
from inscriptions.stockage import DOSSIER_INSCRIPTIONS

NOMS_COURS_REELS = ["Éveil", "Class Ini"]


def _creer_ecole_avec_cours(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    cours_service = CoursService()
    cours = {}
    for nom in NOMS_COURS_REELS:
        cours[nom] = cours_service.create(db_session, ecole_id=ecole.id, nom=nom)
    return ecole, cours


@pytest.fixture()
def _nettoyage_dossier():
    dossiers = []
    yield dossiers
    for dossier in dossiers:
        shutil.rmtree(dossier, ignore_errors=True)


@pytest.fixture()
def _appels_email(monkeypatch):
    """Capture chaque appel à envoyer_confirmation (destinataire, sujet,
    corps, pièces jointes) sans vraiment envoyer — voir docstring du
    module."""
    appels = []
    monkeypatch.setattr(
        inscriptions_client.email,
        "envoyer_confirmation",
        lambda destinataire, sujet, corps, pieces_jointes: appels.append(
            (destinataire, sujet, corps, pieces_jointes)
        ),
    )
    monkeypatch.setattr(inscriptions_client.email, "adresse_admin", "admin-test@example.com")
    return appels


def _donnees_formulaire(cours_ids):
    return {
        "eleve_nom": "Dupont",
        "eleve_prenom": "Marie",
        "eleve_date_naissance": "2018-11-17",
        "eleve_email": "marie@example.com",
        "cours_ids": cours_ids,
        "reglement_lu_approuve": True,
        "signataire_nom": "Jean Dupont",
    }


def test_notifie_admin_en_plus_de_la_famille(client, db_session, _nettoyage_dossier, _appels_email):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Class Ini"].id]),
    ).json()

    client.post(
        f"/inscriptions/{corps['token_public']}/paiement/choix",
        json={"moyen_paiement": "cheque", "paiement_nb_echeances": 1},
    )

    # 2 emails distincts : famille (à eleve_email) + admin.
    assert len(_appels_email) == 2
    destinataires = [a[0] for a in _appels_email]
    assert "marie@example.com" in destinataires
    assert "admin-test@example.com" in destinataires


def test_sujet_et_corps_du_mail_admin(client, db_session, _nettoyage_dossier, _appels_email):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Class Ini"].id]),
    ).json()

    client.post(
        f"/inscriptions/{corps['token_public']}/paiement/choix",
        json={"moyen_paiement": "cheque", "paiement_nb_echeances": 1},
    )

    appel_admin = next(a for a in _appels_email if a[0] == "admin-test@example.com")
    _, sujet, corps_mail, pieces_jointes = appel_admin
    assert sujet == "Inscription de Marie Dupont en base des inscrits"
    assert "Marie Dupont a été ajouté(e) aux nouveaux inscrits" in corps_mail
    assert "Excel officiel" in corps_mail
    assert "application Contretemps" in corps_mail
    # Le fichier "nouvelles inscriptions" est bien joint.
    assert len(pieces_jointes) == 1
    nom_fichier, contenu = pieces_jointes[0]
    assert nom_fichier.endswith(".xlsx")
    assert contenu.startswith(b"PK")  # signature d'un fichier .xlsx (zip)


def test_echec_mail_famille_n_empeche_pas_le_mail_admin(
    client, db_session, _nettoyage_dossier, monkeypatch
):
    ecole, cours = _creer_ecole_avec_cours(db_session)
    _nettoyage_dossier.append(DOSSIER_INSCRIPTIONS / str(ecole.id))
    corps = client.post(
        "/inscriptions",
        params={"ecole_id": ecole.id},
        json=_donnees_formulaire([cours["Class Ini"].id]),
    ).json()

    appels = []

    def _envoyer(destinataire, sujet, corps_mail, pieces_jointes):
        if destinataire == "marie@example.com":
            raise RuntimeError("SMTP en panne")
        appels.append(destinataire)

    monkeypatch.setattr(inscriptions_client.email, "envoyer_confirmation", _envoyer)
    monkeypatch.setattr(inscriptions_client.email, "adresse_admin", "admin-test@example.com")

    reponse = client.post(
        f"/inscriptions/{corps['token_public']}/paiement/choix",
        json={"moyen_paiement": "cheque", "paiement_nb_echeances": 1},
    )
    # L'échec du mail famille ne remonte jamais en erreur HTTP (voir
    # _envoyer_email, jamais bloquant).
    assert reponse.status_code == 200
    # ... et le mail admin part quand même.
    assert appels == ["admin-test@example.com"]
