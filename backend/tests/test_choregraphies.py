"""Tests du module choregraphies (voir spec/SPEC.md §5.3 et §6.7) : une
chorégraphie associée à un cours, ses élèves pris dans toute l'école, ses
vidéos (module générique `videos`), et les droits."""

import pytest
from app.main import app, choregraphies_client, cours_client, videos_client
from comptes import Comptes, rbac
from ecoles import Ecoles
from videos import dossier_ecole


@pytest.fixture()
def e(db_session):
    """Une école : un admin, deux profs (un par cours), des élèves."""
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")

    def compte(role, nom, prenom):
        return comptes.create(db_session, ecole_id=ecole.id, role=role, nom=nom, prenom=prenom)

    donnees = {
        "ecole": ecole,
        "admin": compte("admin", "Dho", "Julia"),
        "prof_jazz": compte("professeur", "Revelles", "Stellina"),
        "prof_classique": compte("professeur", "Petit", "Anne"),
        "zoe": compte("eleve", "Martin", "Zoé"),
        "lea": compte("eleve", "Durand", "Léa"),
        "jazz": cours_client.create(db_session, ecole_id=ecole.id, nom="Jazz Ini"),
        "classique": cours_client.create(db_session, ecole_id=ecole.id, nom="Class Moy"),
    }
    cours_client.ajouter_professeur(db_session, donnees["jazz"].id, donnees["prof_jazz"].id)
    cours_client.ajouter_professeur(db_session, donnees["classique"].id, donnees["prof_classique"].id)
    # Zoé suit le jazz ; Léa aucun de ces deux cours.
    cours_client.inscrire_eleve(db_session, donnees["jazz"].id, donnees["zoe"].id)
    return donnees


@pytest.fixture()
def en_tant_que():
    """Agit au nom d'un compte (les droits restent neutralisés par ailleurs,
    voir conftest.py) : utile là où l'auteur compte (vidéos)."""

    def choisir(compte):
        app.dependency_overrides[rbac.compte_appelant] = lambda: compte

    yield choisir
    app.dependency_overrides[rbac.compte_appelant] = lambda: None


def _envoi(client, ecole):
    """Un envoi de fichier ouvert, pas encore terminé."""
    return client.post(
        f"/ecoles/{ecole.id}/videos/televersements", json={"extension": ".mp4", "octets_total": 100}
    ).json()["id"]


def _ajouter_video(client, choregraphie_id, ecole, nom="Filage", **kw):
    return client.post(
        f"/choregraphies/{choregraphie_id}/videos",
        json={"upload_id": _envoi(client, ecole), "nom": nom},
        **kw,
    )


def test_discipline_et_niveau_deduits_du_nom(e):
    assert (e["jazz"].discipline, e["jazz"].niveau) == ("Jazz", "Initiation")
    assert (e["classique"].discipline, e["classique"].niveau) == ("Classique", "Moyen")


def test_creer_avec_son_cours_puis_lister_toute_l_ecole(client, e):
    creee = client.post(
        f"/cours/{e['jazz'].id}/choregraphies",
        json={"nom": "Spectacle", "costume": "Noir", "eleve_ids": [e["zoe"].id]},
    )
    assert creee.status_code == 201
    assert creee.json() == {
        "id": creee.json()["id"], "cours_id": e["jazz"].id, "cours_ids": [e["jazz"].id], "nom": "Spectacle",
        "horaire_repetition": None, "costume": "Noir", "eleve_ids": [e["zoe"].id], "videos": [],
    }
    client.post(f"/cours/{e['classique'].id}/choregraphies", json={"nom": "Gala"})

    # Une seule requête ramène toutes les chorégraphies de l'école, tous cours confondus.
    liste = client.get(f"/ecoles/{e['ecole'].id}/choregraphies").json()
    assert sorted((c["nom"], c["cours_id"]) for c in liste) == [
        ("Gala", e["classique"].id), ("Spectacle", e["jazz"].id),
    ]
    assert client.post("/cours/999/choregraphies", json={"nom": "X"}).status_code == 404


def test_choregraphie_introuvable(client):
    assert client.get("/choregraphies/999").status_code == 404
    assert client.put("/choregraphies/999", json={"nom": "X"}).status_code == 404
    assert client.delete("/choregraphies/999").status_code == 404


def test_eleves_de_toute_l_ecole(client, db_session, e):
    """Les participants se choisissent dans toute l'école, pas seulement
    dans le cours ; jamais un non-élève ni quelqu'un d'une autre école."""
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    etranger = Comptes().create(db_session, ecole_id=autre.id, role="eleve", nom="X", prenom="Y")
    ch = client.post(f"/cours/{e['jazz'].id}/choregraphies", json={"nom": "Spectacle"}).json()

    demandes = [e["lea"].id, e["zoe"].id, e["lea"].id, e["prof_jazz"].id, etranger.id, 9999]
    modifiee = client.put(f"/choregraphies/{ch['id']}", json={"eleve_ids": demandes}).json()
    assert sorted(modifiee["eleve_ids"]) == sorted([e["lea"].id, e["zoe"].id])
    # Sans `eleve_ids`, la liste ne bouge pas ; une liste vide la vide.
    assert len(client.put(f"/choregraphies/{ch['id']}", json={"costume": "Rouge"}).json()["eleve_ids"]) == 2
    assert client.put(f"/choregraphies/{ch['id']}", json={"eleve_ids": []}).json()["eleve_ids"] == []


def test_changer_de_cours(client, db_session, e):
    ch = client.post(f"/cours/{e['jazz'].id}/choregraphies", json={"nom": "Spectacle"}).json()
    modifiee = client.put(f"/choregraphies/{ch['id']}", json={"cours_ids": [e["classique"].id]}).json()
    assert (modifiee["cours_id"], modifiee["cours_ids"]) == (e["classique"].id, [e["classique"].id])
    assert client.put(f"/choregraphies/{ch['id']}", json={"cours_ids": [999]}).status_code == 404
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    ailleurs = cours_client.create(db_session, ecole_id=autre.id, nom="Jazz")
    assert client.put(f"/choregraphies/{ch['id']}", json={"cours_ids": [ailleurs.id]}).status_code == 400


def test_une_choregraphie_sur_plusieurs_cours(client, db_session, e):
    """Seb, 1er novembre : une même chorégraphie peut être dansée par
    plusieurs cours (avant, il fallait la créer une fois par cours)."""
    jazz, classique = e["jazz"].id, e["classique"].id
    ch = client.post(
        f"/cours/{jazz}/choregraphies", json={"nom": "Begging you", "autres_cours_ids": [classique, jazz]}
    ).json()
    assert (ch["cours_id"], ch["cours_ids"]) == (jazz, [jazz, classique])
    # Chaque cours la retrouve ; l'école ne la liste qu'une fois.
    assert [c.id for c in choregraphies_client.list(db_session, classique)] == [ch["id"]]
    assert [c.id for c in choregraphies_client.list(db_session, jazz)] == [ch["id"]]
    assert [c["id"] for c in client.get(f"/ecoles/{e['ecole'].id}/choregraphies").json()] == [ch["id"]]

    # Retirer le premier cours : le suivant prend sa place.
    modifiee = client.put(f"/choregraphies/{ch['id']}", json={"cours_ids": [classique]}).json()
    assert (modifiee["cours_id"], modifiee["cours_ids"]) == (classique, [classique])
    assert choregraphies_client.list(db_session, jazz) == []
    # Une liste vide ne change rien : une chorégraphie a toujours un cours.
    assert client.put(f"/choregraphies/{ch['id']}", json={"cours_ids": []}).json()["cours_ids"] == [classique]

    # Un cours d'une autre saison est refusé.
    from saisons.models import Saison
    import datetime as dt

    ancienne = Saison(ecole_id=e["ecole"].id, nom="2020-2021", date_debut=dt.date(2020, 9, 1), date_fin=dt.date(2021, 6, 30))
    db_session.add(ancienne)
    db_session.flush()
    vieux = cours_client.create(db_session, ecole_id=e["ecole"].id, nom="Jazz Ini")
    vieux.saison_id = ancienne.id
    db_session.commit()
    assert client.put(f"/choregraphies/{ch['id']}", json={"cours_ids": [classique, vieux.id]}).status_code in (400, 404)

    # Supprimer la chorégraphie la retire de tous ses cours.
    assert client.delete(f"/choregraphies/{ch['id']}").status_code == 204
    assert choregraphies_client.list(db_session, classique) == []


def test_videos_d_une_choregraphie(client, e, en_tant_que):
    """Ajout (l'auteur est l'appelant), ordre, modification, suppression."""
    en_tant_que(e["admin"])
    ch = client.post(f"/cours/{e['jazz'].id}/choregraphies", json={"nom": "Spectacle"}).json()
    en_tant_que(e["zoe"])
    v1 = _ajouter_video(client, ch["id"], e["ecole"], "Prise 1")
    assert v1.status_code == 201
    assert (v1.json()["uploaded_by"], v1.json()["statut"]) == (e["zoe"].id, "en_cours")
    en_tant_que(e["admin"])
    v2 = _ajouter_video(client, ch["id"], e["ecole"], "Prise 2").json()
    v1 = v1.json()

    lire = lambda: [v["nom"] for v in client.get(f"/choregraphies/{ch['id']}").json()["videos"]]
    assert lire() == ["Prise 1", "Prise 2"]
    assert client.put(f"/choregraphies/{ch['id']}/videos/ordre", json={"ordre_video_ids": [v2["id"], v1["id"]]}).status_code == 204
    assert lire() == ["Prise 2", "Prise 1"]

    assert client.put(f"/choregraphies/{ch['id']}/videos/{v1['id']}", json={"nom": "Filage"}).json()["nom"] == "Filage"
    assert client.delete(f"/choregraphies/{ch['id']}/videos/{v2['id']}").status_code == 204
    assert lire() == ["Filage"]
    assert client.get(f"/videos/{v2['id']}").status_code == 404

    # Une vidéo ne se manipule que dans SA chorégraphie.
    autre = client.post(f"/cours/{e['jazz'].id}/choregraphies", json={"nom": "Gala"}).json()
    assert client.delete(f"/choregraphies/{autre['id']}/videos/{v1['id']}").status_code == 404
    assert client.post(f"/choregraphies/{ch['id']}/videos", json={"upload_id": "inconnu", "nom": "X"}).status_code == 404


def test_double_clic_sur_ajouter_ne_cree_qu_une_video(client, e, en_tant_que):
    en_tant_que(e["admin"])
    ch = client.post(f"/cours/{e['jazz'].id}/choregraphies", json={"nom": "Spectacle"}).json()
    corps = {"upload_id": _envoi(client, e["ecole"]), "nom": "Filage"}
    premiere = client.post(f"/choregraphies/{ch['id']}/videos", json=corps).json()
    seconde = client.post(f"/choregraphies/{ch['id']}/videos", json=corps).json()
    assert premiere["id"] == seconde["id"]
    assert len(client.get(f"/choregraphies/{ch['id']}").json()["videos"]) == 1


def test_annuler_l_envoi_retire_la_video_de_la_choregraphie(client, db_session, e, en_tant_que):
    from choregraphies import choregraphies_videos
    from sqlalchemy import select

    en_tant_que(e["admin"])
    ch = client.post(f"/cours/{e['jazz'].id}/choregraphies", json={"nom": "Spectacle"}).json()
    upload_id = _envoi(client, e["ecole"])
    client.post(f"/choregraphies/{ch['id']}/videos", json={"upload_id": upload_id, "nom": "Annulée"})

    assert client.delete(f"/videos/televersements/{upload_id}").status_code == 204
    assert client.get(f"/choregraphies/{ch['id']}").json()["videos"] == []
    assert db_session.execute(select(choregraphies_videos)).all() == []


def test_supprimer_la_choregraphie_supprime_ses_videos_et_leurs_fichiers(client, db_session, e):
    ch = choregraphies_client.create(db_session, e["jazz"].id, nom="Spectacle", eleve_ids=[e["zoe"].id])
    fichier = dossier_ecole(e["ecole"].id) / "spectacle.mp4"
    fichier.write_bytes(b"x")
    video = videos_client.create(
        db_session, ecole_id=e["ecole"].id, nom="Filage", uploaded_by=e["admin"].id,
        lien_fichier=f"{e['ecole'].id}/spectacle.mp4",
    )
    choregraphies_client.attacher_video(db_session, ch.id, video.id)
    video_id = video.id

    assert client.delete(f"/choregraphies/{ch.id}").status_code == 204
    assert client.get(f"/videos/{video_id}").status_code == 404
    assert not fichier.exists()
    assert client.get(f"/ecoles/{e['ecole'].id}/choregraphies").json() == []


# --- Droits (les vraies vérifications, spec §5.3) ---


@pytest.mark.rbac_reel
def test_droits_sur_les_choregraphies(client, db_session, e):
    from conftest import entetes_session

    s = {nom: entetes_session(e[nom]) for nom in ("admin", "prof_jazz", "prof_classique", "zoe", "lea")}
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    etranger = entetes_session(Comptes().create(db_session, ecole_id=autre.id, role="admin", nom="X", prenom="Y"))
    jazz, classique = e["jazz"].id, e["classique"].id

    # Créer : un admin, ou un professeur DU cours.
    assert client.post(f"/cours/{jazz}/choregraphies", json={"nom": "X"}).status_code == 401
    for qui in ("zoe", "prof_classique"):
        assert client.post(f"/cours/{jazz}/choregraphies", json={"nom": "X"}, headers=s[qui]).status_code == 403
    assert client.post(f"/cours/{jazz}/choregraphies", json={"nom": "X"}, headers=etranger).status_code == 403
    ch = client.post(f"/cours/{jazz}/choregraphies", json={"nom": "Spectacle"}, headers=s["prof_jazz"])
    assert ch.status_code == 201
    ch = ch.json()["id"]
    assert client.post(f"/cours/{classique}/choregraphies", json={"nom": "Gala"}, headers=s["admin"]).status_code == 201

    # Lire : toute l'école voit toutes les chorégraphies, même hors de ses cours.
    for qui in ("zoe", "lea", "prof_classique"):
        assert len(client.get(f"/ecoles/{e['ecole'].id}/choregraphies", headers=s[qui]).json()) == 2
        assert client.get(f"/choregraphies/{ch}", headers=s[qui]).status_code == 200
    assert client.get(f"/ecoles/{e['ecole'].id}/choregraphies", headers=etranger).status_code == 403
    assert client.get(f"/choregraphies/{ch}", headers=etranger).status_code == 403

    # Modifier, supprimer : mêmes personnes que créer.
    for qui in ("zoe", "prof_classique"):
        assert client.put(f"/choregraphies/{ch}", json={"nom": "X"}, headers=s[qui]).status_code == 403
        assert client.delete(f"/choregraphies/{ch}", headers=s[qui]).status_code == 403
    assert client.put(f"/choregraphies/{ch}", json={"costume": "Noir"}, headers=s["prof_jazz"]).status_code == 200
    # Ajouter un cours : il faut pouvoir le gérer aussi.
    assert client.put(f"/choregraphies/{ch}", json={"cours_ids": [jazz, classique]}, headers=s["prof_jazz"]).status_code == 403
    assert client.post(
        f"/cours/{jazz}/choregraphies", json={"nom": "X", "autres_cours_ids": [classique]}, headers=s["prof_jazz"]
    ).status_code == 403
    # Une fois le cours ajouté (par un admin), ses profs la gèrent aussi...
    assert client.put(f"/choregraphies/{ch}", json={"cours_ids": [jazz, classique]}, headers=s["admin"]).status_code == 200
    assert client.put(f"/choregraphies/{ch}", json={"costume": "Blanc"}, headers=s["prof_classique"]).status_code == 200
    # ... mais chacun ne retire que son propre cours.
    assert client.put(f"/choregraphies/{ch}", json={"cours_ids": [classique]}, headers=s["prof_classique"]).status_code == 403
    assert client.put(f"/choregraphies/{ch}", json={"cours_ids": [jazz]}, headers=s["prof_classique"]).status_code == 200
    assert client.delete(f"/choregraphies/{ch}", headers=s["admin"]).status_code == 204


@pytest.mark.rbac_reel
def test_droits_sur_les_videos_d_une_choregraphie(client, db_session, e):
    from conftest import entetes_session

    s = {nom: entetes_session(e[nom]) for nom in ("admin", "prof_jazz", "prof_classique", "zoe", "lea")}
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    etranger = entetes_session(Comptes().create(db_session, ecole_id=autre.id, role="admin", nom="X", prenom="Y"))
    ch = choregraphies_client.create(db_session, e["jazz"].id, nom="Spectacle").id

    def ajouter(qui, entetes):
        upload = client.post(
            f"/ecoles/{e['ecole'].id}/videos/televersements",
            json={"extension": ".mp4", "octets_total": 100}, headers=s["admin"],
        ).json()["id"]
        return client.post(f"/choregraphies/{ch}/videos", json={"upload_id": upload, "nom": qui}, headers=entetes)

    # Ajouter : tout le monde dans l'école, même hors du cours.
    assert ajouter("personne", {}).status_code == 401
    assert ajouter("etranger", etranger).status_code == 403
    de_zoe = ajouter("zoe", s["zoe"])
    assert de_zoe.status_code == 201 and de_zoe.json()["uploaded_by"] == e["zoe"].id
    de_lea = ajouter("lea", s["lea"]).json()["id"]
    du_prof = ajouter("prof", s["prof_classique"]).json()["id"]
    de_zoe = de_zoe.json()["id"]

    # Modifier, réordonner : un admin ou un professeur du cours seulement.
    for qui in ("zoe", "prof_classique"):
        assert client.put(f"/choregraphies/{ch}/videos/{de_zoe}", json={"nom": "X"}, headers=s[qui]).status_code == 403
        assert client.put(f"/choregraphies/{ch}/videos/ordre", json={"ordre_video_ids": [de_lea, de_zoe]}, headers=s[qui]).status_code == 403
    assert client.put(f"/choregraphies/{ch}/videos/{de_zoe}", json={"nom": "Filage"}, headers=s["prof_jazz"]).status_code == 200
    assert client.put(f"/choregraphies/{ch}/videos/ordre", json={"ordre_video_ids": [de_lea, de_zoe]}, headers=s["admin"]).status_code == 204

    # Supprimer : eux, et l'auteur de la vidéo.
    assert client.delete(f"/choregraphies/{ch}/videos/{de_lea}", headers=s["zoe"]).status_code == 403
    assert client.delete(f"/choregraphies/{ch}/videos/{de_zoe}", headers=s["zoe"]).status_code == 204
    assert client.delete(f"/choregraphies/{ch}/videos/{de_lea}", headers=s["prof_jazz"]).status_code == 204
    assert client.delete(f"/choregraphies/{ch}/videos/{du_prof}", headers=s["prof_classique"]).status_code == 204


def test_une_video_compressee_par_le_telephone_n_est_pas_recompressee(client, db_session, e, en_tant_que):
    """Une seule compression (Seb, 2026-10-15) : le téléphone a compressé,
    le serveur n'y touche pas ; arrivée telle que filmée, il la compresse."""
    from app.main import videos_client
    from videos.models import Video

    en_tant_que(e["admin"])
    ch = client.post(f"/cours/{e['jazz'].id}/choregraphies", json={"nom": "Spectacle"}).json()
    par_le_telephone = client.post(
        f"/choregraphies/{ch['id']}/videos",
        json={"upload_id": _envoi(client, e["ecole"]), "nom": "Compressée", "deja_compresse": True},
    ).json()
    brute = _ajouter_video(client, ch["id"], e["ecole"], nom="Telle que filmée").json()
    for v in db_session.query(Video).filter(Video.id.in_([par_le_telephone["id"], brute["id"]])):
        v.statut, v.lien_fichier = "complete", f"{e['ecole'].id}/x{v.id}.mp4"
    db_session.commit()
    a_compresser = {v.id for v in videos_client.videos_a_compresser(db_session)}
    assert brute["id"] in a_compresser and par_le_telephone["id"] not in a_compresser
