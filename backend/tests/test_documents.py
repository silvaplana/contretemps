"""Onglet Docs : dossiers et fichiers (module src/documents/, branché par
src/documents_contretemps/). Vraies sessions : les droits sont le sujet."""

import io

import pytest
from conftest import entetes_session
from comptes import Comptes
from cours import CoursService
from ecoles import Ecoles
from eleves import Eleves

from app import main

pytestmark = pytest.mark.rbac_reel

NOUVELLE = {"nom": "2027-2028", "date_debut": "2027-09-01", "date_fin": "2028-08-31"}


@pytest.fixture(autouse=True)
def stockage(tmp_path, monkeypatch):
    monkeypatch.setattr(main.documents_client.storage, "root", tmp_path)
    return tmp_path


@pytest.fixture()
def ecole(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = comptes.create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    prof = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Blanc", prenom="Ima")
    eleve, _ = Eleves(comptes=comptes).create(db_session, ecole_id=ecole.id, nom="Perrin", prenom="Léon")
    autre, _ = Eleves(comptes=comptes).create(db_session, ecole_id=ecole.id, nom="Roux", prenom="Ana")
    cours = CoursService().create(db_session, ecole_id=ecole.id, nom="Éveil")
    CoursService().inscrire_eleve(db_session, cours.id, eleve.id)
    voisine = Ecoles().create(db_session, nom="Voisine", code_postal="83000")
    admin_voisin = comptes.create(db_session, ecole_id=voisine.id, role="admin", nom="Z", prenom="W")
    return {
        "id": ecole.id, "admin": admin, "prof": prof, "eleve": eleve, "autre": autre,
        "cours": cours, "admin_voisin": admin_voisin,
    }


class Docs:
    """Petit client : appelle l'API en tant que `compte`."""

    def __init__(self, client, ecole_id, compte):
        self.c, self.base, self.h = client, f"/documents/orgs/{ecole_id}", entetes_session(compte)

    def get(self, chemin, **params):
        return self.c.get(self.base + chemin, params=params, headers=self.h)

    def racine(self, espace="private", dossier=None):
        params = {"folder": dossier} if dossier else {}
        return self.get(f"/spaces/{espace}", **params)

    def dossier(self, nom, parent=None, espace="private"):
        return self.c.post(self.base + "/folders", json={"space": espace, "parent_id": parent, "name": nom}, headers=self.h)

    def fichier(self, nom, parent=None, espace="private", contenu=b"bonjour"):
        donnees = {"space": espace}
        if parent is not None:
            donnees["parent_id"] = str(parent)
        return self.c.post(self.base + "/files", data=donnees, files={"file": (nom, io.BytesIO(contenu))}, headers=self.h)

    def modifier(self, node_id, **corps):
        return self.c.patch(f"{self.base}/nodes/{node_id}", json=corps, headers=self.h)

    def supprimer(self, node_id):
        return self.c.delete(f"{self.base}/nodes/{node_id}", headers=self.h)

    def acces(self, node_id, restricted=False, entries=()):
        return self.c.put(
            f"{self.base}/nodes/{node_id}/access", json={"restricted": restricted, "entries": list(entries)}, headers=self.h
        )


def _par_nom(reponse):
    return {e["name"]: e for e in reponse.json()["items"]}


def _saison(docs):
    return next(e for e in docs.racine().json()["items"] if e["system_kind"] == "period")


def test_dossiers_systeme_de_prive(client, ecole):
    admin = Docs(client, ecole["id"], ecole["admin"])
    elements = admin.racine().json()["items"]
    assert [e["system_kind"] for e in elements] == ["permanent", "period"]
    assert elements[0]["name"] == "Permanent"
    assert elements[1]["name"].startswith("Saison ")
    for e in elements:
        assert admin.modifier(e["id"], name="Autre").status_code == 409
        assert admin.supprimer(e["id"]).status_code == 409


def test_espaces_selon_le_role(client, ecole):
    cles = lambda c: [e["key"] for e in Docs(client, ecole["id"], c).get("/spaces").json()]  # noqa: E731
    assert cles(ecole["prof"]) == ["public", "private", "personal"]
    # Pas d'espace Personnel pour les élèves.
    assert cles(ecole["eleve"]) == ["public", "private"]
    assert Docs(client, ecole["id"], ecole["eleve"]).racine("personal").status_code == 404


def test_un_prof_ecrit_dans_prive_un_eleve_ne_voit_rien(client, ecole):
    prof, eleve = Docs(client, ecole["id"], ecole["prof"]), Docs(client, ecole["id"], ecole["eleve"])
    saison = _saison(prof)["id"]
    ag = prof.dossier("AG 2027", saison).json()["id"]
    statuts = prof.fichier("Statuts.pdf", ag, contenu=b"%PDF-1.4").json()["id"]

    assert eleve.racine().json()["items"] == []
    assert eleve.racine(dossier=ag).status_code == 404
    assert eleve.get("/spaces/private/search", q="statuts").json() == []
    assert eleve.get(f"/nodes/{statuts}/content").status_code == 404
    assert eleve.dossier("Pirate", ag).status_code == 404

    contenu = prof.get(f"/nodes/{statuts}/content")
    assert contenu.status_code == 200 and contenu.content == b"%PDF-1.4"
    assert [e["name"] for e in prof.get("/spaces/private/search", q="STATUT").json()] == ["Statuts.pdf"]


def test_partager_un_dossier_a_un_cours(client, ecole):
    prof, eleve, autre = (Docs(client, ecole["id"], ecole[q]) for q in ("prof", "eleve", "autre"))
    admin = Docs(client, ecole["id"], ecole["admin"])
    saison = _saison(admin)["id"]
    eveil = admin.dossier("Cours Éveil", saison).json()["id"]
    prof.fichier("Chorégraphie.docx", eveil)
    # Un prof n'a que l'Écriture : il ne partage pas (la Gestion reste aux admins).
    groupe = {"type": "group", "id": f"course:{ecole['cours'].id}", "level": "view"}
    assert prof.acces(eveil, entries=[groupe]).status_code == 403
    assert admin.acces(eveil, entries=[groupe]).status_code == 200

    # À la racine de Privé, l'élève trouve ce qui lui est partagé (pas le
    # dossier de saison au-dessus, qui ne l'est pas).
    racine = eleve.racine().json()
    assert racine["shared_with_me"] is True and [e["name"] for e in racine["items"]] == ["Cours Éveil"]
    dedans = eleve.racine(dossier=eveil).json()
    assert [e["name"] for e in dedans["items"]] == ["Chorégraphie.docx"]
    assert [b["name"] for b in dedans["breadcrumb"]] == ["Cours Éveil"]
    assert eleve.fichier("Copie.docx", eveil).status_code == 403
    assert autre.racine(dossier=eveil).status_code == 404

    acces = admin.get(f"/nodes/{eveil}/access").json()
    assert [d["label"] for d in acces["direct"]] == ["Cours Éveil"]
    assert {h["label"] for h in acces["inherited"]} >= {"Admins", "Professeurs"}
    # Gestion jamais donnée par un partage.
    assert admin.acces(eveil, entries=[{**groupe, "level": "manage"}]).status_code == 422


def test_dossier_restreint(client, ecole):
    admin, prof = Docs(client, ecole["id"], ecole["admin"]), Docs(client, ecole["id"], ecole["prof"])
    permanent = admin.racine().json()["items"][0]["id"]
    bureau = admin.dossier("Bureau", permanent).json()["id"]
    assert prof.acces(bureau, restricted=True).status_code == 403
    assert admin.acces(bureau, restricted=True).status_code == 200
    assert "Bureau" not in _par_nom(prof.racine(dossier=permanent))
    assert admin.racine(dossier=bureau).status_code == 200
    # Un fichier aussi peut être restreint (Seb, 15 octobre) : voir test_fichier_en_acces_restreint.


def test_officiel_fige_le_contenu(client, ecole):
    admin, prof = Docs(client, ecole["id"], ecole["admin"]), Docs(client, ecole["id"], ecole["prof"])
    saison = _saison(admin)["id"]
    ag = prof.dossier("AG", saison).json()["id"]
    pv = prof.fichier("PV.docx", ag).json()["id"]
    assert prof.modifier(pv, change_status=True, status="draft").status_code == 200
    assert prof.modifier(pv, change_status=True, status="official").status_code == 403
    assert admin.modifier(ag, change_status=True, status="official").status_code == 200
    assert prof.fichier("Autre.docx", ag).status_code == 409
    assert prof.modifier(pv, name="PV final.docx").status_code == 409
    assert prof.supprimer(pv).status_code == 409
    assert admin.racine(dossier=ag).json()["items"][0]["frozen"] is True


def test_valide_repasse_en_brouillon_si_modifie_par_un_prof(client, ecole):
    admin, prof = Docs(client, ecole["id"], ecole["admin"]), Docs(client, ecole["id"], ecole["prof"])
    saison = _saison(admin)["id"]
    plan = prof.fichier("Planning.xlsx", saison).json()["id"]
    assert admin.modifier(plan, change_status=True, status="validated").status_code == 200
    reponse = client.post(
        f"{prof.base}/nodes/{plan}/versions", files={"file": ("Planning.xlsx", io.BytesIO(b"v2"))}, headers=prof.h
    )
    assert reponse.status_code == 201
    detail = prof.get(f"/nodes/{plan}").json()
    assert detail["status"] == "draft"
    assert [v["number"] for v in detail["versions"]] == [2, 1]


def test_corbeille_et_restauration(client, ecole):
    prof = Docs(client, ecole["id"], ecole["prof"])
    saison = _saison(prof)["id"]
    photos = prof.dossier("Photos", saison).json()["id"]
    prof.fichier("gala.jpg", photos)
    assert prof.supprimer(photos).status_code == 204
    assert "Photos" not in _par_nom(prof.racine(dossier=saison))
    corbeille = prof.get("/spaces/private/trash").json()
    assert [e["name"] for e in corbeille] == ["Photos"]
    assert client.post(f"{prof.base}/nodes/{photos}/restore", headers=prof.h).status_code == 200
    assert _par_nom(prof.racine(dossier=saison))["Photos"]["child_count"] == 1


def test_vider_la_corbeille(client, ecole, stockage):
    prof = Docs(client, ecole["id"], ecole["prof"])
    admin = Docs(client, ecole["id"], ecole["admin"])
    saison = _saison(prof)["id"]
    photos = prof.dossier("Photos", saison).json()["id"]
    prof.fichier("gala.jpg", photos, contenu=b"photo du gala")
    prof.supprimer(photos)
    admin.supprimer(admin.dossier("Brouillons admin", saison).json()["id"])
    fichiers_avant = [f for f in stockage.rglob("*") if f.is_file()]
    assert fichiers_avant

    # Le prof ne vide que ce qu'il a supprimé lui-même.
    vide = client.delete(f"{prof.base}/spaces/private/trash", headers=prof.h)
    assert vide.status_code == 200 and vide.json() == {"erased": 1}
    assert prof.get("/spaces/private/trash").json() == []
    assert [e["name"] for e in admin.get("/spaces/private/trash").json()] == ["Brouillons admin"]
    # Plus restaurable, et le fichier a quitté le disque.
    assert client.post(f"{prof.base}/nodes/{photos}/restore", headers=prof.h).status_code == 404
    assert not [f for f in stockage.rglob("*") if f.is_file() and f.read_bytes() == b"photo du gala"]


def test_noms_en_double(client, ecole):
    prof = Docs(client, ecole["id"], ecole["prof"])
    saison = _saison(prof)["id"]
    assert prof.fichier("Note.pdf", saison).json()["name"] == "Note.pdf"
    assert prof.fichier("note.pdf", saison).json()["name"] == "note (2).pdf"
    autre = prof.dossier("Dossier", saison).json()["id"]
    assert prof.modifier(autre, name="NOTE.PDF").status_code == 409


def test_deplacer(client, ecole):
    prof = Docs(client, ecole["id"], ecole["prof"])
    racine = prof.racine().json()["items"]
    permanent, saison = racine[0]["id"], racine[1]["id"]
    a = prof.dossier("A", saison).json()["id"]
    b = prof.dossier("B", a).json()["id"]
    assert prof.modifier(a, move=True, space="private", parent_id=b).status_code == 409
    assert prof.modifier(b, move=True, space="private", parent_id=permanent).status_code == 200
    assert "B" in _par_nom(prof.racine(dossier=permanent))
    # Vers l'espace Personnel : le contenu suit.
    f = prof.fichier("brouillon.txt", b).json()["id"]
    assert prof.modifier(b, move=True, space="personal", parent_id=None).status_code == 200
    assert prof.get(f"/nodes/{f}").json()["space"] == "personal"
    assert Docs(client, ecole["id"], ecole["admin"]).get(f"/nodes/{f}").status_code == 404


def test_saison_passee_en_lecture_seule(client, ecole):
    admin = Docs(client, ecole["id"], ecole["admin"])
    ancienne = _saison(admin)["id"]
    ag = admin.dossier("AG", ancienne).json()["id"]
    reponse = client.post(f"/ecoles/{ecole['id']}/saisons", json=NOUVELLE, headers=admin.h)
    assert reponse.status_code == 201
    nouvelle_fiche = reponse.json()["compte_id"]
    admin.h = {**admin.h, "X-Compte-Id": str(nouvelle_fiche)}

    saisons = [e for e in admin.racine().json()["items"] if e["system_kind"] == "period"]
    assert [(s["name"], s["period_current"]) for s in saisons][0] == ("Saison 2027-2028", True)
    vieille = next(s for s in saisons if s["id"] == ancienne)
    assert vieille["closed_period"] is True and vieille["level"] == "view"
    # Même un admin n'y écrit plus ; la lecture reste.
    assert admin.dossier("Nouveau", ancienne).status_code == 403
    assert admin.supprimer(ag).status_code == 403
    assert admin.racine(dossier=ag).status_code == 200


def test_nouvelle_saison_recopie_le_dossier_de_la_precedente(client, ecole):
    admin = Docs(client, ecole["id"], ecole["admin"])
    ancienne = _saison(admin)["id"]
    ag = admin.dossier("AG", ancienne).json()["id"]
    admin.fichier("Convocation.pdf", ag, contenu=b"%PDF convocation")
    assert admin.modifier(ag, change_status=True, status="official").status_code == 200
    eveil = admin.dossier("Éveil", ancienne).json()["id"]
    cle_eveil = f"course:{ecole['cours'].id}"
    entrees = [{"type": "group", "id": cle_eveil, "level": "view"}]
    assert admin.acces(eveil, restricted=True, entries=entrees).status_code == 200
    jete = admin.dossier("Brouillons", ancienne).json()["id"]
    admin.supprimer(jete)

    cases = {"dupliquer_profs": True, "dupliquer_cours": True, "dupliquer_eleves": True, "dupliquer_documents": True}
    reponse = client.post(f"/ecoles/{ecole['id']}/saisons", json={**NOUVELLE, **cases}, headers=admin.h)
    assert reponse.status_code == 201
    admin.h = {**admin.h, "X-Compte-Id": str(reponse.json()["compte_id"])}

    nouvelle = _saison(admin)
    assert nouvelle["name"] == "Saison 2027-2028" and nouvelle["period_current"] is True
    contenu = _par_nom(admin.racine(dossier=nouvelle["id"]))
    # Le contenu est recopié (pas la corbeille), modifiable, et repart en Brouillon.
    assert set(contenu) == {"AG", "Éveil"}
    assert contenu["AG"]["status"] == "draft" and contenu["AG"]["level"] == "manage"
    assert set(_par_nom(admin.racine(dossier=contenu["AG"]["id"]))) == {"Convocation.pdf"}
    # « Accès restreint » suit, et le partage passe au cours Éveil de la nouvelle saison.
    acces = admin.get(f"/nodes/{contenu['Éveil']['id']}/access").json()
    assert acces["restricted"] is True
    cles = [e["id"] for e in acces["direct"]]
    assert cles and cle_eveil not in cles and all(c.startswith("course:") for c in cles)
    # L'ancienne saison est intacte.
    assert set(_par_nom(admin.racine(dossier=ancienne))) == {"AG", "Éveil"}


def test_nouvelle_saison_sans_recopie_des_documents(client, ecole):
    admin = Docs(client, ecole["id"], ecole["admin"])
    admin.dossier("AG", _saison(admin)["id"])
    reponse = client.post(f"/ecoles/{ecole['id']}/saisons", json=NOUVELLE, headers=admin.h)
    admin.h = {**admin.h, "X-Compte-Id": str(reponse.json()["compte_id"])}
    assert admin.racine(dossier=_saison(admin)["id"]).json()["items"] == []


def test_autre_ecole_refusee(client, ecole):
    voisin = Docs(client, ecole["id"], ecole["admin_voisin"])
    assert voisin.racine().status_code == 403


def test_sans_session(client, ecole):
    assert client.get(f"/documents/orgs/{ecole['id']}/spaces/public").status_code == 401


def test_vignette_d_une_photo(client, ecole):
    from PIL import Image

    image = io.BytesIO()
    Image.new("RGB", (800, 600), "orange").save(image, "PNG")
    prof = Docs(client, ecole["id"], ecole["prof"])
    photo = prof.fichier("gala.png", _saison(prof)["id"], contenu=image.getvalue()).json()["id"]
    vignette = prof.get(f"/nodes/{photo}/thumbnail")
    assert vignette.status_code == 200 and vignette.headers["content-type"] == "image/jpeg"


def test_copier_coller(client, ecole):
    admin, prof = Docs(client, ecole["id"], ecole["admin"]), Docs(client, ecole["id"], ecole["prof"])
    racine = prof.racine().json()["items"]
    permanent, saison = racine[0]["id"], racine[1]["id"]
    ag = prof.dossier("AG", saison).json()["id"]
    pv = prof.fichier("PV.docx", ag, contenu=b"pv").json()["id"]
    assert admin.modifier(pv, change_status=True, status="official").status_code == 200

    copier = lambda node, parent: client.post(  # noqa: E731
        f"{prof.base}/nodes/{node}/copy", json={"space": "private", "parent_id": parent}, headers=prof.h
    )
    copie = copier(ag, permanent)
    assert copie.status_code == 201 and copie.json()["name"] == "AG"
    dedans = prof.racine(dossier=copie.json()["id"]).json()["items"]
    assert [(e["name"], e["status"]) for e in dedans] == [("PV.docx", "draft")]
    assert prof.get(f"/nodes/{dedans[0]['id']}/content").content == b"pv"
    # Coller au même endroit : « AG (2) ».
    assert copier(ag, saison).json()["name"] == "AG (2)"
    assert copier(ag, ag).status_code == 409
    assert copier(permanent, saison).status_code == 409


def test_recents(client, ecole):
    """Les derniers fichiers modifiés, tous espaces, seulement ceux qu'on peut voir."""
    admin = Docs(client, ecole["id"], ecole["admin"])
    eleve = Docs(client, ecole["id"], ecole["eleve"])
    saison = _saison(admin)["id"]
    admin.fichier("Budget.xlsx", saison)
    admin.fichier("Affiche.pdf", espace="public")
    admin.fichier("Brouillon perso.txt", espace="personal")
    recents = admin.get("/recent").json()
    assert [r["name"] for r in recents][:3] == ["Brouillon perso.txt", "Affiche.pdf", "Budget.xlsx"]
    assert recents[2]["path"][-1]["id"] == saison and recents[2]["space"] == "private"
    # L'élève ne voit que le Public.
    assert [r["name"] for r in eleve.get("/recent").json()] == ["Affiche.pdf"]


def test_fichier_en_acces_restreint(client, ecole):
    """Le cadenas vaut aussi pour un fichier (Seb, 15 octobre) : restreint,
    il n'est plus visible que des personnes choisies et des admins."""
    admin = Docs(client, ecole["id"], ecole["admin"])
    prof = Docs(client, ecole["id"], ecole["prof"])
    saison = _saison(admin)["id"]
    fichier = admin.fichier("Salaires.xlsx", saison).json()["id"]
    assert "Salaires.xlsx" in _par_nom(prof.racine(dossier=saison))
    assert admin.get(f"/nodes/{fichier}/access").json()["can_restrict"] is True
    assert admin.acces(fichier, restricted=True).status_code == 200
    assert _par_nom(admin.racine(dossier=saison))["Salaires.xlsx"]["restricted"] is True
    assert "Salaires.xlsx" not in _par_nom(prof.racine(dossier=saison))


def test_apercu_pdf_des_fichiers_office(client, ecole, monkeypatch):
    """Word / Excel / PowerPoint : aperçu en PDF par LibreOffice (simulé ici),
    fait une seule fois puis gardé ; pas d'aperçu pour les autres formats."""
    import documents.service as service

    appels = []

    def faux_convertir(source, nom, cible):
        appels.append(nom)
        cible.parent.mkdir(parents=True, exist_ok=True)
        cible.write_bytes(b"%PDF-1.4 apercu")
        return True

    monkeypatch.setattr(service, "convert_to_pdf", faux_convertir)
    admin = Docs(client, ecole["id"], ecole["admin"])
    eleve = Docs(client, ecole["id"], ecole["eleve"])
    saison = _saison(admin)["id"]
    budget = admin.fichier("Budget.xlsx", saison, contenu=b"PK fake xlsx").json()["id"]
    for _ in range(2):
        reponse = admin.get(f"/nodes/{budget}/preview")
        assert reponse.status_code == 200 and reponse.headers["content-type"] == "application/pdf"
        assert reponse.content == b"%PDF-1.4 apercu"
    assert appels == ["Budget.xlsx"]  # converti une seule fois
    # Pas d'aperçu pour un texte (affiché tel quel par l'appli), ni pour qui ne voit pas le fichier.
    note = admin.fichier("Note.txt", saison).json()["id"]
    assert admin.get(f"/nodes/{note}/preview").status_code == 415
    assert eleve.get(f"/nodes/{budget}/preview").status_code == 404
    # Conversion impossible (LibreOffice absent) : message clair.
    monkeypatch.setattr(service, "convert_to_pdf", lambda *a: False)
    autre = admin.fichier("Lettre.docx", saison, contenu=b"PK fake docx").json()["id"]
    assert admin.get(f"/nodes/{autre}/preview").status_code == 503
