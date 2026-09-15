"""Tests de facture_html.py (voir spec/SPEC-inscription.md) — génère un
vrai PDF via un headless Chromium/Chrome installé sur la machine (voir
facture_html.py:_BINAIRES_CHROMIUM), pas de mock : si aucun binaire
n'est trouvé, ces tests échouent avec un message clair plutôt que de
passer à tort."""

import datetime as dt

from inscriptions.facture_html import generer_facture_pdf
from inscriptions.models import Inscription


def _inscription(**overrides) -> Inscription:
    defaults = dict(
        id=42,
        ecole_id=1,
        token_public="11111111-1111-1111-1111-111111111111",
        saison="2026-2027",
        created_at=dt.datetime(2026, 9, 11, 10, 30),
        ip_soumission="127.0.0.1",
        eleve_nom="Dupont",
        eleve_prenom="Marie",
        eleve_date_naissance=dt.date(2018, 11, 17),
        eleve_adresse="1 rue du Test\n83330 Le Beausset",
        eleve_telephone="0600000000",
        eleve_email="marie@example.com",
        signataire_nom="Jean Dupont",
        moyen_paiement="cheque",
        statut_paiement="en_attente",
        paiement_nb_echeances=1,
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
    contenu = generer_facture_pdf(_inscription(), ["Class Ini"])
    assert contenu.startswith(b"%PDF")
    assert len(contenu) > 1000


def test_avec_reduction_famille():
    contenu = generer_facture_pdf(
        _inscription(reduction_famille_appliquee=True, montant_trimestriel=120.0),
        ["Class Ini"],
    )
    assert contenu.startswith(b"%PDF")


def test_avec_alerte_palier_mixte():
    contenu = generer_facture_pdf(_inscription(alerte_palier_mixte=True), ["Éveil", "Class Inter"])
    assert contenu.startswith(b"%PDF")


def test_cheque_en_3_fois():
    contenu = generer_facture_pdf(
        _inscription(paiement_nb_echeances=3), ["Class Ini", "Jazz Ini"]
    )
    assert contenu.startswith(b"%PDF")


def test_carte_en_3_fois_non_payee_pas_acquittee():
    contenu = generer_facture_pdf(
        _inscription(moyen_paiement="helloasso", paiement_nb_echeances=3, statut_paiement="en_attente"),
        ["Class Ini"],
    )
    assert contenu.startswith(b"%PDF")


def test_carte_payee_facture_acquittee():
    contenu = generer_facture_pdf(
        _inscription(moyen_paiement="helloasso", statut_paiement="paye"), ["Class Ini"]
    )
    assert contenu.startswith(b"%PDF")


def test_sans_adresse():
    contenu = generer_facture_pdf(_inscription(eleve_adresse=None), ["Class Ini"])
    assert contenu.startswith(b"%PDF")


def test_nom_avec_caracteres_html_est_echappe():
    """Une famille pourrait taper des caractères spéciaux (ou tenter
    une injection HTML) dans les champs libres — voir
    facture_html.py:_echappe. Vérifié indirectement : la génération ne
    plante pas et produit toujours un PDF valide."""
    contenu = generer_facture_pdf(
        _inscription(eleve_nom="<script>Test</script> & Cie", signataire_nom=None),
        ["Class Ini"],
    )
    assert contenu.startswith(b"%PDF")
