"""Adresse, ville et SIRET de l'école (spec §6.1, demande du 2026-10-15) :
saisis dans Admin > École, imprimés sur la facture et le dossier."""

from ecoles import Ecoles
from inscriptions.coordonnees_association import ADRESSE_L1, ADRESSE_L2, SIRET, coordonnees


def test_modifier_adresse_ville_siret(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    reponse = client.put(
        f"/ecoles/{ecole.id}",
        json={"adresse": " 8 impasse des Pivoines ", "ville": "Le Beausset", "siret": "123 456 789 00012"},
    )
    assert reponse.status_code == 200
    corps = reponse.json()
    assert (corps["adresse"], corps["ville"], corps["siret"]) == (
        "8 impasse des Pivoines", "Le Beausset", "12345678900012",
    )
    # Un champ vidé redevient vide (le document reprend alors la valeur par défaut).
    assert client.put(f"/ecoles/{ecole.id}", json={"siret": " ", "ville": ""}).json()["siret"] is None


def test_siret_invalide_refuse(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    for siret in ("123 456 789", "1234567890001X", "123456789000123"):
        reponse = client.put(f"/ecoles/{ecole.id}", json={"siret": siret})
        assert reponse.status_code == 400
        assert "14 chiffres" in reponse.json()["detail"]


def test_coordonnees_imprimees(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    # Rien de saisi : les valeurs par défaut, jamais une facture sans adresse.
    assert coordonnees(ecole) == {"ADRESSE_L1": ADRESSE_L1, "ADRESSE_L2": ADRESSE_L2, "SIRET": SIRET}

    ecole.adresse = "Salle des fêtes\nAvenue du Port"
    ecole.ville = "Bandol"
    ecole.siret = "98765432100019"
    assert coordonnees(ecole) == {
        "ADRESSE_L1": "Salle des fêtes, Avenue du Port",
        "ADRESSE_L2": "83330 Bandol",
        "SIRET": "987 654 321 00019",
    }


def test_coordonnees_echappees_dans_le_document():
    """Ce que l'école saisit est échappé avant d'entrer dans le HTML."""
    from types import SimpleNamespace

    from inscriptions import facture_html

    ecole = SimpleNamespace(adresse="1 rue <Haute>", ville="Bandol", code_postal="83150", siret="98765432100019")
    valeurs = facture_html.coordonnees(ecole)
    assert valeurs["SIRET"] == "987 654 321 00019"
    assert facture_html._echappe(valeurs["ADRESSE_L1"]) == "1 rue &lt;Haute&gt;"


def test_iban(client, db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    ok = client.put(f"/ecoles/{ecole.id}", json={"iban": "fr76 3000 6000 0112 3456 7890 189"})
    assert ok.status_code == 200 and ok.json()["iban"] == "FR7630006000011234567890189"
    faux = client.put(f"/ecoles/{ecole.id}", json={"iban": "FR76 3000 6000 0112 3456 7890 188"})
    assert faux.status_code == 400 and "incorrect" in faux.json()["detail"]
    assert client.put(f"/ecoles/{ecole.id}", json={"iban": "12345"}).status_code == 400
    assert client.put(f"/ecoles/{ecole.id}", json={"iban": ""}).json()["iban"] is None


def test_adresses_mail_de_l_ecole(client, db_session):
    from ecoles import Ecoles

    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    reponse = client.put(
        f"/ecoles/{ecole.id}", json={"email_contact": " Contact@Asso.fr ", "email_tresorier": "tresorerie@asso.fr"}
    )
    assert reponse.status_code == 200, reponse.text
    assert reponse.json()["email_contact"] == "contact@asso.fr"
    assert reponse.json()["email_tresorier"] == "tresorerie@asso.fr"
    assert client.put(f"/ecoles/{ecole.id}", json={"email_tresorier": "pas une adresse"}).status_code in (400, 422)
