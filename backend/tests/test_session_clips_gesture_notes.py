"""Noter les gestes dans la frise d'une séance (Seb, 15/11) : Bon, Mauvais,
Inventé, Il manque un geste ; « Proposer un réglage » essaie chaque durée
minimale d'un geste sur les séances notées, sans rien changer."""

import datetime as dt

import pytest
from test_session_clips_cutting import pose
from test_session_clips_lab import e  # noqa: F401  (fixture)

pytestmark = pytest.mark.rbac_reel


def _morceau(gestes, duree=30.0):
    """Des images à 5/s : poings touchés pendant chaque (début, fin) de `gestes`."""
    from session_clips.signals import Frame

    out = []
    for i in range(int(duree * 5)):
        t = i / 5
        touche = any(a <= t <= b + 1e-6 for a, b in gestes)
        paire = [pose(100, "touch"), pose(260, "touch", wrist_dx=-160)] if touche else [pose(100), pose(260)]
        out.append(Frame(t=t, people=paire))
    return out


def test_noter_les_gestes_et_proposer_un_reglage(client, e, db_session, tmp_path, monkeypatch):  # noqa: F811
    from session_clips.cutting import _poses_path, _save_frames
    from session_clips.models import ClipSession, Piece

    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    from comptes import Comptes

    ecole = e["ecole"].id
    coach_id = Comptes().create(db_session, ecole_id=ecole, role="professeur", nom="Martin", prenom="Léa").id
    seance = ClipSession(org_id=ecole, title="Adultes", held_on=dt.date(2026, 11, 16), status="ready", created_by=coach_id)
    db_session.add(seance)
    db_session.flush()
    # Deux morceaux de 30 s : de vrais poings touchés à 5 s (3 s) et à 40 s
    # (2,4 s), et de faux à 20 s (1,6 s, des poings croisés en plein échange).
    for position, gestes in enumerate([[(5.0, 8.0), (20.0, 21.6)], [(10.0, 12.4)]]):
        morceau = Piece(session_id=seance.id, position=position, upload_id=f"m{position}", duration_seconds=30.0)
        db_session.add(morceau)
        db_session.flush()
        _save_frames(_poses_path(ecole, morceau.id), _morceau(gestes))
    db_session.commit()
    url = f"/session-clips/sessions/{seance.id}/gesture-notes"
    proposer = "/session-clips/signs/proposal"

    assert client.get(url, headers=e["coach"]).json() == []
    assert client.get(proposer, headers=e["coach"]).json()["total"] == 0
    bon = {"t": 5.0, "kind": "fists_touch", "answer": "good"}
    assert client.post(url, json=bon, headers=e["eleve"]).status_code == 403
    assert client.post(url, json=bon, headers=e["ailleurs"]).status_code == 404
    assert client.post(url, json=bon | {"kind": "go"}, headers=e["coach"]).status_code == 400
    assert client.post(url, json=bon, headers=e["coach"]).status_code == 201
    assert client.post(url, json={"t": 20.0, "kind": "fists_touch", "answer": "invented"}, headers=e["coach"]).status_code == 201
    # Oublié avec le réglage du jour ? Non : 2,4 s est tenu ; noté « Il manque » pour l'exemple.
    assert client.post(url, json={"t": 40.0, "kind": "fists_touch", "answer": "missing"}, headers=e["coach"]).status_code == 201
    # Changer d'avis remplace la note au même moment.
    client.post(url, json=bon | {"answer": "wrong", "real": "arms_up"}, headers=e["coach"])
    notes = client.post(url, json=bon, headers=e["coach"]).json()
    assert [(n["t"], n["answer"]) for n in notes] == [(5.0, "good"), (20.0, "invented"), (40.0, "missing")]

    # 1,6 s (le réglage du jour) garde les faux poings touchés de 1,6 s ;
    # 1,7 s les écarte et garde les vrais : la plus proche des meilleures.
    avant = client.get("/session-clips/signs", headers=e["coach"]).json()
    assert client.get(proposer, headers=e["eleve"]).status_code == 403
    assert client.get(proposer, headers=e["coach"]).json() == {
        "total": 3,
        "sessions": 1,
        "current": {"min_hold": 1.6, "right": 2},
        "best": {"min_hold": 1.7, "right": 3},
    }
    assert client.get("/session-clips/signs", headers=e["coach"]).json() == avant  # rien ne change sans « Appliquer »
    assert client.get(proposer, headers=e["ailleurs"]).json()["total"] == 0  # étanche

    # Une note mise par erreur se retire.
    assert client.delete(f"{url}?t=12.0", headers=e["coach"]).status_code == 404
    assert [n["t"] for n in client.delete(f"{url}?t=20.0", headers=e["coach"]).json()] == [5.0, 40.0]
    assert client.get(proposer, headers=e["coach"]).json()["best"] == {"min_hold": 1.6, "right": 2}
