"""Labo de Fights (spec/modules/video-combats.md §6.5 bis) : une vidéo déjà
filmée envoyée par un coach, lue par le worker (détecteur simulé), ses
signes avec une image de chacun, ses combats selon les « Signes et sons du
club », droits et étanchéité."""

import json

import pytest
from conftest import entetes_session
from test_session_clips_camera import _morceau
from test_session_clips_cutting import frames, pose

from app.main import core
from comptes import Comptes
from ecoles import Ecoles
from session_clips import lab
from session_clips.models import LabTest

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def e(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Fight Lab", code_postal="13600")
    autre = Ecoles().create(db_session, nom="Autre club", code_postal="75001")
    coach = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Durand", prenom="Flo")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Richard", prenom="Seb")
    ailleurs = comptes.create(db_session, ecole_id=autre.id, role="professeur", nom="Nom", prenom="Coach")
    return {
        "ecole": ecole,
        "coach": entetes_session(coach),
        "eleve": entetes_session(eleve),
        "ailleurs": entetes_session(ailleurs),
    }


def _importer(client, e, donnees):
    upload = client.post(
        f"/ecoles/{e['ecole'].id}/videos/televersements",
        json={"extension": ".mp4", "octets_total": len(donnees)},
        headers=e["coach"],
    ).json()["id"]
    r = client.post("/session-clips/lab", json={"upload_id": upload, "title": "Combat du 11/11"}, headers=e["coach"])
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "uploading"
    r = client.put(
        f"/videos/televersements/{upload}",
        content=donnees,
        headers={**e["coach"], "X-Decalage": "0"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_essai_du_labo(client, db_session, e, tmp_path, monkeypatch):
    videos_dir = tmp_path / "videos"
    for cible in ("videos.stockage", "session_clips.lab", "videos.videos"):
        monkeypatch.setattr(f"{cible}.DOSSIER_VIDEOS_LIVE", videos_dir)
    _importer(client, e, _morceau(tmp_path, 0, secondes=30))
    [essai] = client.get("/session-clips/lab", headers=e["coach"]).json()
    assert essai["status"] == "processing" and essai["title"] == "Combat du 11/11"

    touch = [pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]
    fight = [pose(100), pose(300)]
    hand = [pose(100, "hand"), pose(145, "hand", wrist_dx=-50)]
    x = [pose(100, "x"), pose(300, "x")]
    postures = frames([(1, touch), (9, fight), (2, hand), (8, fight), (2, x), (8, [])])
    test = db_session.get(LabTest, essai["id"])
    assert lab.tests_to_read(db_session) == [test]
    assert lab.read_test(db_session, core.session_clips_client, test, lambda _p: postures, lambda _p: [25.0]) == 4
    assert lab.tests_to_read(db_session) == []

    detail = client.get(f"/session-clips/lab/{essai['id']}", headers=e["coach"]).json()
    assert detail["status"] == "ready"
    assert [s["kind"] for s in detail["signs"]] == ["fists_touch", "handshake", "x", "time"]
    assert all(s["thumb"].startswith("data:image/jpeg;base64,") for s in detail["signs"])
    # Tous les signes cochés : le combat finit avec la poignée de main (10 à 12 s).
    assert [round(f["end"]) for f in detail["fights"]] == [12]

    # Sans la poignée de main, il va jusqu'au X : sans relire la vidéo.
    # (Le « Time ! » à 25 s vient après.)
    r = client.put("/session-clips/lab/signs", json={"signs": ["fists_touch", "x"]}, headers=e["coach"])
    assert r.json()["signs"] == ["fists_touch", "x"] and r.json()["framing"] == "wide"
    detail = client.get(f"/session-clips/lab/{essai['id']}", headers=e["coach"]).json()
    assert len(detail["signs"]) == 4 and [round(f["end"]) for f in detail["fights"]] == [22]
    assert client.get("/session-clips/lab/signs", headers=e["coach"]).json()["signs"] == ["fists_touch", "x"]
    # Ceux du tournage ne bougent pas (Seb, 12/11 : le Labo expérimente).
    assert len(client.get("/session-clips/signs", headers=e["coach"]).json()["signs"]) == 8
    [combat] = detail["fights"]
    assert combat["frame"] is None  # plan large

    # Cadrage serré, 1 s retirée au début et 2 s à la fin (Seb, 12/11).
    reglages = {"signs": ["fists_touch", "x"], "framing": "tight", "start_skip": 1, "end_skip": 2, "show_timeline": True}
    assert client.put("/session-clips/lab/signs", json=reglages, headers=e["coach"]).json() == reglages
    [serre] = client.get(f"/session-clips/lab/{essai['id']}", headers=e["coach"]).json()["fights"]
    assert serre["start"] == pytest.approx(combat["start"] + 1) and serre["end"] == pytest.approx(combat["end"] - 2)
    t, x, y, w, h = serre["frame"][0]
    assert t == 0 and 0 < w < 1 and h == pytest.approx(w)  # au format de la vidéo, plus petit qu'elle
    assert 0 <= x <= 1 - w and 0 <= y <= 1 - h
    assert client.put("/session-clips/lab/signs", json={**reglages, "framing": "zoom"}, headers=e["coach"]).status_code == 400
    assert client.put("/session-clips/lab/signs", json={**reglages, "end_skip": 60}, headers=e["coach"]).status_code == 400
    assert client.put("/session-clips/lab/signs", json={"signs": ["salto"]}, headers=e["coach"]).status_code == 400
    # La frise des séances, cochée par défaut, se décoche dans Paramètres de tournage (Seb, 13/11).
    assert client.get("/session-clips/signs", headers=e["coach"]).json()["show_timeline"] is True
    r = client.put("/session-clips/signs", json={"signs": ["go"], "show_timeline": False}, headers=e["coach"])
    assert r.json()["show_timeline"] is False

    # Le crayon : renommer l'essai.
    r = client.patch(f"/session-clips/lab/{essai['id']}", json={"title": " Jo contre Jac "}, headers=e["coach"])
    assert r.status_code == 200 and r.json()["title"] == "Jo contre Jac"
    assert client.patch(f"/session-clips/lab/{essai['id']}", json={"title": " "}, headers=e["coach"]).status_code == 400
    assert client.patch(f"/session-clips/lab/{essai['id']}", json={"title": "x"}, headers=e["ailleurs"]).status_code == 404

    # « Relancer la découpe » : le lecteur relit les signes sur les postures
    # gardées, avec les règles du jour, et réécoute le son (Seb, 12/11 : une
    # écoute ratée se rattrape sans réimporter la vidéo).
    db_session.refresh(test)
    test.signs = json.dumps([])  # comme lu avec d'autres règles et une écoute ratée
    db_session.commit()
    assert client.post(f"/session-clips/lab/{essai['id']}/reread", headers=e["coach"]).status_code == 204
    db_session.refresh(test)
    assert test.status == "processing" and lab.tests_to_read(db_session) == [test]

    def sans_images(_p):
        raise AssertionError("les images ne sont pas relues")

    assert lab.read_test(db_session, core.session_clips_client, test, sans_images, lambda _p: [25.0]) == 4
    signes = client.get(f"/session-clips/lab/{essai['id']}", headers=e["coach"]).json()["signs"]
    assert [s["kind"] for s in signes] == ["fists_touch", "handshake", "x", "time"]
    assert client.post(f"/session-clips/lab/{essai['id']}/reread", headers=e["ailleurs"]).status_code == 404

    # Réservé aux coachs de l'école.
    assert client.get("/session-clips/lab", headers=e["eleve"]).status_code == 403
    assert client.put("/session-clips/signs", json={"signs": []}, headers=e["eleve"]).status_code == 403
    assert client.get(f"/session-clips/lab/{essai['id']}", headers=e["ailleurs"]).status_code == 404
    assert client.get("/session-clips/lab", headers=e["ailleurs"]).json() == []

    # Supprimer l'essai efface sa vidéo ; rien n'est allé dans les combats.
    video_id = test.video_id
    assert client.delete(f"/session-clips/lab/{essai['id']}", headers=e["coach"]).status_code == 204
    assert client.get("/session-clips/lab", headers=e["coach"]).json() == []
    assert core.session_clips_client.videos.get(db_session, video_id) is None
