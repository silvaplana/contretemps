"""Module Sparring (session_clips, spec/modules/video-combats.md §6) :
séance envoyée à la main, clips rangés par la découpe, « Mes combats »,
« À vérifier », noms, droits et étanchéité entre écoles — avec les vraies
vérifications de session (`rbac_reel`)."""

import pytest
from conftest import entetes_session

from app.main import core, videos_client
from app.modules import MODULES
from comptes import Comptes
from ecoles import Ecoles
from registry.activation import set_enabled
from session_clips.models import Clip
from videos.models import Video

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def e(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Fight Lab", code_postal="13600")

    def compte(role, prenom, nom):
        return comptes.create(db_session, ecole_id=ecole.id, role=role, nom=nom, prenom=prenom)

    d = {
        "ecole": ecole,
        "coach": compte("professeur", "Flo", "Durand"),
        "seb": compte("eleve", "Seb", "Richard"),
        "karim": compte("eleve", "Karim", "Benali"),
        "lucas": compte("eleve", "Lucas", "Martin"),
    }
    d["h"] = {k: entetes_session(v) for k, v in d.items() if k != "ecole"}
    return d


def _video(db, ecole, nom="clip"):
    return videos_client.create(db, ecole_id=ecole.id, nom=nom, lien_fichier=f"{ecole.id}/{nom}.mp4", uploaded_by=1)


def _session(client, e):
    upload = client.post(
        f"/ecoles/{e['ecole'].id}/videos/televersements",
        json={"extension": ".mp4", "octets_total": 100},
        headers=e["h"]["coach"],
    ).json()["id"]
    r = client.post(
        "/session-clips/sessions",
        json={"upload_id": upload, "title": "Adultes · 19 h", "held_on": "2026-10-23"},
        headers=e["h"]["coach"],
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_seance_envoyee_puis_clips(client, db_session, e):
    seance = _session(client, e)
    # La vidéo arrive encore : l'envoi n'est pas fini.
    assert seance["status"] == "uploading" and seance["clip_count"] == 0

    sc = core.session_clips_client
    seb, karim, lucas = e["seb"].id, e["karim"].id, e["lucas"].id
    sc.add_clip(db_session, seance["id"], _video(db_session, e["ecole"], "a").id, [seb, karim])
    sc.add_clip(db_session, seance["id"], _video(db_session, e["ecole"], "b").id, [lucas, None], check_reason="Pas de Y")
    sc.add_clip(db_session, seance["id"], _video(db_session, e["ecole"], "c").id, [karim, seb])
    sc.set_attendees(db_session, seance["id"], [seb, karim, lucas])

    detail = client.get(f"/session-clips/sessions/{seance['id']}", headers=e["h"]["coach"]).json()
    assert [c["title"] for c in detail["clips"]] == [
        "Seb R. vs Karim B.",
        "Lucas M. vs ?",
        "Karim B. vs Seb R. 2",
    ]
    assert [c["position"] for c in detail["clips"]] == [1, 2, 3]
    assert detail["clips"][1]["to_check"] and detail["to_check_count"] == 1
    assert [p["name"] for p in detail["attendees"]] == ["Karim B.", "Lucas M.", "Seb R."]
    assert len(detail["previews"]) == 3

    # Mes combats : les clips validés où Seb apparaît.
    mine = client.get("/session-clips/mine", headers=e["h"]["seb"]).json()
    assert [c["title"] for c in mine] == ["Seb R. vs Karim B.", "Karim B. vs Seb R. 2"]
    # Lucas : son clip attend un coach, il ne le voit pas encore.
    assert client.get("/session-clips/mine", headers=e["h"]["lucas"]).json() == []


def test_verifier_inverser_nommer_valider(client, db_session, e):
    seance = _session(client, e)
    sc = core.session_clips_client
    clip = sc.add_clip(db_session, seance["id"], _video(db_session, e["ecole"]).id, [e["lucas"].id, None], check_reason="Pas de Y")
    h = e["h"]["coach"]

    file = client.get("/session-clips/to-check", headers=h).json()
    assert [c["id"] for c in file] == [clip.id] and file[0]["check_reason"] == "Pas de Y"

    # Tant qu'il manque un nom, « C'est bon » est refusé.
    assert client.post(f"/session-clips/clips/{clip.id}/validate", headers=h).status_code == 400
    r = client.put(f"/session-clips/clips/{clip.id}/participants", json={"people": [e["karim"].id, e["lucas"].id]}, headers=h)
    assert r.status_code == 200 and r.json()["title"] == "Karim B. vs Lucas M."
    # Le nombre de places ne change pas.
    assert client.put(f"/session-clips/clips/{clip.id}/participants", json={"people": [e["karim"].id]}, headers=h).status_code == 400

    assert client.post(f"/session-clips/clips/{clip.id}/validate", headers=h).status_code == 200
    assert client.get("/session-clips/to-check", headers=h).json() == []
    assert [c["id"] for c in client.get("/session-clips/mine", headers=e["h"]["lucas"]).json()] == [clip.id]


def test_combattant_inconnu(client, db_session, e):
    """Un combattant qui n'est pas du club (Seb, 17/11) : « Inconnu », le
    combat se valide et part dans « Mes combats » de l'autre."""
    seance = _session(client, e)
    clip = core.session_clips_client.add_clip(db_session, seance["id"], _video(db_session, e["ecole"]).id, [None, None])
    h = e["h"]["coach"]
    r = client.put(f"/session-clips/clips/{clip.id}/participants", json={"people": [e["karim"].id, "outsider"]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Karim B. vs Inconnu"
    assert r.json()["participants"][1] == {"person_id": None, "name": "Inconnu", "outsider": True, "winner": False}
    assert client.post(f"/session-clips/clips/{clip.id}/validate", headers=h).status_code == 200
    assert [c["title"] for c in client.get("/session-clips/mine", headers=e["h"]["karim"]).json()] == ["Karim B. vs Inconnu"]
    # Le remettre à « pas encore nommé ».
    r = client.put(f"/session-clips/clips/{clip.id}/participants", json={"people": [e["karim"].id, None]}, headers=h)
    assert r.json()["participants"][1] == {"person_id": None, "name": None, "outsider": False, "winner": False}


def test_supprimer_un_clip_efface_sa_video(client, db_session, e):
    seance = _session(client, e)
    video_id = _video(db_session, e["ecole"]).id
    clip_id = core.session_clips_client.add_clip(db_session, seance["id"], video_id, [e["seb"].id, e["karim"].id]).id
    assert client.delete(f"/session-clips/clips/{clip_id}", headers=e["h"]["seb"]).status_code == 403
    assert client.delete(f"/session-clips/clips/{clip_id}", headers=e["h"]["coach"]).status_code == 204
    db_session.expire_all()
    assert videos_client.get(db_session, video_id) is None
    assert client.get(f"/session-clips/clips/{clip_id}", headers=e["h"]["coach"]).status_code == 404


def test_droits_et_etancheite(client, db_session, e):
    seance = _session(client, e)
    clip = core.session_clips_client.add_clip(db_session, seance["id"], _video(db_session, e["ecole"]).id, [e["seb"].id, e["karim"].id])

    # Les séances, la file et les corrections : coachs seulement.
    for route in ("/session-clips/sessions", "/session-clips/to-check", "/session-clips/people", f"/session-clips/sessions/{seance['id']}"):
        assert client.get(route, headers=e["h"]["seb"]).status_code == 403
    assert client.put(f"/session-clips/clips/{clip.id}/participants", json={"people": [e["karim"].id, e["seb"].id]}, headers=e["h"]["seb"]).status_code == 403
    # Un membre lit ses clips, pas ceux des autres.
    assert client.get(f"/session-clips/clips/{clip.id}", headers=e["h"]["seb"]).status_code == 200
    assert client.get(f"/session-clips/clips/{clip.id}", headers=e["h"]["lucas"]).status_code == 404
    assert client.get("/session-clips/mine").status_code == 401
    assert client.get("/session-clips/me", headers=e["h"]["seb"]).json() == {"person_id": e["seb"].id, "is_coach": False}
    assert client.get("/session-clips/me", headers=e["h"]["coach"]).json()["is_coach"] is True

    # Une autre école ne voit rien, et ne nomme pas avec nos membres.
    autre = Ecoles().create(db_session, nom="Autre", code_postal="11111")
    etranger = entetes_session(Comptes().create(db_session, ecole_id=autre.id, role="admin", nom="X", prenom="Y"))
    assert client.get("/session-clips/sessions", headers=etranger).json() == []
    assert client.get(f"/session-clips/sessions/{seance['id']}", headers=etranger).status_code == 404
    assert client.get(f"/session-clips/clips/{clip.id}", headers=etranger).status_code == 404
    outsider = Comptes().create(db_session, ecole_id=autre.id, role="eleve", nom="Z", prenom="Z")
    r = client.put(f"/session-clips/clips/{clip.id}/participants", json={"people": [outsider.id, e["seb"].id]}, headers=e["h"]["coach"])
    assert r.status_code == 400


def test_module_eteint_routes_introuvables(client, db_session, e):
    set_enabled(db_session, e["ecole"].id, MODULES, "session_clips", False)
    assert client.get("/session-clips/mine", headers=e["h"]["seb"]).status_code == 404


def test_filmer_un_combat(client, db_session, e):
    """Le + : un combat filmé à la main, gardé puis nommé, va tout de suite
    dans « Mes combats » ; les combats du jour sont rangés dans une séance."""
    h = e["h"]["coach"]

    def filmer(people):
        upload = client.post(
            f"/ecoles/{e['ecole'].id}/videos/televersements",
            json={"extension": ".mp4", "octets_total": 100},
            headers=h,
        ).json()["id"]
        return upload, client.post("/session-clips/fights", json={"upload_id": upload, "people": people}, headers=h)

    seb, karim = e["seb"].id, e["karim"].id
    upload, r = filmer([seb, karim])
    assert r.status_code == 201, r.text
    premier = r.json()
    assert premier["title"] == "Seb R. vs Karim B." and not premier["to_check"]
    # Double clic sur « C'est bon » : pas de second combat.
    assert client.post("/session-clips/fights", json={"upload_id": upload, "people": [seb, karim]}, headers=h).json()["id"] == premier["id"]
    second = filmer([karim, seb])[1].json()
    assert second["session_id"] == premier["session_id"] and second["position"] == 2

    seances = client.get("/session-clips/sessions", headers=h).json()
    assert len(seances) == 1 and seances[0]["status"] == "ready" and seances[0]["clip_count"] == 2
    mine = client.get("/session-clips/mine", headers=e["h"]["seb"]).json()
    assert [c["title"] for c in mine] == ["Seb R. vs Karim B.", "Karim B. vs Seb R. 2"]

    # Deux combattants différents, coach seulement.
    assert filmer([seb, seb])[1].status_code == 400
    assert client.post("/session-clips/fights", json={"upload_id": upload, "people": [seb, karim]}, headers=e["h"]["seb"]).status_code == 403


def test_combat_du_timer_etendu(client, db_session, e):
    """Timer étendu (Seb, 21/11) : le combat filmé peut partir sans nom (il
    attend alors un coach) et avec son vainqueur."""
    h = e["h"]["coach"]

    def filmer(**corps):
        upload = client.post(
            f"/ecoles/{e['ecole'].id}/videos/televersements",
            json={"extension": ".webm", "octets_total": 100},
            headers=h,
        ).json()["id"]
        return client.post("/session-clips/fights", json={"upload_id": upload, **corps}, headers=h)

    seb, karim = e["seb"].id, e["karim"].id
    r = filmer(people=[seb, karim], winner=1)
    assert r.status_code == 201, r.text
    assert [p["winner"] for p in r.json()["participants"]] == [False, True] and not r.json()["to_check"]
    # Un nom manque : à vérifier, le vainqueur reste sur sa place.
    r = filmer(people=[None, karim], winner=0)
    assert r.status_code == 201, r.text
    assert r.json()["to_check"] and [p["winner"] for p in r.json()["participants"]] == [True, False]
    assert filmer(people=[None, None]).json()["participants"][0]["winner"] is False
    assert filmer(people=[seb, karim], winner=2).status_code == 400
    nul = filmer(people=[seb, karim], draw=True).json()
    assert nul["draw"] and not any(p["winner"] for p in nul["participants"])
    assert filmer(people=[seb, karim], winner=0, draw=True).status_code == 400


def test_incrustation_demandee(client, db_session, e):
    """Incrustation (Seb, 21/11) : la demande est gardée sur le combat avec
    les noms et le résultat ; la vidéo attend l'incrustation au lieu de la
    compression ordinaire (une seule compression)."""
    h = e["h"]["coach"]

    def filmer(**corps):
        upload = client.post(
            f"/ecoles/{e['ecole'].id}/videos/televersements",
            json={"extension": ".webm", "octets_total": 100},
            headers=h,
        ).json()["id"]
        return client.post("/session-clips/fights", json={"upload_id": upload, **corps}, headers=h).json()

    seb, karim = e["seb"].id, e["karim"].id
    demande = {"names": True, "winner": True, "music": "rock", "announce": True, "rounds": 3,
               "phases": [{"t": 0, "n": 1, "total": 180}]}
    r = filmer(people=[seb, None], winner=0, overlay=demande)
    clip = db_session.get(Clip, r["id"])
    assert clip.overlay["music"] == "rock" and clip.overlay["result"] == 0 and clip.overlay["people"] == [seb, None]
    assert clip.overlay["labels"][0] and clip.overlay["labels"][1] is None and clip.overlay["voices"][0]
    assert db_session.get(Video, clip.video_id).compresse is True
    assert filmer(people=[seb, karim], draw=True, overlay=demande)["id"]
    assert db_session.get(Clip, r["id"] + 1).overlay["result"] == "draw"
    # Rien de coché : la compression ordinaire.
    r = filmer(people=[seb, karim], overlay={"names": False})
    clip = db_session.get(Clip, r["id"])
    assert clip.overlay is None and db_session.get(Video, clip.video_id).compresse is False


def test_incrustation_ratee(client, db_session, e, monkeypatch):
    """Une incrustation qui échoue rend la vidéo à la compression ordinaire :
    elle reste visible, sans incrustation."""
    from session_clips import overlay

    upload = client.post(
        f"/ecoles/{e['ecole'].id}/videos/televersements", json={"extension": ".webm", "octets_total": 100}, headers=e["h"]["coach"]
    ).json()["id"]
    r = client.post(
        "/session-clips/fights",
        json={"upload_id": upload, "people": [e["seb"].id, e["karim"].id], "winner": 1, "overlay": {"winner": True}},
        headers=e["h"]["coach"],
    ).json()
    clip = db_session.get(Clip, r["id"])
    video = db_session.get(Video, clip.video_id)
    monkeypatch.setattr(overlay, "render", lambda *a: False)
    assert overlay.render_pending(db_session, videos_client) == 0 and clip.overlay is not None  # pas encore arrivée
    video.statut, video.lien_fichier = "complete", f"{e['ecole'].id}/combat.webm"
    db_session.commit()
    assert overlay.render_pending(db_session, videos_client) == 0
    db_session.refresh(clip)
    db_session.refresh(video)
    assert clip.overlay is None and video.compresse is False


def test_favoris(client, db_session, e):
    """« ★ Favoris » : propres à chacun, limités aux clips visibles, effacés
    avec le clip."""
    seance = _session(client, e)
    sc = core.session_clips_client
    seb, karim = e["seb"].id, e["karim"].id
    a = sc.add_clip(db_session, seance["id"], _video(db_session, e["ecole"], "a").id, [seb, karim])
    b = sc.add_clip(db_session, seance["id"], _video(db_session, e["ecole"], "b").id, [karim, None], check_reason="?")

    def mettre(qui, clip, oui=True):
        return client.put(f"/session-clips/clips/{clip.id}/favorite", json={"favorite": oui}, headers=e["h"][qui])

    assert mettre("seb", a).json()["favorite"] is True
    assert [c["id"] for c in client.get("/session-clips/favorites", headers=e["h"]["seb"]).json()] == [a.id]
    # Les favoris de Seb ne sont pas ceux du coach.
    assert client.get("/session-clips/favorites", headers=e["h"]["coach"]).json() == []
    assert client.get(f"/session-clips/clips/{a.id}", headers=e["h"]["coach"]).json()["favorite"] is False
    # Un clip qu'on ne voit pas ne se met pas en favori.
    assert mettre("lucas", a).status_code == 404 and mettre("seb", b).status_code == 404
    assert mettre("seb", a, False).json()["favorite"] is False
    assert client.get("/session-clips/favorites", headers=e["h"]["seb"]).json() == []

    mettre("coach", a)
    assert client.delete(f"/session-clips/clips/{a.id}", headers=e["h"]["coach"]).status_code == 204
    assert client.get("/session-clips/favorites", headers=e["h"]["coach"]).json() == []


def test_nouveaux_combats(client, db_session, e, monkeypatch):
    """Seb, 17/11 : une pastille sur Fights pour les combats validés pas
    encore regardés ; ouvrir le combat l'enlève. Et une notification sur le
    téléphone de chaque combattant quand le combat est validé."""
    seance = _session(client, e)
    sc = core.session_clips_client
    envois = []
    monkeypatch.setattr(sc, "notifier", type("N", (), {"notify": lambda self, db, org, people, title, body: envois.append((sorted(people), title, body))})())
    h = e["h"]
    clip = sc.add_clip(db_session, seance["id"], _video(db_session, e["ecole"], "a").id, [e["seb"].id, None])
    # Pas encore validé : rien de nouveau.
    assert client.get("/session-clips/new", headers=h["seb"]).json() == {"count": 0}
    client.put(f"/session-clips/clips/{clip.id}/participants", json={"people": [e["seb"].id, e["karim"].id]}, headers=h["coach"])
    client.post(f"/session-clips/clips/{clip.id}/validate", headers=h["coach"])
    assert envois == [(sorted([e["seb"].id, e["karim"].id]), "Nouveau combat", "Seb R. vs Karim B. : il est dans Fights › Combats.")]
    # Valider encore (sous le crayon) ne renvoie rien.
    client.post(f"/session-clips/clips/{clip.id}/validate", headers=h["coach"])
    assert len(envois) == 1
    assert client.get("/session-clips/new", headers=h["seb"]).json() == {"count": 1}
    assert client.get("/session-clips/new", headers=h["karim"]).json() == {"count": 1}
    assert client.get("/session-clips/new", headers=h["lucas"]).json() == {"count": 0}
    assert [c["new"] for c in client.get("/session-clips/mine", headers=h["seb"]).json()] == [True]
    # Seb l'ouvre : plus nouveau pour lui, toujours pour Karim. Le coach qui
    # l'ouvre ne change rien.
    client.get(f"/session-clips/clips/{clip.id}", headers=h["coach"])
    client.get(f"/session-clips/clips/{clip.id}", headers=h["seb"])
    assert client.get("/session-clips/new", headers=h["seb"]).json() == {"count": 0}
    assert [c["new"] for c in client.get("/session-clips/mine", headers=h["seb"]).json()] == [False]
    assert client.get("/session-clips/new", headers=h["karim"]).json() == {"count": 1}
