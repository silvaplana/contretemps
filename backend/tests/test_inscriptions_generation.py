"""Tests de pdf.py/excel_export.py/email_envoi.py (voir
spec/SPEC-inscription.md) — écrit dans le vrai dossier de stockage par
défaut puis nettoie (même patron que test_videos.py:test_upload_reel),
pas de monkeypatch d'env (les chemins sont résolus au niveau module)."""

import datetime as dt
import smtplib

import pytest
from inscriptions import excel_export
from inscriptions.email_envoi import EmailEnvoi
from inscriptions.models import Inscription
from inscriptions.pdf import generer_dossier_pdf, generer_facture_pdf
from openpyxl import load_workbook


def _inscription(**overrides) -> Inscription:
    defaults = dict(
        ecole_id=1,
        token_public="11111111-1111-1111-1111-111111111111",
        saison="2026-2027",
        created_at=dt.datetime(2026, 9, 11, 10, 30),
        ip_soumission="127.0.0.1",
        eleve_nom="Dupont",
        eleve_prenom="Marie",
        eleve_date_naissance=dt.date(2018, 11, 17),
        eleve_adresse="1 rue du Test",
        eleve_telephone="0600000000",
        eleve_email="marie@example.com",
        allergies=None,
        traitement_medical=None,
        informations_importantes=None,
        contact_urgence_nom="Dupont",
        contact_urgence_prenom="Jean",
        contact_urgence_lien="Père",
        contact_urgence_telephone="0611111111",
        droit_image_autorise=True,
        droit_image_site=True,
        droit_image_reseaux=False,
        droit_image_affiches=False,
        reglement_lu_approuve=True,
        signataire_nom="Jean Dupont",
        moyen_paiement="cheque",
        statut_paiement="en_attente",
        palier_tarifaire="initiation_moyen",
        nb_cours_semaine=1,
        montant_adhesion=40.0,
        montant_mensuel_septembre=42.0,
        montant_trimestriel=125.0,
        reduction_famille_appliquee=False,
        alerte_palier_mixte=False,
    )
    defaults.update(overrides)
    return Inscription(**defaults)


def test_generer_dossier_pdf_produit_un_vrai_pdf():
    contenu = generer_dossier_pdf(_inscription(), ["Class Ini"])
    assert contenu.startswith(b"%PDF")
    assert len(contenu) > 500


def test_generer_facture_pdf_produit_un_vrai_pdf():
    contenu = generer_facture_pdf(_inscription())
    assert contenu.startswith(b"%PDF")


def test_generer_facture_pdf_avec_alerte_palier_mixte():
    contenu = generer_facture_pdf(_inscription(alerte_palier_mixte=True))
    assert contenu.startswith(b"%PDF")


def test_excel_cree_le_fichier_avec_les_bons_en_tetes_et_ajoute_des_lignes(tmp_path):
    chemin = tmp_path / "nouvelles_inscriptions_1_2026-2027.xlsx"
    excel_export.ajouter_ligne(chemin, _inscription(), ["Class Ini", "Jazz Ini"])
    excel_export.ajouter_ligne(
        chemin, _inscription(eleve_nom="Martin", eleve_prenom="Léo"), ["Éveil"]
    )

    classeur = load_workbook(chemin)
    feuille = classeur.active
    lignes = list(feuille.iter_rows(values_only=True))

    assert lignes[0] == (
        "Nom adhérent", "Prénom adhérent", "Nom - Prénom parent", "E-Mail", "Adresse",
        "Téléphone", "Age", *excel_export.NOMS_COURS,
    )
    assert lignes[1][0] == "Dupont"
    assert lignes[1][6] == "17/11/2018 = 7 ans"
    # "Class Ini" et "Jazz Ini" marqués, les autres colonnes cours vides.
    index_class_ini = excel_export.NOMS_COURS.index("Class Ini")
    index_jazz_ini = excel_export.NOMS_COURS.index("Jazz Ini")
    index_eveil = excel_export.NOMS_COURS.index("Éveil")
    assert lignes[1][7 + index_class_ini] == "X"
    assert lignes[1][7 + index_jazz_ini] == "X"
    assert lignes[1][7 + index_eveil] is None

    assert lignes[2][0] == "Martin"
    assert lignes[2][7 + index_eveil] == "X"
    assert lignes[2][7 + index_class_ini] is None


def test_email_desactive_sans_config(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    monkeypatch.delenv("SMTP_USER", raising=False)
    monkeypatch.delenv("SMTP_PASSWORD", raising=False)
    service = EmailEnvoi()
    assert service.actif is False
    # Ne lève rien, ne fait rien.
    service.envoyer_confirmation("a@b.fr", "Sujet", "Corps", [])


def test_email_envoie_avec_pieces_jointes(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "admin@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    appels = {}

    class FauxSMTP:
        def __init__(self, hote, port):
            appels["hote"] = hote
            appels["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def starttls(self):
            appels["starttls"] = True

        def login(self, utilisateur, mot_de_passe):
            appels["login"] = (utilisateur, mot_de_passe)

        def sendmail(self, expediteur, destinataire, message):
            appels["sendmail"] = (expediteur, destinataire, message)

    monkeypatch.setattr(smtplib, "SMTP", FauxSMTP)

    service = EmailEnvoi()
    assert service.actif is True
    service.envoyer_confirmation(
        "famille@example.com",
        "Confirmation",
        "Merci pour votre inscription.",
        [("dossier.pdf", b"%PDF-fake"), ("facture.pdf", b"%PDF-fake2")],
    )

    assert appels["login"] == ("admin@example.com", "secret")
    expediteur, destinataire, message = appels["sendmail"]
    assert destinataire == "famille@example.com"
    assert "dossier.pdf" in message
    assert "facture.pdf" in message


def test_email_erreur_smtp_est_propagee(monkeypatch):
    """L'appelant (inscriptions.py) attrape cette exception — vérifié ici
    juste qu'elle n'est PAS avalée silencieusement à ce niveau (voir
    inscriptions.py:creer, qui doit journaliser sans bloquer)."""
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_USER", "admin@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")

    class FauxSMTPEnErreur:
        def __init__(self, hote, port):
            pass

        def __enter__(self):
            raise smtplib.SMTPException("boom")

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(smtplib, "SMTP", FauxSMTPEnErreur)

    service = EmailEnvoi()
    with pytest.raises(smtplib.SMTPException):
        service.envoyer_confirmation("a@b.fr", "Sujet", "Corps", [])
