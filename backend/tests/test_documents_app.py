"""Fichiers de l'appli (fichier de base, spec fichier-de-base.md) : nature,
contenu JSON versionné, état, essais et réponses."""

import pytest
from test_documents import Docs, _saison, ecole, stockage  # noqa: F401 (fixtures)

from documents import app_content
from documents.app_content import ContentError

pytestmark = pytest.mark.rbac_reel


def bloc(ident, genre, texte="", **props):
    b = {"id": ident, "type": genre, "props": props, "content": [{"type": "text", "text": texte, "styles": {}}], "children": []}
    return b


SONDAGE = {
    "schema": 1,
    "entry": {
        "blocks": [
            bloc("h1", "heading", "Fête de fin d'année", level=1),
            bloc("q1", "choice", label="Quelle date ?", options="20 juin\n21 juin", required=True),
            bloc("q2", "longText", label="Une remarque ?"),
        ]
    },
    "result": {"blocks": []},
}


def creer(docs, famille="question", parent=None, nom=None):
    return docs.c.post(
        docs.base + "/apps", json={"space": "private", "parent_id": parent, "family": famille, "name": nom}, headers=docs.h
    )


def enregistrer(docs, ident, contenu, **autres):
    return docs.c.put(f"{docs.base}/nodes/{ident}/app", json={"content": contenu, **autres}, headers=docs.h)


def test_creer_un_fichier_vierge(client, ecole):
    prof = Docs(client, ecole["id"], ecole["prof"])
    saison = _saison(prof)["id"]
    r = creer(prof, "question", saison)
    assert r.status_code == 201
    ident = r.json()["id"]
    assert r.json()["name"] == "Nouvelles questions"
    # Deux fichiers neufs : jamais deux fois le même nom.
    assert creer(prof, "question", saison).json()["name"] == "Nouvelles questions (2)"
    f = prof.get(f"/nodes/{ident}/app").json()
    assert f["status"] == "draft" and f["family"] == "question" and f["editable"] is True
    assert f["content"] == app_content.empty_content()
    liste = {e["name"]: e for e in prof.racine(dossier=saison).json()["items"]}
    assert liste["Nouvelles questions"]["kind"] == "app"
    assert creer(prof, "autre", saison).status_code == 422


def test_enregistrer_et_versions(client, ecole):
    prof = Docs(client, ecole["id"], ecole["prof"])
    ident = creer(prof, "question", _saison(prof)["id"]).json()["id"]
    r = enregistrer(prof, ident, SONDAGE, base_version=1)
    # La version de création est gardée ; l'enregistrement en fait une neuve,
    # puis les suivants de la même personne s'y ajoutent (frappe en cours).
    assert r.status_code == 200 and r.json()["version"]["number"] == 2
    assert enregistrer(prof, ident, SONDAGE, base_version=2).json()["version"]["number"] == 2
    assert prof.get(f"/nodes/{ident}/app").json()["content"]["entry"]["blocks"][1]["id"] == "q1"
    # Modifié ailleurs entre-temps : refusé.
    assert enregistrer(prof, ident, SONDAGE, base_version=1).status_code == 409


def test_les_blocs_suivent_la_nature(client, ecole):
    prof = Docs(client, ecole["id"], ecole["prof"])
    ident = creer(prof, "inform", _saison(prof)["id"]).json()["id"]
    r = enregistrer(prof, ident, SONDAGE)
    assert r.status_code == 422 and "Informer" in r.json()["detail"]
    paiement = {**SONDAGE, "entry": {"blocks": [bloc("p", "payment", label="Cotisation", amount=12)]}}
    assert enregistrer(prof, ident, paiement, family="question").status_code == 422
    # Changer de nature en même temps que le contenu.
    assert enregistrer(prof, ident, paiement, family="act").json()["family"] == "act"


def test_pas_de_html_ni_de_lien_douteux(client, ecole):
    prof = Docs(client, ecole["id"], ecole["prof"])
    ident = creer(prof, "inform", _saison(prof)["id"]).json()["id"]
    lien = {"type": "link", "href": "javascript:alert(1)", "content": [{"type": "text", "text": "clic", "styles": {}}]}
    piege = {"schema": 1, "entry": {"blocks": [{"id": "a", "type": "paragraph", "props": {}, "content": [lien]}]}, "result": {"blocks": []}}
    assert enregistrer(prof, ident, piege).status_code == 422
    inconnu = {"schema": 1, "entry": {"blocks": [{"id": "a", "type": "html", "props": {}}]}, "result": {"blocks": []}}
    assert enregistrer(prof, ident, inconnu).status_code == 422


def test_l_etat_ouvre_et_ferme_les_modifications(client, ecole):
    prof, admin = Docs(client, ecole["id"], ecole["prof"]), Docs(client, ecole["id"], ecole["admin"])
    ident = creer(prof, "question", _saison(prof)["id"]).json()["id"]
    enregistrer(prof, ident, SONDAGE)
    assert admin.modifier(ident, change_status=True, status="validated").status_code == 200
    f = prof.get(f"/nodes/{ident}/app").json()
    assert f["status"] == "validated" and f["editable"] is False
    assert enregistrer(prof, ident, SONDAGE).status_code == 409
    assert admin.modifier(ident, change_status=True, status="draft").status_code == 200
    assert enregistrer(admin, ident, SONDAGE).status_code == 200


def test_essayer_et_reponses(client, ecole):
    prof, eleve = Docs(client, ecole["id"], ecole["prof"]), Docs(client, ecole["id"], ecole["eleve"])
    ident = creer(prof, "question", _saison(prof)["id"]).json()["id"]
    enregistrer(prof, ident, SONDAGE)
    essai = lambda d, v: d.c.post(f"{d.base}/nodes/{ident}/app/try", json={"values": v}, headers=d.h)
    assert essai(prof, {}).status_code == 422  # question obligatoire
    assert essai(prof, {"q1": "14 juillet"}).status_code == 422  # choix inexistant
    assert essai(prof, {"q1": "20 juin", "zz": 1}).status_code == 422  # question inconnue
    assert essai(prof, {"q1": "20 juin", "q2": " Super "}).status_code == 201
    # Un élève sans droit sur le fichier ne le voit même pas.
    assert essai(eleve, {"q1": "20 juin"}).status_code == 404

    reponses = prof.get(f"/nodes/{ident}/app/responses").json()["items"]
    assert len(reponses) == 1
    assert reponses[0]["is_test"] is True and reponses[0]["values"] == {"q1": "20 juin", "q2": "Super"}
    assert reponses[0]["who"] == "Ima Blanc"
    assert prof.get(f"/nodes/{ident}/app").json()["response_count"] == 1
    # Des réponses existent : le prochain enregistrement fait une nouvelle version.
    numero = prof.get(f"/nodes/{ident}/app").json()["version"]["number"]
    assert enregistrer(prof, ident, SONDAGE).json()["version"]["number"] == numero + 1

    efface = prof.c.delete(f"{prof.base}/nodes/{ident}/app/responses/tests", headers=prof.h)
    assert efface.json() == {"erased": 1}


def test_copier_et_effacer(client, ecole):
    prof = Docs(client, ecole["id"], ecole["prof"])
    saison = _saison(prof)["id"]
    ident = creer(prof, "question", saison, nom="Sondage").json()["id"]
    enregistrer(prof, ident, SONDAGE)
    prof.c.post(f"{prof.base}/nodes/{ident}/app/try", json={"values": {"q1": "21 juin"}}, headers=prof.h)
    copie = prof.c.post(f"{prof.base}/nodes/{ident}/copy", json={"space": "private", "parent_id": saison}, headers=prof.h)
    cid = copie.json()["id"]
    f = prof.get(f"/nodes/{cid}/app").json()
    assert f["content"]["entry"]["blocks"][1]["id"] == "q1" and f["response_count"] == 0
    assert prof.supprimer(ident).status_code == 204
    assert prof.c.delete(prof.base + "/spaces/private/trash", headers=prof.h).json()["erased"] == 1


def test_valeurs_des_questions():
    contenu = {
        "schema": 1,
        "entry": {
            "blocks": [
                bloc("m", "member", label="Vos coordonnées", required=True),
                bloc("d", "date", label="Naissance"),
                bloc("n", "number", label="Âge"),
                bloc("o", "yesNo", label="Photo ?"),
                bloc("c", "choice", label="Cours", options="Éveil\nJazz", multiple=True),
                bloc("p", "payment", label="Cotisation", amount=12),
            ]
        },
        "result": {"blocks": []},
    }
    app_content.check_content(contenu, "act")
    ok = app_content.check_values(
        contenu,
        {"m": {"last_name": "Martin", "email": "c@exemple.fr"}, "d": "2017-03-02", "n": 9, "o": True, "c": ["Jazz"], "p": True},
        test=True,
    )
    assert ok["c"] == ["Jazz"] and ok["p"] == {"amount": 12, "test": True}
    with pytest.raises(ContentError):
        app_content.check_values(contenu, {"m": {"last_name": "Martin", "email": "pas-un-email"}}, test=True)
    with pytest.raises(ContentError):
        app_content.check_values(contenu, {"m": {"last_name": "M", "email": "c@e.fr"}, "d": "hier"}, test=True)
    with pytest.raises(ContentError):
        app_content.check_values(contenu, {"m": {"last_name": "M", "email": "c@e.fr"}, "p": True}, test=False)
    # Changer de nature retire les blocs qui n'y existent pas.
    assert [b["id"] for b in app_content.drop_for_family(contenu, "question")["entry"]["blocks"]] == ["d", "n", "o", "c"]


def test_faire_un_modele_puis_l_utiliser(client, ecole):
    """« Faire un modèle » (fichier-de-base.md §5) : admins seulement, le
    contenu est recopié sans les réponses ; la tuile crée une copie en
    Brouillon ; renommer, cacher, supprimer."""
    admin = Docs(client, ecole["id"], ecole["admin"])
    prof = Docs(client, ecole["id"], ecole["prof"])
    saison = _saison(admin)["id"]
    ident = creer(admin, "question", saison).json()["id"]
    modele = lambda docs, nom: docs.c.post(f"{docs.base}/nodes/{ident}/app/template", json={"name": nom}, headers=docs.h)
    assert modele(admin, "Organiser la fête").status_code == 409  # fichier vide
    enregistrer(admin, ident, SONDAGE)
    admin.c.post(f"{admin.base}/nodes/{ident}/app/try", json={"values": {"q1": "20 juin"}}, headers=admin.h)

    m = modele(admin, "Organiser la fête")
    assert m.status_code == 201 and m.json()["family"] == "question" and m.json()["question_count"] == 2
    deux = modele(admin, "organiser la fête").json()
    assert deux["name"] == "organiser la fête (2)"
    # Un prof (pas admin) ne fait pas de modèle, mais voit les tuiles.
    assert modele(prof, "X").status_code == 403
    liste = prof.get("/app-templates").json()
    assert len(liste["items"]) == 2 and liste["can_manage"] is False

    copie = prof.c.post(f"{prof.base}/app-templates/{m.json()['id']}/use", json={"space": "private", "parent_id": saison}, headers=prof.h)
    assert copie.status_code == 201
    lue = prof.get(f"/nodes/{copie.json()['id']}/app").json()
    assert lue["name"] == "Organiser la fête" and lue["status"] == "draft" and lue["family"] == "question"
    assert lue["content"]["entry"]["blocks"][1]["id"] == "q1" and lue["response_count"] == 0

    # Cacher : disparaît pour les autres, reste listé (caché) aux admins.
    admin.c.patch(f"{admin.base}/app-templates/{deux['id']}", json={"hidden": True, "name": "Fête 2"}, headers=admin.h)
    assert len(prof.get("/app-templates").json()["items"]) == 1
    assert [t["name"] for t in admin.get("/app-templates").json()["items"] if t["hidden"]] == ["Fête 2"]
    assert prof.c.delete(f"{prof.base}/app-templates/{deux['id']}", headers=prof.h).status_code == 403
    assert admin.c.delete(f"{admin.base}/app-templates/{deux['id']}", headers=admin.h).status_code == 204
    assert len(admin.get("/app-templates").json()["items"]) == 1


def test_mettre_en_ligne_et_repondre_sans_compte(client, ecole):
    """Page en ligne (documents.md §5.5) : en Officiel seulement, nom créé
    depuis le nom du fichier et jamais en double ; on y répond sans compte,
    la réponse arrive dans Résultats (provenance « public »)."""
    admin = Docs(client, ecole["id"], ecole["admin"])
    saison = _saison(admin)["id"]
    ident = creer(admin, "question", saison, "Fête de l'école").json()["id"]
    enregistrer(admin, ident, SONDAGE)
    publier = lambda i: admin.c.post(f"{admin.base}/nodes/{i}/app/publication", headers=admin.h)
    assert publier(ident).status_code == 409  # Brouillon
    admin.modifier(ident, change_status=True, status="validated")
    assert publier(ident).status_code == 409  # Validé : relecteurs seulement
    admin.modifier(ident, change_status=True, status="official")
    p = publier(ident)
    assert p.status_code == 200 and p.json()["slug"] == "fete-de-l-ecole" and p.json()["online"] is True
    assert admin.get(f"/nodes/{ident}/app").json()["publication"]["slug"] == "fete-de-l-ecole"

    # Un second fichier du même nom : un autre nom de page.
    autre = creer(admin, "question", saison, "Fête de l'école").json()["id"]
    enregistrer(admin, autre, SONDAGE)
    admin.modifier(autre, change_status=True, status="official")
    assert publier(autre).json()["slug"] == "fete-de-l-ecole-2"

    page = f"/documents/public/orgs/{ecole['id']}/pages/fete-de-l-ecole"
    lue = client.get(page)
    assert lue.status_code == 200 and lue.json()["accepting"] is True
    assert [b["id"] for b in lue.json()["content"]["entry"]["blocks"]] == ["h1", "q1", "q2"]
    assert "result" not in lue.json()["content"]
    assert client.post(page + "/answers", json={"values": {}}).status_code == 422  # q1 obligatoire
    assert client.post(page + "/answers", json={"values": {"q1": "21 juin"}}).status_code == 201
    rep = admin.get(f"/nodes/{ident}/app/responses").json()["items"]
    assert len(rep) == 1 and rep[0]["source"] == "public" and rep[0]["is_test"] is False

    # Retirer : la page n'est plus là, le nom reste réservé.
    admin.c.delete(f"{admin.base}/nodes/{ident}/app/publication", headers=admin.h)
    assert client.get(page).status_code == 404
    assert publier(ident).json()["slug"] == "fete-de-l-ecole"
    # Le prof ne met pas en ligne (niveau gérer).
    prof = Docs(client, ecole["id"], ecole["prof"])
    assert prof.c.post(f"{prof.base}/nodes/{autre}/app/publication", headers=prof.h).status_code == 403


class FauxMails:
    available = True

    def __init__(self):
        self.envoyes = []

    def org(self, db, org_id):
        return "Contretemps", "https://contretemps-83330.contretemps.silvaplana.cloud"

    def send(self, to, subject, text, html, sender_name, reply_to):
        if to == "panne@exemple.fr":
            raise RuntimeError("Boîte pleine")
        self.envoyes.append({"to": to, "subject": subject, "text": text, "html": html, "from": sender_name, "reply_to": reply_to})


@pytest.fixture
def mails(monkeypatch):
    from app.main import documents_client

    faux = FauxMails()
    monkeypatch.setattr(documents_client, "mailer", faux)
    return faux


def test_diffuser_aux_personnes_choisies(client, ecole, db_session, mails):
    """Diffuser (fichier-de-base.md §2.3) : en Validé, aux relecteurs
    seulement et réponses d'essai ; en Officiel, aux groupes, réponses
    comptées ; un lien personnel par personne, une réponse par lien."""
    ecole["admin"].email = "julia@exemple.fr"
    ecole["eleve"].email = "leon@exemple.fr"
    ecole["prof"].email = "panne@exemple.fr"
    db_session.commit()
    admin = Docs(client, ecole["id"], ecole["admin"])
    saison = _saison(admin)["id"]
    ident = creer(admin, "question", saison, "Fête de l'école").json()["id"]
    enregistrer(admin, ident, SONDAGE)
    url = f"{admin.base}/nodes/{ident}/app/sends"
    envoyer = lambda cibles, **autres: admin.c.post(url, json={"principals": cibles, **autres}, headers=admin.h)
    personne = lambda c: {"type": "member", "id": str(c.id)}
    cours = {"type": "group", "id": f"course:{ecole['cours'].id}"}

    assert envoyer([personne(ecole["admin"])]).status_code == 409  # Brouillon
    admin.modifier(ident, change_status=True, status="validated")
    assert envoyer([cours]).status_code == 409  # Validé : un par un
    apercu = admin.c.post(url + "/preview", json={"principals": [personne(ecole["admin"]), personne(ecole["autre"])]}, headers=admin.h).json()
    assert apercu == {"test": True, "available": True, "count": 1, "without_email": ["Ana Roux"]}
    r = envoyer([personne(ecole["admin"])], message="Tu relis ?")
    assert r.status_code == 201 and r.json() == {"sent": 1, "test": True}
    mail = mails.envoyes[-1]
    assert mail["to"] == "julia@exemple.fr" and mail["subject"] == "[Relecture] Fête de l'école"
    assert mail["from"] == "Contretemps" and mail["reply_to"] == "julia@exemple.fr"
    assert "Tu relis ?" in mail["text"] and "Fête de fin d'année" in mail["text"] and "Quelle date" not in mail["text"]
    lien = mail["text"].split("https://contretemps-83330.contretemps.silvaplana.cloud/r/")[1].split()[0]
    assert "<a " not in mail["html"]

    page = client.get(f"/documents/public/links/{lien}")
    assert page.status_code == 200 and page.json()["accepting"] is True and page.json()["test"] is True
    assert page.json()["person"] == "Julia Dho" and page.json()["values"] is None
    assert client.post(f"/documents/public/links/{lien}/answers", json={"values": {"q1": "20 juin"}}).status_code == 201
    assert client.post(f"/documents/public/links/{lien}/answers", json={"values": {"q1": "21 juin"}}).status_code == 201
    rep = admin.get(f"/nodes/{ident}/app/responses").json()["items"]
    assert len(rep) == 1 and rep[0]["is_test"] is True and rep[0]["source"] == "link" and rep[0]["values"]["q1"] == "21 juin"
    assert client.get(f"/documents/public/links/{lien}").json()["values"]["q1"] == "21 juin"

    # Officiel : au cours (Léon) et au prof (son adresse est en panne).
    admin.modifier(ident, change_status=True, status="official")
    assert client.post(f"/documents/public/links/{lien}/answers", json={"values": {"q1": "20 juin"}}).status_code == 409
    r = envoyer([cours, personne(ecole["prof"]), personne(ecole["autre"])])
    assert r.json() == {"sent": 2, "test": False}
    suivi = {s["name"]: s for s in admin.get(f"/nodes/{ident}/app/sends").json()["items"]}
    assert suivi["Léon Perrin"]["status"] == "sent" and suivi["Léon Perrin"]["test"] is False
    assert suivi["Ima Blanc"]["status"] == "failed" and suivi["Ima Blanc"]["error"] == "Boîte pleine"
    assert suivi["Julia Dho"]["answered_at"] and suivi["Julia Dho"]["test"] is True
    lien_leon = next(m for m in mails.envoyes if m["to"] == "leon@exemple.fr")["text"].split("/r/")[1].split()[0]
    assert client.post(f"/documents/public/links/{lien_leon}/answers", json={"values": {"q1": "20 juin"}}).status_code == 201
    rep = admin.get(f"/nodes/{ident}/app/responses").json()["items"]
    assert [(r["who"], r["is_test"]) for r in rep] == [("Julia Dho", True), ("Léon Perrin", False)]
    # Renvoyer : le même lien.
    envoyer([cours])
    assert mails.envoyes[-1]["text"].split("/r/")[1].split()[0] == lien_leon
    # Le prof ne diffuse pas (niveau gérer) ; un lien inconnu ne mène à rien.
    prof = Docs(client, ecole["id"], ecole["prof"])
    assert prof.c.post(f"{prof.base}/nodes/{ident}/app/sends", json={"principals": [cours]}, headers=prof.h).status_code == 403
    assert client.get("/documents/public/links/inconnu").status_code == 404


def test_slugify():
    from documents.app_files import slugify

    assert slugify("Convocation AG 2026") == "convocation-ag-2026"
    assert slugify("  Été à l'école !! ") == "ete-a-l-ecole"
    assert len(slugify("x" * 80)) == 40
    assert slugify("A") == "a-page"
