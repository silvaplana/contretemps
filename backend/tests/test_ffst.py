"""Module FFST, étape 1 (spec/modules/ffst.md §2-4) : la connexion du club,
la lecture des trois listes du site de la FFST, la copie de la dernière
lecture et le statut FFST des adhérents. Aucun appel au vrai site : les
pages sont fabriquées, au format WEBDEV que lit Sambo Admin."""

import httpx
import pytest
from comptes import Comptes
from conftest import entetes_session
from ecoles import Ecoles
from ffst import site
from ffst.club import Club, name_key

IDENTIFIANTS = {"part1": "21", "part2": "13", "part3": "1230", "password": "le-mot-de-passe"}


def page_webdev(lignes, entete="", formulaire="VISU_LICENCES_CLUB"):
    """Une page du site : le formulaire WEBDEV et le tableau « A1 » en XML échappé."""
    colonnes = ["Nom et Prénom", "Né(e) le", "Type", "Licence n°"]
    xml = "<TABLE><COLONNES>" + "".join(f'<C TITRE="{c}"/>' for c in colonnes) + "</COLONNES><LIGNES>"
    xml += "".join("<L>" + "".join(f"<V>{v}</V>" for v in ligne) + "</L>" for ligne in lignes) + "</LIGNES></TABLE>"
    xml = xml.replace("<", "\\x3C").replace(">", "\\x3E").replace('"', '\\"')
    return (
        f'{entete}<form name="{formulaire}" action="/PAGE_SUIVANTE">'
        '<input type="hidden" name="WD_ACTION_" value="&amp;x">'
        f'<script>DeclareChamp("A1",1,WDTable,["{xml}",0,1,2,3,4,[]]);</script>'
    )


def test_lire_un_tableau_webdev():
    lignes = [["DUPONT Jean", "01/02/1990", "Pratiquant", "047012345"]]
    assert site.parse_table(page_webdev(lignes)) == [
        {"Nom et Prénom": "DUPONT Jean", "Né(e) le": "01/02/1990", "Type": "Pratiquant", "Licence n°": "047012345"}
    ]
    with pytest.raises(site.FfstError, match="a changé"):
        site.parse_table("<html>autre chose</html>")


@pytest.fixture()
def faux_site(monkeypatch):
    """Le site de la FFST simulé derrière httpx : connexion, puis clic M32
    (demandes validées) ou M39 (panier)."""
    requetes = []

    def repondre(request: httpx.Request) -> httpx.Response:
        corps = dict(httpx.QueryParams(request.content.decode())) if request.method == "POST" else {}
        requetes.append((request.method, request.url.path, corps))
        if request.method == "GET":
            return httpx.Response(200, text='<form name="ACCUEIL" action="/CONNEXION"></form>')
        if request.url.path == "/CONNEXION":
            if corps.get("A3") != "le-mot-de-passe":
                return httpx.Response(200, text="Identifiant incorrect")
            return httpx.Response(200, text=page_webdev([["MARTIN Léa", "02/03/2001", "Pratiquant", "1"]], "Visu_Licences_Club"))
        if corps.get("WD_BUTTON_CLICK_") == "M32":
            return httpx.Response(200, text=page_webdev([["BENALI Yanis", "", "", ""]], "Renouvellement de licences"))
        return httpx.Response(200, text=page_webdev([["CASTEL Maëlle", "", "", ""]], "Panier"))

    vrai_client = httpx.Client
    monkeypatch.setattr(site.httpx, "Client", lambda **kw: vrai_client(transport=httpx.MockTransport(repondre), **kw))
    return requetes


def test_lire_les_trois_listes_comme_sambo_admin(faux_site):
    login = site.Login("21", "13", "1230", "le-mot-de-passe")
    listes = site.read_all(login)
    assert [r["Nom et Prénom"] for r in listes[site.LICENSEES]] == ["MARTIN Léa"]
    assert [r["Nom et Prénom"] for r in listes[site.VALIDATED]] == ["BENALI Yanis"]
    assert [r["Nom et Prénom"] for r in listes[site.DRAFTS]] == ["CASTEL Maëlle"]
    connexion = next(c for m, p, c in faux_site if p == "/CONNEXION")
    assert (connexion["A5"], connexion["A9"], connexion["A10"], connexion["WD_BUTTON_CLICK_"]) == ("21", "13", "1230", "A7")
    # Le clic garde les champs cachés du formulaire.
    assert any(c.get("WD_BUTTON_CLICK_") == "M39" and c.get("WD_ACTION_") == "&x" for _, _, c in faux_site)
    with pytest.raises(site.FfstAuthError, match="refuse"):
        site.check(site.Login("21", "13", "1230", "faux"))


def test_rapprochement_par_nom_et_prenom():
    # Sans accent, majuscule, apostrophe ni espace en trop (Sambo Admin).
    assert name_key("  M'Hadjou   Léo ") == name_key("M HADJOU Leo") == "m hadjou leo"
    listes = {
        site.LICENSEES: [{"Nom et Prénom": "FERRAND Hugo"}],
        site.VALIDATED: [{"Nom et Prénom": "MOREL Karim"}, {"Nom et Prénom": "FERRAND Hugo"}],
        site.DRAFTS: [{"Nom et Prénom": "CASTEL Maëlle"}],
    }
    personnes = [(1, "Ferrand", "Hugo"), (2, "Morel", "Karim"), (3, "Castel", "Maelle"), (4, "Roux", "Lina")]
    assert Club.statuses(listes, personnes) == {
        1: "Licence créée", 2: "Validée, à payer", 3: "Brouillon", 4: "Inconnu",
    }


@pytest.fixture()
def ecole(db_session):
    return Ecoles().create(db_session, nom="Alliance Sambo Combat La Ciotat", code_postal="13600")


@pytest.fixture()
def ffst(monkeypatch):
    from app import main

    etat = {"listes": None, "appels": []}

    def check(login):
        etat["appels"].append(login)
        if login.password != "le-mot-de-passe":
            raise site.FfstAuthError("Le site de la FFST refuse cet identifiant ou ce mot de passe.")
        return 12

    def read_all(login):
        if etat["listes"] is None:
            raise site.FfstError("Le site de la FFST ne répond pas, réessayez plus tard.")
        return etat["listes"]

    monkeypatch.setattr(main.core.ffst_club, "check", check)
    monkeypatch.setattr(main.core.ffst_club, "read_all", read_all)
    return etat


def test_connexion_du_club(client, db_session, ecole, ffst):
    from ffst import FfstConnection

    url = f"/ecoles/{ecole.id}/ffst"
    assert client.get(url).json() == {
        "connected": False, "login": None, "connected_at": None, "settings": None, "school_town": None,
    }
    faux = client.post(f"{url}/tester", json={**IDENTIFIANTS, "password": "faux"})
    assert faux.status_code == 422 and "refuse" in faux.json()["detail"]
    assert client.post(f"{url}/tester", json={**IDENTIFIANTS, "part1": " 21 "}).json() == {"licensees": 12}
    assert ffst["appels"][-1].part1 == "21"
    # Tester n'enregistre rien.
    assert client.get(url).json()["connected"] is False

    assert client.put(url, json=IDENTIFIANTS).json() == {"licensees": 12}
    etat = client.get(url).json()
    assert (etat["connected"], etat["login"]) == (True, "21 / 13 / 1230")
    # Le mot de passe est chiffré en base et se relit pour retester.
    assert "le-mot-de-passe" not in db_session.query(FfstConnection).one().password_encrypted
    assert client.post(f"{url}/retester").json() == {"licensees": 12}
    assert ffst["appels"][-1].password == "le-mot-de-passe"


def test_copie_de_la_derniere_lecture(client, db_session, ecole, ffst):
    url = f"/ecoles/{ecole.id}/ffst"
    assert client.get(f"{url}/listes").json() == {"connected": False, "read_at": None, "lists": {}, "error": None}
    eleve = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="Castel", prenom="Maëlle")
    autre = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Lina")

    ffst["listes"] = {site.LICENSEES: [], site.VALIDATED: [], site.DRAFTS: [{"Nom et Prénom": "CASTEL Maëlle"}]}
    client.put(url, json=IDENTIFIANTS)  # première lecture tout de suite
    lu = client.get(f"{url}/listes").json()
    assert lu["lists"][site.DRAFTS] == [{"Nom et Prénom": "CASTEL Maëlle"}] and lu["read_at"]
    statuts = client.get(f"{url}/adherents").json()["members"]
    assert statuts[str(eleve.id)]["status"] == "Brouillon" and statuts[str(autre.id)]["status"] == "Inconnu"

    # Rafraîchir : la copie est remplacée en entier.
    ffst["listes"] = {site.LICENSEES: [{"Nom et Prénom": "CASTEL Maëlle"}], site.VALIDATED: [], site.DRAFTS: []}
    relu = client.post(f"{url}/lire").json()
    assert relu["lists"][site.DRAFTS] == [] and relu["error"] is None
    assert client.get(f"{url}/adherents").json()["members"][str(eleve.id)]["status"] == "Licence créée"

    # Le site ne répond pas : la dernière lecture reste, avec le message.
    ffst["listes"] = None
    panne = client.post(f"{url}/lire").json()
    assert "ne répond pas" in panne["error"]
    assert panne["lists"][site.LICENSEES] == [{"Nom et Prénom": "CASTEL Maëlle"}]


def test_ecoles_etanches(client, db_session, ecole, ffst):
    ffst["listes"] = {site.LICENSEES: [{"Nom et Prénom": "CASTEL Maëlle"}], site.VALIDATED: [], site.DRAFTS: []}
    client.put(f"/ecoles/{ecole.id}/ffst", json=IDENTIFIANTS)
    autre = Ecoles().create(db_session, nom="Le Beausset", code_postal="83330")
    assert client.get(f"/ecoles/{autre.id}/ffst/listes").json()["connected"] is False
    assert client.get(f"/ecoles/{autre.id}/ffst/adherents").json() == {"connected": False, "read_at": None, "members": {}}


@pytest.mark.rbac_reel
def test_droits_et_module_eteint(client, db_session, ecole, ffst):
    from app import main
    from registry import activation

    proprietaire = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Noir", prenom="Léo")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Blanc", prenom="Ima")
    eleve = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom="Roux", prenom="Lina")
    url = f"/ecoles/{ecole.id}/ffst"
    activation.set_enabled(db_session, ecole.id, main.MODULES, "ffst", True)
    # Les identifiants : l'administrateur principal ; les listes : tout admin.
    assert client.get(url, headers=entetes_session(admin)).status_code == 403
    assert client.get(url, headers=entetes_session(proprietaire)).status_code == 200
    assert client.get(f"{url}/listes", headers=entetes_session(admin)).status_code == 200
    assert client.get(f"{url}/listes", headers=entetes_session(eleve)).status_code == 403
    # Module éteint (Contretemps, Le Beausset) : introuvable.
    activation.set_enabled(db_session, ecole.id, main.MODULES, "ffst", False)
    assert client.get(f"{url}/listes", headers=entetes_session(admin)).status_code == 404
    assert client.get(f"{url}/adherents", headers=entetes_session(admin)).status_code == 404


def test_helloasso_et_ffst_eteints_dans_une_nouvelle_ecole(db_session):
    """Seb, 18/11 : HelloAsso et FFST ne sont pas allumés par défaut."""
    from app import main
    from registry import activation

    ecole = Ecoles().create(db_session, nom="Nouveau club", code_postal="13000")
    assert {"helloasso", "ffst"} <= activation.disabled(db_session, ecole.id)
    assert "messaging" not in activation.disabled(db_session, ecole.id)
    activation.set_enabled(db_session, ecole.id, main.MODULES, "ffst", True)
    assert not {"helloasso", "ffst"} & activation.disabled(db_session, ecole.id)


def test_migration_garde_l_etat_des_ecoles_existantes(tmp_path, monkeypatch):
    """Contretemps et Le Beausset ne bougent pas ; ASC La Ciotat (combat) a
    HelloAsso et FFST allumés."""
    from pathlib import Path

    import sqlalchemy as sa
    from alembic import command
    from alembic.config import Config

    backend = Path(__file__).resolve().parents[1]
    url = f"sqlite:///{tmp_path / 'avant.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    config = Config(str(backend / "alembic.ini"))
    config.set_main_option("script_location", str(backend / "alembic"))
    command.upgrade(config, "b7d2a9c4e1f3")
    moteur = sa.create_engine(url)
    with moteur.begin() as c:
        for ecole_id, nom, nature in ((1, "Contretemps", "danse"), (2, "Le Beausset", "danse"), (3, "ASC La Ciotat", "combat")):
            c.execute(sa.text(
                "INSERT INTO ecoles (id, nom, code_postal, sous_domaine, nature, created_at) "
                f"VALUES ({ecole_id}, '{nom}', '83000', 'e{ecole_id}', '{nature}', CURRENT_TIMESTAMP)"
            ))
        # Contretemps a éteint HelloAsso ; Le Beausset et ASC n'ont pas de ligne (allumé).
        c.execute(sa.text("INSERT INTO org_modules (org_id, module_key, enabled, updated_at) VALUES (1, 'helloasso', 0, CURRENT_TIMESTAMP)"))
    command.upgrade(config, "head")
    with moteur.connect() as c:
        lignes = c.execute(sa.text(
            "SELECT org_id, module_key, enabled FROM org_modules WHERE module_key IN ('helloasso', 'ffst') ORDER BY org_id, module_key"
        )).all()
    assert lignes == [
        (1, "ffst", 0), (1, "helloasso", 0),
        (2, "ffst", 0), (2, "helloasso", 1),
        (3, "ffst", 1), (3, "helloasso", 1),
    ]


# --- Étape 2 : faire et supprimer les demandes (spec §5) ---


def test_date_de_naissance_et_genre_pour_le_site():
    from datetime import date

    from ffst.club import birth_date, gender

    assert birth_date("05/11/0017", today=date(2026, 11, 18)) == "05/11/2017"
    assert birth_date("05/11/0085", today=date(2026, 11, 18)) == "05/11/1985"
    assert birth_date("2009-03-14") == "14/03/2009"
    assert birth_date("") is None
    assert (gender("Homme"), gender(" femme"), gender("F"), gender("?"), gender(None)) == ("H", "F", "F", None, None)
    assert (site.site_name("M’Hadjou  "), site.site_city("élancourt"), site.site_city("laciotat")) == (
        "M Hadjou", "Elancourt", "Laciotat")


def test_reponses_du_formulaire_d_asc():
    from ffst.club import answers_of

    reponses = [
        {"name": "Genre(H/F)", "answer": "H"},
        {"name": "date de naissance", "answer": "14/03/2009"},
        {"name": "Ville de naissance", "answer": "Marseille"},
        {"name": "Adresse", "answer": "12 avenue de la Pétanque"},
        {"name": "Adresse mail des parents", "answer": "p@test.fr"},
        {"name": "code postal", "answer": "13600"},
        {"name": "Ville", "answer": "La Ciotat"},
        {"name": "Numéro de téléphone", "answer": "0600000001"},
    ]
    assert answers_of(reponses) == {
        "gender": "H", "birth_date": "14/03/2009", "address": "12 avenue de la Pétanque",
        "postal_code": "13600", "city": "La Ciotat", "phone": "0600000001",
    }


@pytest.fixture()
def ecrit(monkeypatch, ffst):
    """Le navigateur simulé : ce qui part vers le site."""
    from app import main

    club = main.core.ffst_club
    ffst["demandes"], ffst["retraits"] = [], []

    def create_request(login, person, fonction, settings):
        ffst["demandes"].append((person, fonction, settings))
        ffst["listes"][site.DRAFTS].append({"Nom et Prénom": f"{person.last_name.upper()} {person.first_name}"})
        return ["Commune de naissance mise par défaut."] if fonction != site.PRATIQUANT else []

    def delete_draft(login, nom, prenom):
        ffst["retraits"].append((nom, prenom))
        ffst["listes"][site.DRAFTS] = []

    monkeypatch.setattr(club, "create_request", create_request)
    monkeypatch.setattr(club, "delete_draft", delete_draft)
    return ffst


def _adherent_helloasso(db_session, ecole, nom, prenom, reponses):
    from helloasso import HelloAssoRegistration
    from saisons import saison_courante_id

    eleve = Comptes().create(db_session, ecole_id=ecole.id, role="eleve", nom=nom, prenom=prenom)
    db_session.add(HelloAssoRegistration(
        org_id=ecole.id, season_id=saison_courante_id(db_session, ecole.id), item_id=f"i{eleve.id}",
        order_id="o1", member_id=eleve.id, first_name=prenom, last_name=nom, payer_email="payeur@test.fr",
        state="Processed", answers=reponses,
    ))
    db_session.commit()
    return eleve


def test_faire_puis_supprimer_une_demande(client, db_session, ecole, ecrit):
    ecrit["listes"] = {site.LICENSEES: [], site.VALIDATED: [], site.DRAFTS: []}
    url = f"/ecoles/{ecole.id}/ffst"
    client.put(url, json=IDENTIFIANTS)
    assert client.put(f"{url}/reglages", json={"discipline": "0470-SAMBO", "default_birth_town": "", "image_rights": True}).status_code == 200
    eleve = _adherent_helloasso(db_session, ecole, "M'Hadjou", "Léo", [
        {"name": "date de naissance", "answer": "05/11/0017"}, {"name": "Ville", "answer": "La Ciotat"},
    ])
    ligne = client.get(f"{url}/adherents").json()["members"][str(eleve.id)]
    assert ligne == {"status": "Inconnu", "gender_known": False}

    # Genre choisi à l'écran, le reste lu dans le formulaire HelloAsso.
    reponse = client.post(f"{url}/adherents/{eleve.id}/demande", json={"fonction": "004-ENTRAINEUR", "gender": "F"})
    assert reponse.json() == {"warnings": ["Commune de naissance mise par défaut."]}
    personne, fonction, reglages = ecrit["demandes"][-1]
    assert (personne.last_name, personne.gender, personne.birth_date, personne.city, personne.email) == (
        "M'Hadjou", "F", "05/11/2017", "La Ciotat", "payeur@test.fr")
    assert (fonction, reglages.discipline, reglages.default_birth_town) == ("004-ENTRAINEUR", "0470-SAMBO", "")
    # Le site est relu après l'action : la personne est dans le panier.
    assert client.get(f"{url}/adherents").json()["members"][str(eleve.id)]["status"] == "Brouillon"

    # Déjà dans le panier : rien ne part.
    refus = client.post(f"{url}/adherents/{eleve.id}/demande", json={})
    assert refus.status_code == 422 and "Brouillon" in refus.json()["detail"]
    assert len(ecrit["demandes"]) == 1

    assert client.delete(f"{url}/adherents/{eleve.id}/demande").status_code == 204
    assert ecrit["retraits"] == [("M'Hadjou", "Léo")]
    assert client.get(f"{url}/adherents").json()["members"][str(eleve.id)]["status"] == "Inconnu"
    # Plus dans le panier : rien ne part.
    assert client.delete(f"{url}/adherents/{eleve.id}/demande").status_code == 422
    assert len(ecrit["retraits"]) == 1


def test_relit_le_site_avant_d_ecrire(client, db_session, ecole, ecrit):
    """Pendant que Sambo Admin écrit aussi : la copie dit Inconnu, le site
    a déjà la demande."""
    ecrit["listes"] = {site.LICENSEES: [], site.VALIDATED: [], site.DRAFTS: []}
    url = f"/ecoles/{ecole.id}/ffst"
    client.put(url, json=IDENTIFIANTS)
    eleve = _adherent_helloasso(db_session, ecole, "Castel", "Maëlle", [{"name": "Genre(H/F)", "answer": "Femme"}])
    assert client.get(f"{url}/adherents").json()["members"][str(eleve.id)] == {"status": "Inconnu", "gender_known": True}
    ecrit["listes"][site.VALIDATED] = [{"Nom et Prénom": "CASTEL Maëlle"}]
    refus = client.post(f"{url}/adherents/{eleve.id}/demande", json={})
    assert refus.status_code == 422 and "Validée" in refus.json()["detail"]
    assert ecrit["demandes"] == []
    # Le site ne répond pas : rien ne part non plus.
    ecrit["listes"] = None
    assert client.post(f"{url}/adherents/{eleve.id}/demande", json={}).status_code == 422
    assert ecrit["demandes"] == []


def test_ecole_etanche_pour_les_demandes(client, db_session, ecole, ecrit):
    ecrit["listes"] = {site.LICENSEES: [], site.VALIDATED: [], site.DRAFTS: []}
    client.put(f"/ecoles/{ecole.id}/ffst", json=IDENTIFIANTS)
    autre = Ecoles().create(db_session, nom="Le Beausset", code_postal="83330")
    etranger = Comptes().create(db_session, ecole_id=autre.id, role="eleve", nom="Roux", prenom="Lina")
    assert client.post(f"/ecoles/{ecole.id}/ffst/adherents/{etranger.id}/demande", json={}).status_code == 404
    assert ecrit["demandes"] == []
