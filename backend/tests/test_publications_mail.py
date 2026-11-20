"""Une actu envoyée par mail aux adhérents (Seb, 19 novembre 2026 ;
spec/modules/actualites.md §12.13) : un mail à chacun par Brevo, réponses à
l'adresse du club, essai à une adresse, mail seul, désinscription."""

import pytest

from app.main import app, core
from comptes import Comptes
from ecoles import Ecoles
from groups import rights
from publications.publications import blogs_of, publish_right


@pytest.fixture(autouse=True)
def _pas_de_minuteur(monkeypatch):
    monkeypatch.setattr(core.publications_client, "session_factory", None)


@pytest.fixture()
def envois(monkeypatch):
    """Ce que le service du core aurait envoyé : (adresses, contenu de la 1re)."""
    faits = []

    def envoyer_a_chacun(db, ecole_id, adresses, contenu, repondre_a=None, images=None):
        faits.append({"ecole": ecole_id, "adresses": list(adresses), "mails": [contenu(a) for a in adresses],
                      "images": images})
        return list(adresses)

    monkeypatch.setattr(core.publications_client, "send_mails", envoyer_a_chacun)
    return faits


@pytest.fixture()
def club(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="ASC La Ciotat", code_postal="13600")
    ecole.sous_domaine = "asc"
    blog = blogs_of(db_session, ecole.id)[0]
    seb = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Richard", prenom="Seb", email="seb@asc.fr")
    rights.add(db_session, seb, publish_right(blog.id))
    comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Martin", prenom="Zoé", email="zoe@ex.fr")
    # Deux enfants, une même adresse : un seul mail.
    comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Léo", email="famille@ex.fr")
    comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Lou", email="famille@ex.fr")
    comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Sans", prenom="Mail")
    voisin = Ecoles().create(db_session, nom="Fight Lab", code_postal="13600")
    comptes.create(db_session, ecole_id=voisin.id, role="eleve", nom="Voisin", prenom="Ana", email="ana@ex.fr")
    db_session.commit()
    return {"ecole": ecole, "blog": f"/ecoles/{ecole.id}/publications/blogs/{blog.id}"}


def _actu(client, club, **kw):
    reponse = client.post(f"{club['blog']}/posts", json={"body": "Stage de Noël samedi 20 décembre.", **kw})
    assert reponse.status_code == 201, reponse.text
    return reponse.json()


def test_sans_adresse_du_club_pas_de_mail(client, db_session, club, envois):
    # Les réponses doivent arriver au club : sans son adresse, on n'envoie pas.
    assert client.get(f"{club['blog']}/mail").json()["reply_to"] is None
    actu = _actu(client, club)
    refus = client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={})
    assert refus.status_code == 400
    assert "Coordonnées" in refus.json()["detail"]


def _avec_contact(db_session, club):
    club["ecole"].email_contact = "contact@asc.fr"
    db_session.commit()


def test_une_actu_envoyee_par_mail_a_chaque_adherent(client, db_session, club, envois):
    _avec_contact(db_session, club)
    # Une adresse par famille, sans les fiches sans mail ni l'autre école.
    info = client.get(f"{club['blog']}/mail").json()
    assert (info["recipients"], info["reply_to"]) == (3, "contact@asc.fr")

    actu = _actu(client, club)
    demande = client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={})
    assert demande.status_code == 200, demande.text
    assert demande.json() == {"recipients": 3, "test": False}
    # Part 10 s après, comme la notification (Annuler possible) : ici à la main.
    assert core.publications_client.send_mail(db_session, actu["id"]) == 3
    (envoi,) = envois
    assert envoi["adresses"] == ["famille@ex.fr", "seb@asc.fr", "zoe@ex.fr"]
    sujet, texte, html = envoi["mails"][0]
    assert sujet == "Actus · Stage de Noël samedi 20 décembre."
    assert "Stage de Noël samedi 20 décembre." in texte
    assert "Lire sur l’appli" in html and "https://asc." in html
    assert "/api/publications/desinscription/" in html
    # Une seule fois, et l'actu le dit à qui publie.
    assert core.publications_client.send_mail(db_session, actu["id"]) == 0
    assert client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={}).status_code == 409
    feed = client.get(club["blog"]).json()
    assert feed["items"][0]["mailed_to"] == 3


def test_essai_a_une_adresse_sans_rien_marquer(client, db_session, club, envois):
    _avec_contact(db_session, club)
    actu = _actu(client, club, publish=False)
    essai = client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={"test_address": " Moi@Exemple.fr "})
    assert essai.json() == {"recipients": 1, "test": True}
    # L'essai part tout de suite, à cette seule adresse.
    assert envois[0]["adresses"] == ["moi@exemple.fr"]
    # Brouillon : pas de « Lire sur l'appli ».
    assert "Lire sur l’appli" not in envois[0]["mails"][0][2]
    # Rien n'est marqué : l'envoi pour de bon reste possible.
    assert client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={}).status_code == 200
    assert client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={"test_address": "pas-une-adresse"}).status_code == 400


def test_essai_a_plusieurs_adresses(client, db_session, club, envois):
    """Seb, 19 novembre : deux adresses (ou plus), comme dans Gmail."""
    _avec_contact(db_session, club)
    actu = _actu(client, club)
    essai = client.post(f"{club['blog']}/posts/{actu['id']}/mail",
                        json={"test_address": "moi@exemple.fr, Toi@Exemple.fr"})
    assert essai.json() == {"recipients": 2, "test": True}
    assert envois[0]["adresses"] == ["moi@exemple.fr", "toi@exemple.fr"]
    # Une seule mauvaise adresse : rien ne part.
    refus = client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={"test_address": "moi@exemple.fr, toi"})
    assert refus.status_code == 400 and len(envois) == 1


def test_mail_seul_et_annuler(client, db_session, club, envois):
    _avec_contact(db_session, club)
    # Mail seul : l'actu reste en brouillon, le mail part quand même.
    seul = _actu(client, club, publish=False)
    client.post(f"{club['blog']}/posts/{seul['id']}/mail", json={})
    assert core.publications_client.send_mail(db_session, seul["id"]) == 3
    feed = client.get(club["blog"]).json()
    assert feed["items"] == [] and feed["drafts"][0]["mailed_to"] == 3

    # Annuler pendant les 10 s : rien ne part.
    annulee = _actu(client, club)
    client.post(f"{club['blog']}/posts/{annulee['id']}/mail", json={})
    assert client.delete(f"{club['blog']}/posts/{annulee['id']}/mail").status_code == 204
    assert core.publications_client.send_mail(db_session, annulee["id"]) == 0
    # « Annuler » après Publier dépublie et retient aussi le mail.
    depubliee = _actu(client, club)
    client.post(f"{club['blog']}/posts/{depubliee['id']}/mail", json={})
    client.post(f"{club['blog']}/posts/{depubliee['id']}/unpublish")
    assert core.publications_client.send_mail(db_session, depubliee["id"]) == 0
    assert len(envois) == 1


def test_ne_plus_recevoir_les_actus_par_mail(client, db_session, club, envois):
    _avec_contact(db_session, club)
    actu = _actu(client, club)
    client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={})
    core.publications_client.send_mail(db_session, actu["id"])
    html_zoe = envois[0]["mails"][envois[0]["adresses"].index("zoe@ex.fr")][2]
    lien = html_zoe.split("/api")[1].split('"')[0]

    page = client.get(lien)
    assert page.status_code == 200 and "Vous ne recevrez plus les actus par mail" in page.text
    assert client.get(f"{club['blog']}/mail").json()["recipients"] == 2
    # « Annuler » sur la page : réabonnée.
    assert client.post(lien).status_code == 200
    assert client.get(f"{club['blog']}/mail").json()["recipients"] == 3
    # Un lien trafiqué ne fait rien.
    assert client.get(lien[:-3] + "abc").status_code == 404


def test_les_gens_de_l_ecole_pour_completer_l_essai(client, club):
    """Seb, 19 novembre : en tapant quelques lettres, la case de l'essai
    propose les administrateurs, profs et élèves de l'école, pas des autres."""
    gens = client.get(f"{club['blog']}/mail").json()["people"]
    assert gens == [
        {"name": "Lou Roux", "email": "famille@ex.fr"},
        {"name": "Léo Roux", "email": "famille@ex.fr"},
        {"name": "Seb Richard", "email": "seb@asc.fr"},
        {"name": "Zoé Martin", "email": "zoe@ex.fr"},
    ]


def test_texte_mis_en_forme_dans_le_mail(client, db_session, club, envois):
    """§12.15 : le mail garde le gras ; le sujet et la version texte, non."""
    _avec_contact(db_session, club)
    actu = _actu(client, club, body="[grand]Stage de Noël[/grand]\nSamedi [g]20 décembre[/g]")
    client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={})
    core.publications_client.send_mail(db_session, actu["id"])
    sujet, texte, html = envois[0]["mails"][0]
    assert sujet == "Actus · Stage de Noël"
    assert "Stage de Noël\nSamedi 20 décembre" in texte and "[g]" not in texte
    assert "Samedi <strong>20 décembre</strong>" in html


def test_essai_qui_ne_part_pas_le_dit(client, db_session, club, monkeypatch):
    """Seb, 20 novembre : pas de « Essai envoyé » si le mail n'est pas parti."""
    _avec_contact(db_session, club)

    def en_panne(*args, **kwargs):
        raise RuntimeError("Le mail n’est pas parti : expéditeur refusé")

    monkeypatch.setattr(core.publications_client, "send_mails", en_panne)
    actu = _actu(client, club, publish=False)
    refus = client.post(f"{club['blog']}/posts/{actu['id']}/mail", json={"test_address": "moi@exemple.fr"})
    assert refus.status_code == 502
    assert "expéditeur refusé" in refus.json()["detail"]
