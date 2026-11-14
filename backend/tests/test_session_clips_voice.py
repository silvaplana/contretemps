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
