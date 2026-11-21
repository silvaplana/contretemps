"""Timer étendu (Seb, 21/11) : le choix du combattant (★ habitués du jour) et
l'annonce du vainqueur par la voix de George."""

from datetime import date, timedelta

import pytest
from conftest import entetes_session

from app.main import core, videos_client
from comptes import Comptes
from ecoles import Ecoles
from session_clips import announcer
from session_clips.models import ClipSession

pytestmark = pytest.mark.rbac_reel


@pytest.fixture()
def e(db_session):
    comptes = Comptes()
    ecole = Ecoles().create(db_session, nom="Fight Lab", code_postal="13600")
    autre = Ecoles().create(db_session, nom="Autre club", code_postal="13000")

    def compte(role, prenom, nom, ecole_id=ecole.id):
        return comptes.create(db_session, ecole_id=ecole_id, role=role, nom=nom, prenom=prenom)

    d = {
        "ecole": ecole,
        "coach": compte("professeur", "Flo", "Durand"),
        "seb": compte("eleve", "Seb", "Richard"),
        "karim": compte("eleve", "Karim", "Benali"),
        "lucas": compte("eleve", "Lucas", "Martin"),
        "ailleurs": compte("eleve", "Paul", "Ailleurs", autre.id),
    }
    d["h"] = {k: entetes_session(v) for k, v in d.items() if k in ("coach", "seb")}
    return d


def test_noms_du_timer_habitues_en_tete(client, db_session, e):
    jour = date.today() - timedelta(days=7)
    seance = ClipSession(org_id=e["ecole"].id, held_on=jour, status="ready", created_by=e["coach"].id)
    db_session.add(seance)
    db_session.flush()
    video = videos_client.create(db_session, ecole_id=e["ecole"].id, nom="c", lien_fichier="c.mp4", uploaded_by=1)
    core.session_clips_client.add_clip(db_session, seance.id, video.id, [e["lucas"].id, e["seb"].id])

    r = client.get("/session-clips/timer/names", headers=e["h"]["coach"])
    assert r.status_code == 200, r.text
    noms = [(p["name"], p["regular"]) for p in r.json()]
    assert noms[:2] == [("Lucas M.", True), ("Seb R.", True)]
    assert ("Karim B.", False) in noms and all(n != "Paul A." for n, _ in noms)
    assert client.get("/session-clips/timer/names", headers=e["h"]["seb"]).status_code == 403


def test_annonce_du_vainqueur(client, e, monkeypatch, tmp_path):
    dits = []

    def speak(texte, cible):
        dits.append(texte)
        cible.write_bytes(b"ID3 mp3")

    monkeypatch.setattr(announcer, "speak", speak)
    monkeypatch.setattr(announcer, "dossier_ecole", lambda org: tmp_path / str(org))
    url = f"/session-clips/timer/announce/{e['karim'].id}"
    r = client.get(url, headers=e["h"]["coach"])
    assert r.status_code == 200 and r.content == b"ID3 mp3" and r.headers["content-type"] == "audio/mpeg"
    assert dits == ["Karim Benali!"]
    # Gardé : pas refait au deuxième appel.
    client.get(url, headers=e["h"]["coach"])
    assert dits == ["Karim Benali!"]
    # Les écoles sont étanches ; réservé aux coachs.
    assert client.get(f"/session-clips/timer/announce/{e['ailleurs'].id}", headers=e["h"]["coach"]).status_code == 404
    assert client.get(url, headers=e["h"]["seb"]).status_code == 403


def test_voix_indisponible(client, e, monkeypatch, tmp_path):
    def speak(texte, cible):
        raise announcer.VoiceUnavailable("Voix indisponible")

    monkeypatch.setattr(announcer, "speak", speak)
    monkeypatch.setattr(announcer, "dossier_ecole", lambda org: tmp_path / str(org))
    assert client.get(f"/session-clips/timer/announce/{e['karim'].id}", headers=e["h"]["coach"]).status_code == 503
