"""Labo de Fights (spec/modules/video-combats.md §6.5 bis) : une vidéo déjà
filmée envoyée par un coach, lue par le worker (détecteur simulé), ses
signes avec une image de chacun, ses combats selon les « Signes et sons du
club », droits et étanchéité."""

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
    x = [pose(100, "x"), pose(300)]
    postures = frames([(1, touch), (9, fight), (2, hand), (8, fight), (2, x), (8, [])])
    test = db_session.get(LabTest, essai["id"])
    assert lab.tests_to_read(db_session) == [test]
    assert lab.read_test(db_session, core.session_clips_client, test, lambda _p: postures, lambda _p: [25.0]) == 4
    assert lab.tests_to_read(db_session) == []

    detail = client.get(f"/session-clips/lab/{essai['id']}", headers=e["coach"]).json()
    assert detail["status"] == "ready"
    assert [s["kind"] for s in detail["signs"]] == ["fists_touch", "handshake", "x", "time"]
    assert all(s["thumb"].startswith("data:image/jpeg;base64,") for s in detail["signs"])
    # Tous les signes cochés : le combat finit à la poignée de main (10 s + 1).
    assert [round(f["end"]) for f in detail["fights"]] == [11]

    # Sans la poignée de main, il va jusqu'au X : sans relire la vidéo.
    # (Le « Time ! » à 25 s vient après.)
    r = client.put("/session-clips/signs", json={"signs": ["fists_touch", "x"]}, headers=e["coach"])
    assert r.json() == {"signs": ["fists_touch", "x"]}
    detail = client.get(f"/session-clips/lab/{essai['id']}", headers=e["coach"]).json()
    assert len(detail["signs"]) == 4 and [round(f["end"]) for f in detail["fights"]] == [21]
    assert client.get("/session-clips/signs", headers=e["coach"]).json() == {"signs": ["fists_touch", "x"]}
    assert client.put("/session-clips/signs", json={"signs": ["salto"]}, headers=e["coach"]).status_code == 400

    # Le crayon : renommer l'essai.
    r = client.patch(f"/session-clips/lab/{essai['id']}", json={"title": " Jo contre Jac "}, headers=e["coach"])
    assert r.status_code == 200 and r.json()["title"] == "Jo contre Jac"
    assert client.patch(f"/session-clips/lab/{essai['id']}", json={"title": " "}, headers=e["coach"]).status_code == 400
    assert client.patch(f"/session-clips/lab/{essai['id']}", json={"title": "x"}, headers=e["ailleurs"]).status_code == 404

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
