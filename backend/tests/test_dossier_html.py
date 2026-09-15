"""Tests de dossier_html.py (voir spec/SPEC-inscription.md) — génère un
vrai PDF via un headless Chromium/Chrome installé sur la machine (voir
dossier_html.py:_BINAIRES_CHROMIUM), pas de mock : si aucun binaire
n'est trouvé, ces tests échouent avec un message clair plutôt que de
passer à tort."""

import datetime as dt

from inscriptions.dossier_html import generer_dossier_pdf
from inscriptions.models import Inscription


def _inscription(**overrides) -> Inscription:
    defaults = dict(
        id=17,
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


def test_produit_un_vrai_pdf():
    contenu = generer_dossier_pdf(_inscription(), ["Class Ini"])
    assert contenu.startswith(b"%PDF")
    assert len(contenu) > 1000


def test_avec_photo(tmp_path):
    from PIL import Image

    chemin_photo = tmp_path / "photo.jpg"
    Image.new("RGB", (120, 160), color=(200, 120, 60)).save(chemin_photo)

    sans_photo = generer_dossier_pdf(_inscription(), ["Class Ini"])
    avec_photo = generer_dossier_pdf(_inscription(), ["Class Ini"], chemin_photo)
    assert avec_photo.startswith(b"%PDF")
    assert len(avec_photo) != len(sans_photo)


def test_photo_illisible_ignoree_sans_planter(tmp_path):
    chemin_photo = tmp_path / "pas-une-image.jpg"
    chemin_photo.write_text("ceci n'est pas une image")

    contenu = generer_dossier_pdf(_inscription(), ["Class Ini"], chemin_photo)
    assert contenu.startswith(b"%PDF")


def test_champs_vides_affiches_comme_non_renseignes():
    contenu = generer_dossier_pdf(
        _inscription(
            eleve_adresse=None,
            eleve_telephone=None,
            eleve_email=None,
            contact_urgence_nom=None,
            allergies=None,
        ),
        [],
    )
    assert contenu.startswith(b"%PDF")


def test_reglement_non_approuve():
    contenu = generer_dossier_pdf(_inscription(reglement_lu_approuve=False), ["Class Ini"])
    assert contenu.startswith(b"%PDF")


def test_alerte_palier_mixte():
    contenu = generer_dossier_pdf(_inscription(alerte_palier_mixte=True), ["Éveil", "Class Inter"])
    assert contenu.startswith(b"%PDF")


def test_signataire_absent():
    contenu = generer_dossier_pdf(_inscription(signataire_nom=None), ["Class Ini"])
    assert contenu.startswith(b"%PDF")


def test_nom_avec_caracteres_html_est_echappe():
    """Voir facture_html.py:test_nom_avec_caracteres_html_est_echappe,
    même principe (voir dossier_html.py:_echappe)."""
    contenu = generer_dossier_pdf(
        _inscription(eleve_nom="<script>Test</script> & Cie"), ["Class Ini"]
    )
    assert contenu.startswith(b"%PDF")
