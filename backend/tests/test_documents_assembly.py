"""Convocation d'assemblée générale et procurations (procurations.md) :
dossier automatique, envoi, règles d'une procuration, pouvoirs signés en
PDF, décompte et récapitulatif."""

import time

import pytest
from test_documents import (  # noqa: F401 (fixtures)
    Docs,
    _par_nom,
    _saison,
    ecole,
    stockage,
)
from test_documents_app import mails  # noqa: F401 (fixture)

pytestmark = pytest.mark.rbac_reel

PNG = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
QUAND = "2099-11-21T14:00"


def convoquer(docs, **corps):
    return docs.c.post(docs.base + "/assemblies", json={"kind": "ordinary", "starts_at": QUAND, **corps}, headers=docs.h)


def lien(mails, adresse):
    return next(m for m in reversed(mails.envoyes) if m["to"] == adresse)["text"].split("/r/")[1].split("?")[0].split()[0]


def repondre(client, jeton, **valeur):
    page = client.get(f"/documents/public/links/{jeton}").json()
    return client.post(f"/documents/public/links/{jeton}/answers", json={"values": {page["assembly"]["block_id"]: valeur}})


def procuration(client, jeton, qui):
    return repondre(client, jeton, answer="proxy", proxy_to=qui, signature=PNG)


@pytest.fixture
def ag(client, ecole, db_session, mails):
    """Une AGO convoquée et envoyée aux quatre membres de l'école."""
    for compte, adresse in (("admin", "julia"), ("prof", "ima"), ("eleve", "leon"), ("autre", "ana")):
        ecole[compte].definir_emails(f"{adresse}@exemple.fr")
    db_session.commit()
    admin = Docs(client, ecole["id"], ecole["admin"])
    r = convoquer(admin)
    assert r.status_code == 201, r.text
    ident = r.json()["id"]
    assert admin.modifier(ident, change_status=True, status="official").status_code == 200
    vue = admin.get(f"/nodes/{ident}/app/assembly").json()
    assert len(vue["recipients"]) == 4
    envoi = admin.c.post(f"{admin.base}/nodes/{ident}/app/sends", json={"principals": vue["principals"]}, headers=admin.h)
    assert envoi.json()["sent"] == 4
    return {"admin": admin, "id": ident, "folder": r.json()["folder_id"]}


def test_convoquer_range_dans_reunions(client, ecole):
    admin = Docs(client, ecole["id"], ecole["admin"])
    saison = _saison(admin)["id"]
    r = convoquer(admin)
    assert r.status_code == 201
    assert r.json()["name"] == "Convocation AGO du 21 novembre 2099"
    reunions = _par_nom(admin.racine(dossier=saison))["Réunions"]
    assert "AGO du 21 novembre 2099" in _par_nom(admin.racine(dossier=reunions["id"]))
    f = admin.get(f"/nodes/{r.json()['id']}/app").json()
    textes = [b["content"][0]["text"] for b in f["content"]["entry"]["blocks"] if b["content"]]
    assert "Rapport financier et approbation des comptes" in textes
    assert any("samedi 21 novembre 2099 à 14 h" in t for t in textes)
    # Deux dossiers d'AG possibles : l'appli demande, sans rien créer.
    admin.dossier("Assemblée générale", reunions["id"])
    r = convoquer(admin, starts_at="2099-12-05T18:30")
    assert r.status_code == 201 and {d["name"] for d in r.json()["folders"]} == {"AGO du 21 novembre 2099", "Assemblée générale"}
    choisi = r.json()["folders"][1]["id"]
    assert convoquer(admin, starts_at="2099-12-05T18:30", folder_id=choisi).json()["folder_id"] == choisi
    # L'extraordinaire a son ordre du jour à elle.
    e = convoquer(admin, kind="extraordinary", new_folder=True).json()
    textes = [b["content"][0]["text"] for b in admin.get(f"/nodes/{e['id']}/app").json()["content"]["entry"]["blocks"] if b["content"]]
    assert "Modification des statuts" in textes
    assert convoquer(admin, starts_at="2001-01-01T10:00").status_code == 422
    assert convoquer(admin, kind="autre").status_code == 422


def test_regles_des_procurations(client, ecole, ag, mails):
    julia, ima, leon, ana = (lien(mails, f"{x}@exemple.fr") for x in ("julia", "ima", "leon", "ana"))
    page = client.get(f"/documents/public/links/{leon}").json()
    gens = {g["name"]: g["id"] for g in page["assembly"]["candidates"]}
    assert set(gens) == {"Julia Dho", "Ima Blanc", "Ana Roux"}  # pas soi-même
    # Le mail porte les trois réponses.
    mail = next(m for m in mails.envoyes if m["to"] == "leon@exemple.fr")
    assert "Je donne procuration :" in mail["text"] and "?c=proxy" in mail["text"]

    assert procuration(client, leon, gens["Ana Roux"]).status_code == 201
    # Ana n'a pas répondu : le pouvoir est en attente, ni compté ni perdu.
    s = ag["admin"].get(f"/nodes/{ag['id']}/app/assembly").json()["summary"]
    assert (s["votes"], s["lost"], s["holders"][0]["pending"]) == (0, 0, True)
    a_ana = {g["name"]: g["id"] for g in client.get(f"/documents/public/links/{ana}").json()["assembly"]["candidates"]}
    # Ana a reçu un pouvoir : elle ne peut pas en donner.
    r = procuration(client, ana, a_ana["Ima Blanc"])
    assert r.status_code == 422 and "venez" in r.json()["detail"]
    # Léon a déjà donné le sien : pas de chaîne.
    r = procuration(client, ima, a_ana["Léon Perrin"])
    assert r.status_code == 422 and "lui-même donné" in r.json()["detail"]
    assert procuration(client, ima, gens["Ana Roux"]).status_code == 201
    # Ana a ses 2 pouvoirs.
    r = procuration(client, julia, gens["Ana Roux"])
    assert r.status_code == 422 and "déjà 2 pouvoirs" in r.json()["detail"]
    complet = {g["name"]: g for g in client.get(f"/documents/public/links/{julia}").json()["assembly"]["candidates"]}
    assert complet["Ana Roux"]["full"] is True
    assert procuration(client, julia, ecole["admin"].id).status_code == 422  # soi-même
    assert procuration(client, julia, 999999).status_code == 422  # pas convoqué
    assert repondre(client, julia, answer="proxy", proxy_to="blank").status_code == 422  # sans signature
    # Un pouvoir en blanc ne compte pas dans le plafond.
    assert procuration(client, julia, "blank").status_code == 201
    assert repondre(client, ana, answer="attend").status_code == 201

    s = ag["admin"].get(f"/nodes/{ag['id']}/app/assembly").json()["summary"]
    assert (s["convoked"], s["attend"], s["proxy"], s["absent"], s["none"], s["votes"]) == (4, 1, 3, 0, 0, 4)
    porteurs = {h["name"]: h for h in s["holders"]}
    assert porteurs["Ana Roux"]["count"] == 2 and porteurs["Ana Roux"]["from"] == ["Ima Blanc", "Léon Perrin"]
    assert any(h["person_id"] is None and h["count"] == 1 for h in s["holders"])
    # Ana ne vient plus : les pouvoirs qu'elle porte sont perdus.
    assert repondre(client, ana, answer="absent").status_code == 201
    s = ag["admin"].get(f"/nodes/{ag['id']}/app/assembly").json()["summary"]
    assert s["lost"] == 2 and s["votes"] == 1


def test_pouvoirs_en_pdf_dans_le_dossier(client, ecole, ag, mails):
    admin = ag["admin"]
    leon = lien(mails, "leon@exemple.fr")
    ana = next(g["id"] for g in client.get(f"/documents/public/links/{leon}").json()["assembly"]["candidates"] if g["name"] == "Ana Roux")
    assert procuration(client, leon, ana).status_code == 201
    pouvoirs = _par_nom(admin.racine(dossier=ag["folder"]))["Pouvoirs"]
    fichiers = _par_nom(admin.racine(dossier=pouvoirs["id"]))
    assert list(fichiers) == ["Pouvoir de Léon Perrin à Ana Roux.pdf"]
    # Il change d'avis : le pouvoir reste, marqué retiré.
    assert repondre(client, leon, answer="attend").status_code == 201
    noms = list(_par_nom(admin.racine(dossier=pouvoirs["id"])))
    assert len(noms) == 1 and "(retiré le" in noms[0]
    # Récapitulatif PDF et Excel, convocation imprimable.
    for quoi, debut in (("summary.pdf", b"%PDF"), ("convocation.pdf", b"%PDF"), ("summary.xlsx", b"PK")):
        r = admin.get(f"/nodes/{ag['id']}/app/assembly/{quoi}")
        assert r.status_code == 200 and r.content.startswith(debut), quoi


def test_essai_avec_un_membre_et_pas_de_page_publique(client, ecole, mails, db_session):
    ecole["admin"].definir_emails("julia@exemple.fr")
    ecole["eleve"].definir_emails("leon@exemple.fr")
    db_session.commit()
    admin = Docs(client, ecole["id"], ecole["admin"])
    ident = convoquer(admin).json()["id"]
    admin.modifier(ident, change_status=True, status="official")
    r = admin.c.post(f"{admin.base}/nodes/{ident}/app/sends/trial", json={"person_id": ecole["eleve"].id}, headers=admin.h)
    assert r.status_code == 201 and r.json()["email"] == "leon@exemple.fr"
    mail = mails.envoyes[-1]
    assert mail["subject"].startswith("[Essai] ") and "Julia Dho vous envoie" in mail["text"]
    # La réponse d'essai ne compte pas, et ne range aucun pouvoir.
    jeton = lien(mails, "leon@exemple.fr")
    julia = next(g["id"] for g in client.get(f"/documents/public/links/{jeton}").json()["assembly"]["candidates"] if g["name"] == "Julia Dho")
    assert procuration(client, jeton, julia).status_code == 201
    s = admin.get(f"/nodes/{ident}/app/assembly").json()["summary"]
    assert s["proxy"] == 0 and s["tests"][0]["answer"] == "proxy"
    # Une convocation ne se met pas en ligne : chacun signe pour lui-même.
    assert admin.c.post(f"{admin.base}/nodes/{ident}/app/publication", headers=admin.h).status_code == 409


def test_ecoles_etanches(client, ecole, ag):
    voisin = Docs(client, ecole["id"], ecole["admin_voisin"])
    assert voisin.get(f"/nodes/{ag['id']}/app/assembly").status_code == 403
    assert voisin.get(f"/nodes/{ag['id']}/app/assembly/summary.pdf").status_code == 403
    assert convoquer(voisin).status_code == 403


def test_par_l_assistant(client, ecole, db_session, mails):
    """L'assistant fait comme l'écran (procurations.md §1.4) : convoquer,
    valider, envoyer, chaque fois sur une carte Faire / Annuler."""
    from app import main

    actions = main.assistant_client.actions
    admin = ecole["admin"]
    ecole["eleve"].definir_emails("leon@exemple.fr")
    db_session.commit()
    proposer = lambda nom, args: actions.propose(db_session, admin, ecole["id"], admin.id, nom, args)  # noqa: E731
    faire = lambda carte: actions.execute(db_session, ecole["id"], admin.id, carte["jeton"])  # noqa: E731

    _, carte = proposer("convene_assembly", {"kind": "ordinary", "date": "2099-11-21", "time": "14:00"})
    assert carte["lignes"] == [
        "Préparer la convocation de l'AGO du 21 novembre 2099 à 14 h, rangée dans Réunions › AGO du 21 novembre 2099 "
        "(nouveau dossier) (brouillon « Convocation AGO du 21 novembre 2099 », à relire avant de valider)"
    ]
    fait = faire(carte)[0]
    nom = "Convocation AGO du 21 novembre 2099"
    # Le brouillon s'ouvre au-dessus de l'assistant pour être relu (Seb, 21 octobre).
    ouvrir = fait["ouvrir"]
    assert fait["ok"] and ouvrir["name"] == nom and ouvrir["kind"] == "app" and ouvrir["family"] == "question"
    assert ouvrir["space"] == "private" and ouvrir["parent_id"] and ouvrir["id"]
    texte, carte = proposer("send_app_file", {"file": nom})
    assert carte is None and "pas encore validé" in texte
    _, carte = proposer("validate_app_file", {"file": nom})
    assert faire(carte)[0]["ok"]
    _, carte = proposer("send_app_file", {"file": nom})
    assert carte["lignes"][0].startswith(f"Envoyer « {nom} » par email à 1 membre (Léon Perrin) ; sans adresse email : ")
    texte, carte = proposer("convene_assembly", {"kind": "ordinary", "date": "2001-01-01", "time": "10:00"})
    assert carte is None and "passée" in texte


def test_feuille_d_emargement(client, ecole, ag, mails, db_session):
    """Le jour de l'AG (procurations.md §3.5, §4) : un pouvoir compte si son
    mandataire est pointé présent, il est perdu sinon, et un mandant présent
    reprend sa voix."""
    from comptes import Comptes

    admin, ident = ag["admin"], ag["id"]
    url = f"{admin.base}/nodes/{ident}/app/attendance"
    pointer = lambda pid, oui=True: admin.c.put(f"{url}/{pid}", json={"present": oui}, headers=admin.h)  # noqa: E731
    leon, ima = lien(mails, "leon@exemple.fr"), lien(mails, "ima@exemple.fr")
    ana = next(g["id"] for g in client.get(f"/documents/public/links/{leon}").json()["assembly"]["candidates"] if g["name"] == "Ana Roux")
    assert procuration(client, leon, ana).status_code == 201
    assert procuration(client, ima, "blank").status_code == 201

    s = admin.get(f"/nodes/{ident}/app/attendance").json()
    assert (s["present"], s["represented"], s["lost"], s["votes"]) == (0, 1, 1, 1)  # seul le blanc compte
    s = pointer(ana).json()
    assert (s["present"], s["represented"], s["absent"], s["votes"]) == (1, 2, 1, 3)
    lignes = {r["name"]: r for r in s["rows"]}
    assert lignes["Léon Perrin"]["represented_by"] == "Ana Roux" and lignes["Ana Roux"]["holds"] == 1
    assert lignes["Ima Blanc"]["represented_by"] == "le bureau"
    # Léon vient finalement : sa présence l'emporte sur son pouvoir.
    s = pointer(ecole["eleve"].id).json()
    assert (s["present"], s["represented"], s["votes"]) == (2, 1, 3)
    # Ana repart : Léon reste présent, rien n'est perdu ; Léon repart : son pouvoir est perdu.
    pointer(ana, False)
    s = pointer(ecole["eleve"].id, False).json()
    assert (s["present"], s["lost"], s["votes"]) == (0, 1, 1)
    lignes = {r["name"]: r for r in s["rows"]}
    assert lignes["Ana Roux"]["lost"] == ["Léon Perrin"] and lignes["Léon Perrin"]["proxy_name"] == "Ana Roux"

    # Une personne de l'école non convoquée peut être ajoutée ; pas d'ailleurs.
    nouvelle = Comptes().create(db_session, ecole_id=ecole["id"], role="eleve", nom="Neuf", prenom="Zoé")
    db_session.commit()
    s = pointer(nouvelle.id).json()
    assert {r["name"]: r for r in s["rows"]}["Zoé Neuf"]["convoked"] is False and s["present"] == 1
    assert pointer(ecole["admin_voisin"].id).status_code == 404
    assert pointer(999999).status_code == 404

    # Le PDF se range à côté de la convocation ; refait, il devient une nouvelle version.
    r = admin.c.post(f"{url}/pdf", headers=admin.h)
    assert r.status_code == 201 and r.json()["name"] == "Feuille d'émargement AGO du 21 novembre 2099.pdf"
    assert admin.c.post(f"{url}/pdf", headers=admin.h).json()["id"] == r.json()["id"]
    assert "Feuille d'émargement AGO du 21 novembre 2099.pdf" in _par_nom(admin.racine(dossier=ag["folder"]))

    voisin = Docs(client, ecole["id"], ecole["admin_voisin"])
    assert voisin.get(f"/nodes/{ident}/app/attendance").status_code == 403


def test_emargement_seulement_en_officiel(client, ecole):
    admin = Docs(client, ecole["id"], ecole["admin"])
    ident = convoquer(admin).json()["id"]
    r = admin.c.put(f"{admin.base}/nodes/{ident}/app/attendance/{ecole['eleve'].id}", json={"present": True}, headers=admin.h)
    assert r.status_code == 409


def test_copies_du_pouvoir(client, ecole, ag, mails):
    """Étape 3 : le mandataire est prévenu, le mandant reçoit la copie de son
    pouvoir signé ; tous deux avec le PDF joint."""
    leon, julia = lien(mails, "leon@exemple.fr"), lien(mails, "julia@exemple.fr")
    ana = next(g["id"] for g in client.get(f"/documents/public/links/{leon}").json()["assembly"]["candidates"] if g["name"] == "Ana Roux")
    avant = len(mails.envoyes)
    assert procuration(client, leon, ana).status_code == 201
    nouveaux = {m["to"]: m for m in mails.envoyes[avant:]}
    assert set(nouveaux) == {"ana@exemple.fr", "leon@exemple.fr"}
    a_ana, a_leon = nouveaux["ana@exemple.fr"], nouveaux["leon@exemple.fr"]
    assert a_ana["subject"] == "Léon Perrin vous a donné procuration pour l'assemblée générale du 21 novembre 2099"
    assert "Bonjour Ana Roux," in a_ana["text"] and "son pouvoir sera perdu" in a_ana["text"]
    assert a_leon["subject"] == "Votre procuration pour l'assemblée générale du 21 novembre 2099"
    assert "Ana Roux vous représentera" in a_leon["text"] and f"/r/{leon}" in a_leon["text"]
    for m in (a_ana, a_leon):
        assert [n for n, _ in m["attachments"]] == ["Pouvoir.pdf"] and m["attachments"][0][1].startswith(b"%PDF")
    # Même réponse renvoyée : pas de nouveau mail.
    avant = len(mails.envoyes)
    assert procuration(client, leon, ana).status_code == 201
    assert len(mails.envoyes) == avant
    # En blanc : seulement la copie au mandant.
    assert procuration(client, julia, "blank").status_code == 201
    nouveaux = mails.envoyes[avant:]
    assert [m["to"] for m in nouveaux] == ["julia@exemple.fr"]
    assert "le bureau désignera la personne qui vous représente" in nouveaux[0]["text"]


def test_relance_sept_jours_avant(client, ecole, ag, mails, db_session):
    """Étape 3 : sept jours avant l'assemblée, une relance part une fois aux
    convoqués qui n'ont pas répondu, avec leur lien."""
    from datetime import datetime

    from app.main import documents_client
    from documents import assembly

    leon = lien(mails, "leon@exemple.fr")
    assert repondre(client, leon, answer="attend").status_code == 201
    relancer = lambda quand: assembly.remind_due(db_session, mails, documents_client.directory, now=quand)
    avant = len(mails.envoyes)
    assert relancer(datetime(2099, 11, 13, 14, 0)) == 0  # J-8 : trop tôt
    assert relancer(datetime(2099, 11, 14, 15, 0)) == 3
    relances = mails.envoyes[avant:]
    assert {m["to"] for m in relances} == {"julia@exemple.fr", "ima@exemple.fr", "ana@exemple.fr"}
    ima = next(m for m in relances if m["to"] == "ima@exemple.fr")
    assert ima["subject"].startswith("Rappel : ") and f"/r/{lien(mails, 'ima@exemple.fr')}?c=proxy" in ima["text"]
    assert "dans une semaine" in ima["text"]
    assert relancer(datetime(2099, 11, 15, 9, 0)) == 0  # une seule fois
    from documents.models import DocActivity

    trace = db_session.query(DocActivity).filter_by(node_id=ag["id"], action="reminded").one()
    assert trace.detail == {"count": 3}


# --- Procès-verbal, étape 1 : la liste des présents en photo (proces-verbal-ag.md §1) ---


class LecteurFactice:
    """Remplace la lecture par Claude : rend les lignes données, en gardant
    ce qu'on lui a demandé."""

    actif = True

    def __init__(self, lignes):
        self.lignes = lignes
        self.appels = []

    def read(self, db, org_id, pages, people):
        from documents.attendance_photo import ReadLine

        self.appels.append((org_id, [t for _, t in pages], dict(people)))
        return [ReadLine(**l) for l in self.lignes(people)]


def _id(people, nom):
    return next(pid for pid, n in people.items() if n == nom)


def test_photo_de_la_liste_des_presents(client, ecole, ag, mails, db_session, monkeypatch):
    from app import main

    admin, ident = ag["admin"], ag["id"]
    leon = lien(mails, "leon@exemple.fr")
    candidats = client.get(f"/documents/public/links/{leon}").json()["assembly"]["candidates"]
    ana = next(g["id"] for g in candidats if g["name"] == "Ana Roux")
    assert procuration(client, leon, ana).status_code == 201

    lecteur = LecteurFactice(lambda people: [
        {"written": "Ana Roux", "person_id": _id(people, "Ana Roux"), "candidates": [], "doubt": None},
        {"written": "J. Dho", "person_id": None, "candidates": [_id(people, "Julia Dho"), 999999], "doubt": "Initiale seulement"},
        {"written": "Marcel Inconnu", "person_id": None, "candidates": [], "doubt": None},
        {"written": "Ana R.", "person_id": _id(people, "Ana Roux"), "candidates": [], "doubt": None},  # doublon
        {"written": "Pirate", "person_id": 424242, "candidates": [], "doubt": None},  # hors de la liste
    ])
    monkeypatch.setattr(main.documents_client, "attendance_reader", lecteur)
    url = f"{admin.base}/nodes/{ident}/app/attendance"
    photo = ("files", ("liste.jpg", b"\xff\xd8\xff photo", "image/jpeg"))
    r = admin.c.post(f"{url}/photo", files=[photo, ("files", ("page2.png", b"\x89PNG", "image/png"))], headers=admin.h)
    assert r.status_code == 200, r.text
    lu = r.json()
    assert lecteur.appels[0][1] == ["image/jpeg", "image/png"]
    assert set(lecteur.appels[0][2].values()) == {"Julia Dho", "Ima Blanc", "Léon Perrin", "Ana Roux"}
    assert [(p["name"], p["written"]) for p in lu["sure"]] == [("Ana Roux", "Ana Roux")]
    assert lu["doubts"] == [{"written": "J. Dho", "reason": "Initiale seulement",
                             "candidates": [{"person_id": ecole["admin"].id, "name": "Julia Dho"}]}]
    assert [u["written"] for u in lu["unknown"]] == ["Marcel Inconnu", "Pirate"]
    # Les photos sont rangées dans le dossier de l'AG ; rien n'est encore pointé.
    noms = set(_par_nom(admin.racine(dossier=ag["folder"])))
    assert {"Liste des présents.jpg", "Liste des présents (page 2).png"} <= noms
    assert lu["photos"] == ["Liste des présents.jpg", "Liste des présents (page 2).png"]
    assert admin.get(f"/nodes/{ident}/app/attendance").json()["present"] == 0

    # « Continuer » : on pointe les présents retenus, d'un coup.
    r = admin.c.post(f"{url}/batch", json={"person_ids": [ana, ecole["admin"].id]}, headers=admin.h)
    s = r.json()
    assert (s["present"], s["represented"], s["votes"]) == (2, 1, 3)
    assert {r["source"] for r in s["rows"] if r["present"]} == {"photo"}
    # Une autre école ne lit pas cette AG.
    voisin = Docs(client, ecole["id"], ecole["admin_voisin"])
    assert voisin.c.post(f"{url}/photo", files=[photo], headers=voisin.h).status_code in (403, 404)


def test_photo_sans_lecture_configuree(client, ecole, ag, monkeypatch):
    from app import main

    class Eteint:
        actif = False

    monkeypatch.setattr(main.documents_client, "attendance_reader", Eteint())
    admin = ag["admin"]
    r = admin.c.post(
        f"{admin.base}/nodes/{ag['id']}/app/attendance/photo", files=[("files", ("l.jpg", b"x", "image/jpeg"))], headers=admin.h
    )
    assert r.status_code == 503 and "cochez les présents" in r.json()["detail"]


def test_presents_par_l_assistant(client, ecole, ag, db_session):
    """L'assistant lit lui-même la photo envoyée dans la discussion, puis
    pointe les présents par leur nom, sur une carte Faire / Annuler."""
    from app import main

    actions = main.assistant_client.actions
    admin = ecole["admin"]
    proposer = lambda args: actions.propose(db_session, admin, ecole["id"], admin.id, "mark_attendance", args)  # noqa: E731
    nom = "Convocation AGO du 21 novembre 2099"
    texte, carte = proposer({"file": nom, "names": ["ana roux", "Dupont"]})
    assert carte is None and "Dupont" in texte
    _, carte = proposer({"file": nom, "names": ["Ana ROUX", "Perrin Léon"]})
    assert carte["lignes"] == [f"Pointer présents pour « {nom} » : Ana Roux, Léon Perrin (2 personnes)"]
    assert actions.execute(db_session, ecole["id"], admin.id, carte["jeton"])[0]["ok"]
    s = ag["admin"].get(f"/nodes/{ag['id']}/app/attendance").json()
    assert s["present"] == 2


def test_assistant_etat_relance_et_pdf(client, ecole, ag, mails, db_session):
    """Étape 4 (procurations.md §1.4) : l'assistant lit où en est l'AG
    (chiffres de l'appli), relance les sans-réponse comme le bouton de
    Résultats, et range le récapitulatif en PDF dans le dossier de l'AG."""
    from datetime import datetime

    from app import main
    from documents import assembly

    admin, compte = ag["admin"], ecole["admin"]
    actions = main.assistant_client.actions
    proposer = lambda nom, args: actions.propose(db_session, compte, ecole["id"], compte.id, nom, args)
    faire = lambda carte: actions.execute(db_session, ecole["id"], compte.id, carte["jeton"])
    nom = "Convocation AGO du 21 novembre 2099"
    leon = lien(mails, "leon@exemple.fr")
    assert repondre(client, leon, answer="attend").status_code == 201

    # Où en est l'AG : lu avec le fichier, chiffres calculés par l'appli.
    etat = main.assistant_client.fichier_appli.lire(db_session, main._membre_de(db_session, compte.id, ecole["id"]), ag["id"])
    assert "4 convoqués, 1 a répondu : 1 vient, 0 procuration, 0 ne vient pas" in etat
    assert "Sans réponse (3) : Ana Roux, Ima Blanc, Julia Dho" in etat

    # Relancer à l'écran.
    avant = len(mails.envoyes)
    r = admin.c.post(f"{admin.base}/nodes/{ag['id']}/app/assembly/remind", headers=admin.h)
    assert r.status_code == 201 and r.json() == {"sent": 3}
    relances = mails.envoyes[avant:]
    assert {m["to"] for m in relances} == {"julia@exemple.fr", "ima@exemple.fr", "ana@exemple.fr"}
    assert all(m["subject"] == f"Rappel : {nom}" and "pas encore votre réponse" in m["text"] for m in relances)
    # Le rappel automatique de J-7 part quand même.
    assert assembly.remind_due(db_session, mails, main.documents_client.directory, now=datetime(2099, 11, 14, 15, 0)) == 3

    # Relancer par l'assistant : même chose, sur une carte.
    _, carte = proposer("remind_assembly", {"file": nom})
    assert carte["lignes"] == [f"Relancer par email les 3 membres qui n'ont pas répondu à « {nom} » (Ana Roux, Ima Blanc, Julia Dho)"]
    avant = len(mails.envoyes)
    assert faire(carte)[0]["ok"]
    for _ in range(50):  # les emails partent à côté, comme Envoyer
        if len(mails.envoyes) == avant + 3:
            break
        time.sleep(0.02)
    assert len(mails.envoyes) == avant + 3

    # Ranger le récapitulatif : une seule fois dans le dossier, mis à jour ensuite.
    _, carte = proposer("store_assembly_pdf", {"file": nom, "document": "summary"})
    assert carte["lignes"] == ["Ranger « Récapitulatif AGO du 21 novembre 2099.pdf » dans Réunions › AGO du 21 novembre 2099"]
    assert faire(carte)[0]["ok"]
    _, carte = proposer("store_assembly_pdf", {"file": nom, "document": "summary"})
    assert faire(carte)[0]["ok"]
    _, carte = proposer("store_assembly_pdf", {"file": nom, "document": "convocation"})
    assert faire(carte)[0]["ok"]
    noms = list(_par_nom(admin.racine(dossier=ag["folder"])))
    assert noms.count("Récapitulatif AGO du 21 novembre 2099.pdf") == 1 and f"{nom}.pdf" in noms

    # Tout le monde a répondu : plus rien à relancer.
    for x in ("julia", "ima", "ana"):
        assert repondre(client, lien(mails, f"{x}@exemple.fr"), answer="absent").status_code == 201
    texte, carte = proposer("remind_assembly", {"file": nom})
    assert carte is None and "tout le monde a répondu" in texte
    assert admin.c.post(f"{admin.base}/nodes/{ag['id']}/app/assembly/remind", headers=admin.h).status_code == 409
