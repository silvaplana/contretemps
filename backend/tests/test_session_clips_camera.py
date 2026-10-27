"""Caméra de la salle de Fights (spec/modules/video-combats.md §4, étape 3) :
jumelage par code, ordres Démarrer / Fin de séance, morceaux de 2 minutes
envoyés par blocs, et découpe au fil des morceaux (détecteur simulé)."""

import subprocess

import imageio_ffmpeg
import pytest
from conftest import entetes_session
from test_session_clips_cutting import frames, pose

from app.main import core
from comptes import Comptes
from ecoles import Ecoles
from session_clips.cutting import REASON_NAMES, cut_live, live_sessions
from session_clips.fights import REASON_NO_END
from session_clips.models import ClipSession

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def e(db_session):
    ecole = Ecoles().create(db_session, nom="Fight Lab", code_postal="13600")
    comptes = Comptes()
    coach = comptes.create(db_session, ecole_id=ecole.id, role="professeur", nom="Durand", prenom="Flo")
    eleve = comptes.create(db_session, ecole_id=ecole.id, role="eleve", nom="Richard", prenom="Seb")
    return {"ecole": ecole, "coach": entetes_session(coach), "eleve": entetes_session(eleve)}


def _jumeler(client, e):
    code = client.post("/session-clips/camera/pairing-code", headers=e["coach"]).json()["pairing_code"]
    r = client.post("/session-clips/recorder/pair", json={"code": code})
    assert r.status_code == 200, r.text
    return {"X-Recorder-Token": r.json()["token"]}


def _battre(client, tel, state="ready"):
    r = client.post("/session-clips/recorder/heartbeat", json={"state": state, "battery_percent": 86, "free_bytes": 41 * 10**9}, headers=tel)
    assert r.status_code == 200, r.text
    return r.json()


def test_jumelage_et_ordres(client, e):
    h = e["coach"]
    assert client.get("/session-clips/camera", headers=h).json()["state"] == "none"
    assert client.get("/session-clips/camera", headers=e["eleve"]).status_code == 403
    pending = client.post("/session-clips/camera/pairing-code", headers=h).json()
    assert len(pending["pairing_code"]) == 8 and not pending["paired"]
    assert client.post("/session-clips/recorder/pair", json={"code": "00000000"}).status_code == 404

    tel = _jumeler(client, e)
    assert client.post("/session-clips/recorder/heartbeat", json={"state": "ready"}, headers={"X-Recorder-Token": "faux"}).status_code == 403
    assert _battre(client, tel) == {"session_id": None, "signal": "beep"}
    cam = client.get("/session-clips/camera", headers=h).json()
    assert cam["state"] == "ready" and cam["battery_percent"] == 86 and cam["pairing_code"] is None

    cam = client.post("/session-clips/camera/start", json={"title": "Adultes · 19 h"}, headers=h).json()
    assert cam["state"] == "recording" and cam["session_title"] == "Adultes · 19 h"
    assert client.put("/session-clips/camera/signal", json={"signal": "both"}, headers=h).status_code == 200
    ordres = _battre(client, tel, "recording")
    assert ordres == {"session_id": cam["session_id"], "signal": "both"}
    seance = client.get("/session-clips/sessions", headers=h).json()[0]
    assert seance["status"] == "recording"

    assert client.post("/session-clips/camera/stop", headers=h).json()["state"] == "recording"  # le téléphone finit son morceau
    assert _battre(client, tel)["session_id"] is None
    assert client.get("/session-clips/camera", headers=h).json()["state"] == "ready"

    # Un nouveau jumelage remplace l'ancien téléphone.
    _jumeler(client, e)
    assert client.post("/session-clips/recorder/heartbeat", json={"state": "ready"}, headers=tel).status_code == 403


def test_arreter_avant_le_premier_morceau(client, e):
    tel = _jumeler(client, e)
    _battre(client, tel)
    client.post("/session-clips/camera/start", json={"title": ""}, headers=e["coach"])
    client.post("/session-clips/camera/stop", headers=e["coach"])
    assert client.get("/session-clips/sessions", headers=e["coach"]).json() == []


def _morceau(tmp_path, n, secondes=30):
    fichier = tmp_path / f"morceau{n}.mp4"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"testsrc=s=640x360:d={secondes}:r=25", "-pix_fmt", "yuv420p", str(fichier)],
        check=True,
    )
    return fichier.read_bytes()


def _envoyer(client, tel, session_id, position, donnees, last=False):
    r = client.post("/session-clips/recorder/pieces", json={"session_id": session_id, "position": position, "size": len(donnees), "last": last}, headers=tel)
    assert r.status_code == 200, r.text
    upload = r.json()["upload_id"]
    moitie = len(donnees) // 2
    for debut, bloc in ((0, donnees[:moitie]), (moitie, donnees[moitie:])):
        r = client.put(f"/session-clips/recorder/pieces/{upload}", content=bloc, headers={**tel, "X-Decalage": str(debut)})
        assert r.status_code == 200, r.text
    assert r.json()["received"] == len(donnees)
    # Reprise après coupure : le même morceau rouvert donne où on en est.
    assert client.post("/session-clips/recorder/pieces", json={"session_id": session_id, "position": position, "size": len(donnees)}, headers=tel).json()["received"] == len(donnees)


def test_decoupe_au_fil_des_morceaux(client, db_session, e, tmp_path, monkeypatch):
    videos_dir = tmp_path / "videos"
    for cible in ("videos.stockage", "session_clips.cutting", "videos.videos"):
        monkeypatch.setattr(f"{cible}.DOSSIER_VIDEOS_LIVE", videos_dir)
    tel = _jumeler(client, e)
    _battre(client, tel)
    sid = client.post("/session-clips/camera/start", json={"title": "Adultes · 19 h"}, headers=e["coach"]).json()["session_id"]
    _battre(client, tel, "recording")

    y2 = [pose(100, "fist"), pose(300, "fist")]
    fight = [pose(100), pose(300)]
    x = [pose(100, "x"), pose(300)]
    # Morceaux de 30 s : combat 1 dans le morceau 0 ; combat 2 à cheval sur
    # 0 et 1 ; combat 3 commencé dans le dernier, sans fin repérée.
    postures = [
        frames([(2, y2), (15, fight), (1, x), (5, []), (2, y2), (5, fight)]),
        frames([(15, fight), (1, x), (14, [])]),
        frames([(2, y2), (28, fight)]),
    ]
    detecteur = lambda _path: postures.pop(0)
    sc = core.session_clips_client
    session = db_session.get(ClipSession, sid)

    _envoyer(client, tel, sid, 0, _morceau(tmp_path, 0))
    assert [s.id for s in live_sessions(db_session)] == [sid]
    assert cut_live(db_session, sc, session, detecteur) == 1
    assert cut_live(db_session, sc, session, detecteur) == 0  # rien de nouveau

    _envoyer(client, tel, sid, 1, _morceau(tmp_path, 1))
    assert cut_live(db_session, sc, session, detecteur) == 1
    client.post("/session-clips/camera/stop", headers=e["coach"])
    _envoyer(client, tel, sid, 2, _morceau(tmp_path, 2), last=True)
    db_session.refresh(session)
    assert cut_live(db_session, sc, session, detecteur) == 1
    assert session.status == "ready" and live_sessions(db_session) == []

    clips = sc.clips_by_session(db_session, [sid])[sid]
    assert [c.position for c in clips] == [1, 2, 3]
    assert [c.check_reason for c in clips] == [REASON_NAMES, REASON_NAMES, REASON_NO_END]
    assert clips[1].start_seconds == pytest.approx(23, abs=0.5)  # 2 + 15 + 1 + 5
    videos = sc.video_map(db_session, [c.video_id for c in clips])
    # Le combat 2 recolle les morceaux 0 et 1 : 2 + 5 + 15 + 1 s et la marge.
    assert 22 <= videos[clips[1].video_id].duree_secondes <= 26
    assert videos[clips[0].video_id].nom == "Fights · " + session.held_on.strftime("%d/%m/%Y") + " · Adultes · 19 h · combat 1"
    seance = client.get(f"/session-clips/sessions/{sid}", headers=e["coach"]).json()
    assert seance["live"] and seance["clip_count"] == 3
