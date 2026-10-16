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
    essai = lambda d, v: d.c.post(f"{d.base}/nodes/{ident}/app/try", json={"values": v}, headers=d.h)  # noqa: E731
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
