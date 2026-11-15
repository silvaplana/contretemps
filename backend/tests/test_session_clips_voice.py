"""Fights › ⋮ › Entraîner l'écoute (Seb, 14/11) : un coach enregistre au
téléphone des « Fight ! », « Hajime ! », « Combat ! » et « Time ! », pour
apprendre ces mots à l'écoute ; chaque école garde les siens."""

import pytest
from test_session_clips_lab import e  # noqa: F401  (fixture)

pytestmark = pytest.mark.rbac_reel


def test_enregistrer_les_mots(client, e, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    son = {"Content-Type": "audio/webm"}
    vide = {"hajime": [], "combattez": [], "time": []}
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
    assert {m: len(n) for m, n in mots.items()} == {"hajime": 1, "combattez": 0, "time": 1}
    dossier = tmp_path / str(e["ecole"].id) / "voice"
    assert len(list((dossier / "other").glob("*.wav"))) == 1 and len(list((dossier / "noise").glob("*.wav"))) == 1
    # Le cri gardé : 2 s autour du moment trouvé, lisible comme un enregistrement.
    [time] = mots["time"]
    assert client.get(f"/session-clips/voice/time/{time}", headers=e["coach"]).content[:4] == b"RIFF"


def test_points_d_un_essai():
    """Seb, 14/11 : +1 bon mot, −1 mauvais mot, −2 mot inventé, −1 mot
    oublié ; et le détail mot par mot (étude du 14/11)."""
    from session_clips.voice import score

    verite = [
        {"t": 2.0, "word": "time"},  # Bon
        {"t": 5.0, "word": "hajime"},  # Mauvais : c'était Hajime
        {"t": 7.0, "word": None},  # Inventé
        {"t": 8.5, "word": "other"},  # Mauvais : un autre mot
        {"t": None, "word": "combattez"},  # Il manque un mot
    ]
    tout_juste = [("time", 2.1), ("hajime", 4.8), ("combattez", 9.8)]
    juste = score([(k, t, 0.9, 20.0) for k, t in tout_juste], verite)
    assert {k: v for k, v in juste.items() if k != "words"} == {
        "good": 3, "wrong": 0, "invented": 0, "missed": 0, "points": 3, "best": 3,
    }
    assert [juste["words"][w]["good"] for w in ("hajime", "combattez", "time")] == [1, 1, 1]
    comme_avant = [("time", 2.0), ("time", 5.0), ("go", 7.0), ("time", 8.5)]
    faux = score([(k, t, 0.9, 20.0) for k, t in comme_avant], verite)
    assert {k: v for k, v in faux.items() if k != "words"} == {
        "good": 1, "wrong": 2, "invented": 1, "missed": 1, "points": 1 - 2 - 2 - 1, "best": 3,
    }
    assert faux["words"] == {
        "hajime": {"good": 0, "missed": 0, "invented": 0, "wrong": 0, "heard_as": {"time": 1}},
        "combattez": {"good": 0, "missed": 1, "invented": 0, "wrong": 0, "heard_as": {}},
        "time": {"good": 1, "missed": 0, "invented": 0, "wrong": 2, "heard_as": {}},
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
    assert client.post(f"/session-clips/voice-tests/{repondu}/missing", json={"word": "combattez"}, headers=e["coach"]).status_code == 204
    assert client.post(f"/session-clips/voice-tests/{repondu}/missing", json={"word": "fight"}, headers=e["coach"]).status_code == 400

    assert client.post("/session-clips/voice-replays", headers=e["eleve"]).status_code == 403
    assert client.post("/session-clips/voice-replays", headers=e["coach"]).status_code == 201
    [attente] = client.get("/session-clips/voice-replays", headers=e["coach"]).json()
    assert attente["done"] is False

    rejoues = []

    def ecoute(path, exclude):
        rejoues.append((path.name, exclude))
        # Avant le seuil : (mot, moment, ressemblance, avance sur le 2e, volume).
        return [("time", 2.2, 0.9, 0.5, 20.0), ("hajime", 6.0, 0.1, 0.0, 15.0)]

    assert voice.run_replays(ecoute) == 1
    assert voice.run_replays(ecoute) == 0
    [(nom, sans)] = rejoues
    [exemple] = client.get("/session-clips/voice", headers=e["coach"]).json()["time"]
    assert nom == repondu and sans == frozenset({f"time/{exemple}"})
    [fait] = client.get("/session-clips/voice-replays", headers=e["coach"]).json()
    assert fait["done"] and fait["tests"] == 1 and fait["examples"] == 1
    assert (fait["points"], fait["best"], fait["good"], fait["missed"]) == (0, 2, 1, 1)
    assert fait["words"]["time"]["good"] == 1 and fait["words"]["combattez"]["missed"] == 1
    # Le rejeu règle le seuil (étude du 14/11) : le « hajime » inventé à 0,1 est écarté,
    # et l'écoute du club prend ce réglage ensuite.
    assert fait["invented"] == 0 and fait["min_score"] > 0.1
    import json

    [ecole] = [p for p in tmp_path.iterdir() if (p / "voice-replays").is_dir()]
    assert json.loads((ecole / "voice-replays" / "thresholds.json").read_text())["min_score"] == fait["min_score"]
    assert len(client.get("/session-clips/voice-replays", headers=e["coach"]).json()) == 1
    assert client.get("/session-clips/voice-replays", headers=e["ailleurs"]).json() == []


def test_retrouver_les_reponses_d_avant(client, e, tmp_path, monkeypatch):  # noqa: F811
    """Seb, 14/11 : les réponses données avant que la vérité soit gardée ne
    comptaient pas. Chaque exemple est 2 s coupées dans un test : on le
    retrouve dans le test et on reconstruit la réponse."""
    import json
    import subprocess

    import imageio_ffmpeg

    from session_clips import voice
    from session_clips.hearing import _audio

    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    son = tmp_path / "son.webm"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anoisesrc=d=10:c=pink:seed=3", str(son)],
        check=True,
    )
    entete = e["coach"] | {"Content-Type": "audio/webm"}
    nom = client.post("/session-clips/voice-tests", content=son.read_bytes(), headers=entete).json()["name"]
    url = f"/session-clips/voice-tests/{nom}/answer"
    client.post(url, json={"t": 3.0, "answer": "good", "word": "time"}, headers=e["coach"])
    client.post(url, json={"t": 7.0, "answer": "invented"}, headers=e["coach"])
    verite = tmp_path / str(e["ecole"].id) / "voice-tests" / nom.replace(".webm", ".truth.json")
    attendu = json.loads(verite.read_text())
    verite.unlink()  # comme avant la mise en ligne de la vérité

    assert voice.recover_truths(_audio) == 2
    assert voice.recover_truths(_audio) == 0  # déjà retrouvées
    retrouve = sorted(json.loads(verite.read_text()), key=lambda x: x["t"])
    assert [(x["word"], x["example"]) for x in retrouve] == [(x["word"], x["example"]) for x in attendu]
    assert [round(x["t"], 1) for x in retrouve] == [3.0, 7.0]


def test_effacer_les_enregistrements_ou_les_tests(client, e, tmp_path, monkeypatch):  # noqa: F811
    """Seb, 14/11 : deux boutons. « Effacer les enregistrements » efface les
    cris (et les exemples rangés après un test), « Effacer les tests » les
    tests, leurs réponses et les points ; seulement ceux de l'école."""
    import time

    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    son = {"Content-Type": "audio/webm"}
    vide = {"hajime": [], "combattez": [], "time": []}
    client.post("/session-clips/voice/time", content=b"webm", headers=e["coach"] | son)
    test = client.post("/session-clips/voice-tests", content=b"webm", headers=e["coach"] | son).json()["name"]
    client.post("/session-clips/voice-replays", headers=e["coach"])
    ecole = next(p for p in tmp_path.iterdir() if (p / "voice").is_dir())
    (ecole / "voice" / "noise").mkdir()
    (ecole / "voice" / "noise" / "x.wav").write_bytes(b"wav")
    autre = tmp_path / "autre-ecole"
    for dossier in ("voice/time", "voice-tests"):
        (autre / dossier).mkdir(parents=True)
        (autre / dossier / "y.webm").write_bytes(b"webm")
    avant = time.time() - 1

    assert client.delete("/session-clips/voice", headers=e["eleve"]).status_code == 403
    assert client.delete("/session-clips/voice-tests", headers=e["eleve"]).status_code == 403

    assert client.delete("/session-clips/voice", headers=e["coach"]).status_code == 204
    assert client.get("/session-clips/voice", headers=e["coach"]).json() == vide
    assert not any((ecole / "voice").iterdir())
    # Le dossier vide reste, daté de maintenant : voice.newest() fait réécouter les morceaux.
    assert (ecole / "voice").stat().st_mtime >= avant
    assert client.get(f"/session-clips/voice-tests/{test}", headers=e["coach"]).status_code == 200  # les tests restent

    client.post("/session-clips/voice/time", content=b"webm", headers=e["coach"] | son)
    assert client.delete("/session-clips/voice-tests", headers=e["coach"]).status_code == 204
    assert client.get(f"/session-clips/voice-tests/{test}", headers=e["coach"]).status_code == 404
    assert client.get("/session-clips/voice-replays", headers=e["coach"]).json() == []
    assert len(client.get("/session-clips/voice", headers=e["coach"]).json()["time"]) == 1  # les cris restent

    assert (autre / "voice/time/y.webm").exists() and (autre / "voice-tests/y.webm").exists()


def test_noter_les_cris_d_une_seance(client, e, db_session, tmp_path, monkeypatch):  # noqa: F811
    """Étude du 14/11 : noter Bon / Mauvais / Inventé / Il manque un mot sur
    les cris d'une vraie séance filmée ; le rejeu la compte comme un test,
    ses cris remis à l'heure de la séance."""
    import datetime as dt
    import subprocess

    import imageio_ffmpeg

    from app.main import core
    from session_clips import voice
    from session_clips.models import ClipSession
    from videos.stockage import chemin_relatif, dossier_ecole

    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    ecole = e["ecole"].id
    fichier = dossier_ecole(ecole) / "seance.mp4"
    fichier.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "sine=f=440:d=20",
         "-f", "lavfi", "-i", "testsrc=s=160x90:d=20:r=5", "-shortest", "-pix_fmt", "yuv420p", str(fichier)],
        check=True,
    )
    from comptes import Comptes

    coach_id = Comptes().create(db_session, ecole_id=ecole, role="professeur", nom="Martin", prenom="Léa").id
    raw = core.videos_client.create(
        db_session, ecole_id=ecole, nom="Séance", lien_fichier=chemin_relatif(ecole, fichier.name), uploaded_by=coach_id
    )
    raw.duree_secondes = 20
    seance = ClipSession(org_id=ecole, title="Adultes", held_on=dt.date(2026, 11, 16), raw_video_id=raw.id, created_by=coach_id)
    db_session.add(seance)
    db_session.commit()
    url = f"/session-clips/sessions/{seance.id}/voice-notes"

    assert client.get(url, headers=e["coach"]).json() == []
    assert client.post(url, json={"t": 3.0, "answer": "good", "word": "time"}, headers=e["eleve"]).status_code == 403
    assert client.post(url, json={"t": 3.0, "answer": "good", "word": "time"}, headers=e["ailleurs"]).status_code == 404
    assert client.post(url, json={"t": 3.0, "answer": "good", "word": "time"}, headers=e["coach"]).status_code == 201
    assert client.post(url, json={"t": 9.0, "answer": "invented"}, headers=e["coach"]).status_code == 201
    assert client.post(url, json={"t": 14.0, "answer": "missing", "word": "hajime"}, headers=e["coach"]).status_code == 201
    assert client.post(url, json={"t": 14.0, "answer": "missing", "word": "fight"}, headers=e["coach"]).status_code == 400
    assert client.post(url, json={"t": 99.0, "answer": "invented"}, headers=e["coach"]).status_code == 404
    notes = client.get(url, headers=e["coach"]).json()
    assert [(n["t"], n["word"]) for n in notes] == [(3.0, "time"), (9.0, None), (14.0, "hajime")]
    mots = client.get("/session-clips/voice", headers=e["coach"]).json()
    assert (len(mots["time"]), len(mots["hajime"])) == (1, 1)  # rangés comme exemples

    # Une note mise par erreur se retire (Seb, 15/11 : un « Time » de trop à 38 s),
    # avec l'exemple qui en venait.
    assert client.post(url, json={"t": 17.0, "answer": "missing", "word": "time"}, headers=e["coach"]).status_code == 201
    assert len(client.get("/session-clips/voice", headers=e["coach"]).json()["time"]) == 2
    assert client.delete(f"{url}?t=17.0", headers=e["eleve"]).status_code == 403
    assert client.delete(f"{url}?t=12.0", headers=e["coach"]).status_code == 404
    assert client.delete(f"{url}?t=17.0", headers=e["coach"]).json() == notes
    assert len(client.get("/session-clips/voice", headers=e["coach"]).json()["time"]) == 1

    client.post("/session-clips/voice-replays", headers=e["coach"])
    ecoutes = []

    def ecoute(path, exclude):
        ecoutes.append((path, exclude))
        return [("time", 3.1, 0.9, 0.5, 20.0), ("time", 9.0, 0.8, 0.5, 20.0), ("hajime", 14.2, 0.9, 0.5, 20.0)]

    assert voice.run_replays(ecoute) == 1
    [(chemin, sans)] = ecoutes
    assert chemin == fichier and sans == frozenset(n["example"] for n in notes)
    [fait] = client.get("/session-clips/voice-replays", headers=e["coach"]).json()
    assert (fait["tests"], fait["good"], fait["missed"], fait["best"]) == (1, 2, 0, 2)
    assert fait["invented"] == 0  # le « time » à 9 s écarté par le réglage (0,8 < seuil trouvé)

    # « Effacer tous les tests » efface aussi les séances notées.
    client.delete("/session-clips/voice-tests", headers=e["coach"])
    assert client.get(url, headers=e["coach"]).json() == []
