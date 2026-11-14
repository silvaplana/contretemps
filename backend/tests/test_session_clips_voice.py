"""Fights › ⋮ › Entraîner l'écoute (Seb, 14/11) : un coach enregistre au
téléphone des « Fight ! », « Hajime ! », « Combat ! » et « Time ! », pour
apprendre ces mots à l'écoute ; chaque école garde les siens."""

import pytest
from test_session_clips_lab import e  # noqa: F401  (fixture)

pytestmark = pytest.mark.rbac_reel


def test_enregistrer_les_mots(client, e, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    son = {"Content-Type": "audio/webm"}
    vide = {"fight": [], "hajime": [], "combat": [], "time": []}
    assert client.get("/session-clips/voice", headers=e["coach"]).json() == vide
    assert client.get("/session-clips/voice", headers=e["eleve"]).status_code == 403

    r = client.post("/session-clips/voice/hajime", content=b"webm", headers=e["coach"] | son)
    assert r.status_code == 201
    [nom] = r.json()["hajime"]
    assert client.post("/session-clips/voice/allez", content=b"webm", headers=e["coach"] | son).status_code == 400
    assert client.post("/session-clips/voice/time", content=b"", headers=e["coach"] | son).status_code == 400
    assert client.post("/session-clips/voice/time", content=b"x", headers=e["eleve"] | son).status_code == 403

    lu = client.get(f"/session-clips/voice/hajime/{nom}", headers=e["coach"])
    assert lu.status_code == 200 and lu.content == b"webm"
    # Étanche : une autre école ne voit ni ne lit les enregistrements.
    assert client.get("/session-clips/voice", headers=e["ailleurs"]).json() == vide
    assert client.get(f"/session-clips/voice/hajime/{nom}", headers=e["ailleurs"]).status_code == 404
    assert client.get("/session-clips/voice/hajime/..%2F..%2Fx", headers=e["coach"]).status_code == 404

    assert client.delete(f"/session-clips/voice/hajime/{nom}", headers=e["coach"]).status_code == 204
    assert client.get("/session-clips/voice", headers=e["coach"]).json() == vide


def test_tester_l_ecoute(client, e, tmp_path, monkeypatch):  # noqa: F811
    """Seb, 14/11 : « Tester » enregistre 10 s, le worker les écoute avec
    l'écoute du club, et la page montre les mots reconnus."""
    from session_clips import voice

    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    son = {"Content-Type": "audio/webm"}
    assert client.post("/session-clips/voice-tests", content=b"x", headers=e["eleve"] | son).status_code == 403
    nom = client.post("/session-clips/voice-tests", content=b"webm", headers=e["coach"] | son).json()["name"]
    assert client.get(f"/session-clips/voice-tests/{nom}", headers=e["coach"]).json() == {"done": False, "words": []}

    entendus = []
    ecoute = lambda path, model: entendus.append((path.name, model)) or [("time", 4.2, 0.91, 25.0)]
    assert voice.hear_tests(ecoute) == 1
    assert voice.hear_tests(ecoute) == 0  # déjà écouté
    assert entendus == [(nom, "club")]
    assert client.get(f"/session-clips/voice-tests/{nom}", headers=e["coach"]).json() == {
        "done": True,
        "words": [{"kind": "time", "t": 4.2, "note": 0.91, "db": 25.0}],
    }
    assert client.get(f"/session-clips/voice-tests/{nom}", headers=e["ailleurs"]).status_code == 404


def test_dire_la_verite_apres_un_test(client, e, tmp_path, monkeypatch):  # noqa: F811
    """Seb, 14/11 : sous chaque mot trouvé, Bon, Mauvais ou Inventé. Le cri
    (2 s autour) est rangé comme exemple du mot, du bon mot, d'un autre mot
    ou de « rien » ; seuls les mots comptent dans la page."""
    import subprocess

    import imageio_ffmpeg

    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    son = tmp_path / "son.webm"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=10", str(son)],
        check=True,
    )
    nom = client.post("/session-clips/voice-tests", content=son.read_bytes(), headers=e["coach"] | {"Content-Type": "audio/webm"}).json()["name"]
    url = f"/session-clips/voice-tests/{nom}/answer"
    assert client.post(url, json={"t": 4.2, "answer": "good", "word": "time"}, headers=e["eleve"]).status_code == 403
    assert client.post(url, json={"t": 4.2, "answer": "good", "word": "time"}, headers=e["coach"]).status_code == 204
    assert client.post(url, json={"t": 6.0, "answer": "wrong", "word": "hajime"}, headers=e["coach"]).status_code == 204
    assert client.post(url, json={"t": 7.0, "answer": "wrong", "word": "other"}, headers=e["coach"]).status_code == 204
    assert client.post(url, json={"t": 8.0, "answer": "invented"}, headers=e["coach"]).status_code == 204
    assert client.post(url, json={"t": 8.0, "answer": "peut-être"}, headers=e["coach"]).status_code == 400
    assert client.post(url, json={"t": 8.0, "answer": "good", "word": "allez"}, headers=e["coach"]).status_code == 400

    mots = client.get("/session-clips/voice", headers=e["coach"]).json()
    assert {m: len(n) for m, n in mots.items()} == {"fight": 0, "hajime": 1, "combat": 0, "time": 1}
    dossier = tmp_path / str(e["ecole"].id) / "voice"
    assert len(list((dossier / "other").glob("*.wav"))) == 1 and len(list((dossier / "noise").glob("*.wav"))) == 1
    # Le cri gardé : 2 s autour du moment trouvé, lisible comme un enregistrement.
    [time] = mots["time"]
    assert client.get(f"/session-clips/voice/time/{time}", headers=e["coach"]).content[:4] == b"RIFF"


def test_points_d_un_essai():
    """Seb, 14/11 : +1 bon mot, −1 mauvais mot, −2 mot inventé, −1 mot oublié."""
    from session_clips.voice import score

    verite = [
        {"t": 2.0, "word": "time"},  # Bon
        {"t": 5.0, "word": "hajime"},  # Mauvais : c'était Hajime
        {"t": 7.0, "word": None},  # Inventé
        {"t": 8.5, "word": "other"},  # Mauvais : un autre mot
        {"t": None, "word": "fight"},  # Il manque un mot
    ]
    tout_juste = [("time", 2.1), ("hajime", 4.8), ("fight", 9.8)]
    assert score([(k, t, 0.9, 20.0) for k, t in tout_juste], verite) == {
        "good": 3, "wrong": 0, "invented": 0, "missed": 0, "points": 3, "best": 3,
    }
    comme_avant = [("time", 2.0), ("time", 5.0), ("go", 7.0), ("time", 8.5)]
    assert score([(k, t, 0.9, 20.0) for k, t in comme_avant], verite) == {
        "good": 1, "wrong": 2, "invented": 1, "missed": 1, "points": 1 - 2 - 2 - 1, "best": 3,
    }


def test_rejouer_tous_les_essais(client, e, tmp_path, monkeypatch):  # noqa: F811
    """Seb, 14/11 : « Rejouer tous les essais » réécoute les tests répondus,
    sans les exemples venus du test rejoué, et garde l'historique des points."""
    import subprocess

    import imageio_ffmpeg

    from session_clips import voice

    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    son = tmp_path / "son.webm"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=10", str(son)],
        check=True,
    )
    entete = e["coach"] | {"Content-Type": "audio/webm"}
    repondu = client.post("/session-clips/voice-tests", content=son.read_bytes(), headers=entete).json()["name"]
    client.post("/session-clips/voice-tests", content=son.read_bytes(), headers=entete)  # sans réponse : pas compté
    client.post(f"/session-clips/voice-tests/{repondu}/answer", json={"t": 2.0, "answer": "good", "word": "time"}, headers=e["coach"])
    assert client.post(f"/session-clips/voice-tests/{repondu}/missing", json={"word": "fight"}, headers=e["coach"]).status_code == 204
    assert client.post(f"/session-clips/voice-tests/{repondu}/missing", json={"word": "allez"}, headers=e["coach"]).status_code == 400

    assert client.post("/session-clips/voice-replays", headers=e["eleve"]).status_code == 403
    assert client.post("/session-clips/voice-replays", headers=e["coach"]).status_code == 201
    [attente] = client.get("/session-clips/voice-replays", headers=e["coach"]).json()
    assert attente["done"] is False

    rejoues = []

    def ecoute(path, exclude):
        rejoues.append((path.name, exclude))
        return [("time", 2.2, 0.9, 20.0)]

    assert voice.run_replays(ecoute) == 1
    assert voice.run_replays(ecoute) == 0
    [(nom, sans)] = rejoues
    [exemple] = client.get("/session-clips/voice", headers=e["coach"]).json()["time"]
    assert nom == repondu and sans == frozenset({f"time/{exemple}"})
    [fait] = client.get("/session-clips/voice-replays", headers=e["coach"]).json()
    assert fait["done"] and fait["tests"] == 1 and fait["examples"] == 1
    assert (fait["points"], fait["best"], fait["good"], fait["missed"]) == (0, 2, 1, 1)
    assert client.get("/session-clips/voice-replays", headers=e["ailleurs"]).json() == []
