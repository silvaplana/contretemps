"""Qui est qui ? (Seb, 17/11) : les combattants des combats d'une séance
regroupés par personne (tenue, visage), nommés par le coach, et les noms
proposés d'après les autres séances."""

import datetime as dt

import pytest
from test_session_clips import _video, e  # noqa: F401  (fixture)

from app.main import core, videos_client
from session_clips import people
from session_clips.people import Fighter, colour_name, group, outfit_label

pytestmark = pytest.mark.rbac_reel

ROUGE, BLANC, NOIR, BLEU = "#d03030", "#f0f0f0", "#151515", "#2040c0"


def _tenue(haut: int, bas: int, n: int = 8) -> list[float]:
    """Un histogramme de tenue : toute la couleur du haut dans la case
    `haut`, celle du bas dans la case `bas`."""
    h, b = [0.0] * 72, [0.0] * 72
    h[haut], b[bas] = 1.0, 1.0
    return h + b


def _visage(i: int) -> list[float]:
    v = [0.0] * 128
    v[i] = 1.0
    return v


def _combattant(haut, bas, visage=None, couleurs=(ROUGE, NOIR)):
    return Fighter(outfit=_tenue(haut, bas), face=_visage(visage) if visage is not None else None, shirt=couleurs[0], short=couleurs[1], image="data:image/jpeg;base64,xx")


def test_noms_des_couleurs():
    assert [colour_name(c) for c in (ROUGE, BLANC, NOIR, BLEU, "#808080", "#e0c020")] == ["rouge", "blanc", "noir", "bleu", "gris", "jaune"]
    assert outfit_label(ROUGE, NOIR) == "Haut rouge, bas noir"


def test_regrouper_par_personne():
    rouge, blanc, noir = (0, 1), (2, 3), (4, 5)
    combattants = [
        (1, _combattant(*rouge)),
        (1, _combattant(*blanc)),
        (2, _combattant(*blanc)),
        (2, _combattant(*rouge)),
        (3, _combattant(*noir)),
        (3, _combattant(*rouge)),
    ]
    assert group(combattants) == [0, 1, 1, 0, 2, 0]
    # Même tenue dans un même combat : jamais la même personne.
    assert group([(1, _combattant(*noir)), (1, _combattant(*noir))]) == [0, 1]
    # Même tenue, visages différents : deux personnes ; tenue un peu
    # différente, même visage : une seule.
    assert group([(1, _combattant(*noir, visage=1)), (2, _combattant(*noir, visage=2))]) == [0, 1]
    proche = [a * 0.6 + b * 0.4 for a, b in zip(_tenue(0, 1), _tenue(6, 1))]
    assert group([(1, _combattant(0, 1, visage=3)), (2, Fighter(proche, _visage(3), ROUGE, NOIR, None))]) == [0, 0]


def _seance(db, ecole_id, coach_id, jour, n_combats, sc):
    from session_clips.models import ClipSession, Piece

    seance = ClipSession(org_id=ecole_id, title="Adultes", held_on=jour, status="ready", created_by=coach_id)
    db.add(seance)
    db.flush()
    db.add(Piece(session_id=seance.id, position=0, upload_id=f"p{seance.id}", duration_seconds=120.0))
    db.commit()
    clips = [sc.add_clip(db, seance.id, _video(db, e_ecole(db, ecole_id), f"s{seance.id}c{i}").id, [None, None]) for i in range(n_combats)]
    return seance, clips


def e_ecole(db, ecole_id):
    from ecoles.models import Ecole

    return db.get(Ecole, ecole_id)


def test_qui_est_qui(client, db_session, e, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    sc = core.session_clips_client
    ecole, h = e["ecole"].id, e["h"]["coach"]
    karim, lucas = e["karim"].id, e["lucas"].id
    rouge, blanc, noir = (0, 1), (2, 3), (4, 5)

    # Séance du 12/11 : Karim en rouge (visage 1) contre Lucas en blanc, deux fois.
    s1, c1 = _seance(db_session, ecole, e["coach"].id, dt.date(2026, 11, 12), 2, sc)
    vus = {
        f"s{s1.id}c0.mp4": [_combattant(*rouge, visage=1), _combattant(*blanc, couleurs=(BLANC, BLEU))],
        f"s{s1.id}c1.mp4": [_combattant(*blanc, couleurs=(BLANC, BLEU)), _combattant(*rouge, visage=1)],
    }

    def lire(path, faces):
        return vus[path.name]

    url = f"/session-clips/sessions/{s1.id}/people"
    assert client.get(url, headers=h).json() == {"ready": False, "persons": [], "filled": 0, "total": 2}
    assert client.get(url, headers=e["h"]["seb"]).status_code == 403
    assert [s.id for s in people.sessions_to_recognize(db_session)] == [s1.id]
    assert people.recognize(db_session, videos_client, s1, None, lire) == 2
    assert people.sessions_to_recognize(db_session) == []

    r = client.get(url, headers=h).json()
    assert r["ready"] and r["filled"] == 0 and r["total"] == 2
    assert [(p["n"], p["label"], p["fights"], p["name"], p["proposal"]) for p in r["persons"]] == [
        (1, "Haut rouge, bas noir", 2, None, None),
        (2, "Haut blanc, bas bleu", 2, None, None),
    ]
    # Nommer : chaque combat de la personne reçoit le nom ; un nom mis à la main reste.
    sc.set_participants(db_session, _coach(db_session, e), c1[1].id, [None, e["seb"].id])
    r = client.put(f"{url}/1", json={"who": karim}, headers=h).json()
    assert r["persons"][0]["name"] == "Karim B."
    noms = sc.participants(db_session, [c.id for c in c1])
    assert noms[c1[0].id] == [karim, None] and noms[c1[1].id] == [karim, e["seb"].id]
    r = client.put(f"{url}/2", json={"who": "outsider"}, headers=h).json()
    assert r["persons"][1]["outsider"] and r["persons"][1]["name"] == "Inconnu" and r["filled"] == 2
    # Les noms restent à valider à la main (Seb, 17/11).
    assert all(c["to_check"] for c in client.get(f"/session-clips/sessions/{s1.id}", headers=h).json()["clips"])
    r = client.put(f"{url}/2", json={"who": lucas}, headers=h).json()
    assert sc.participants(db_session, [c1[0].id])[c1[0].id] == [karim, lucas]
    assert client.put(f"{url}/9", json={"who": lucas}, headers=h).status_code == 404

    # Séance du 16/11 : Karim a changé de tenue (noire) mais c'est son visage ;
    # Lucas a gardé la sienne ; un nouveau en noir sans visage.
    s2, c2 = _seance(db_session, ecole, e["coach"].id, dt.date(2026, 11, 16), 2, sc)
    vus2 = {
        f"s{s2.id}c0.mp4": [_combattant(*noir, visage=1, couleurs=(NOIR, NOIR)), _combattant(*blanc, couleurs=(BLANC, BLEU))],
        f"s{s2.id}c1.mp4": [_combattant(6, 7, couleurs=(BLEU, BLEU)), _combattant(*blanc, couleurs=(BLANC, BLEU))],
    }
    people.recognize(db_session, videos_client, s2, None, lambda path, faces: vus2[path.name])
    r = client.get(f"/session-clips/sessions/{s2.id}/people", headers=h).json()
    props = {p["n"]: p["proposal"] for p in r["persons"]}
    assert props[2] == {"member_id": lucas, "name": "Lucas M.", "reason": "même tenue le 12/11"}
    assert props[3] is None
    # Le visage seul ne suffit pas sous 0,30 avec une tenue toute différente.
    assert props[1] is None or props[1]["member_id"] == karim

    # Relancer la découpe : les combats changent, la séance est relue et les
    # noms suivent la personne qui ressemble le plus.
    client.put(f"/session-clips/sessions/{s2.id}/people/2", json={"who": lucas}, headers=h)
    sc.delete_clip(db_session, _coach(db_session, e), c2[1].id)
    assert [s.id for s in people.sessions_to_recognize(db_session)] == [s2.id]
    people.recognize(db_session, videos_client, s2, None, lambda path, faces: vus2[path.name])
    r = client.get(f"/session-clips/sessions/{s2.id}/people", headers=h).json()
    assert [p["name"] for p in r["persons"]] == [None, "Lucas M."]

    # Effacer la séance efface ce qui a été repéré.
    assert client.delete(f"/session-clips/sessions/{s2.id}", headers=h).status_code == 204
    assert people.load(ecole, s2.id) is None


def _coach(db, e):
    from session_clips.ports import Member

    return Member(person_id=e["coach"].id, org_id=e["ecole"].id, name="Flo D.", is_coach=True)


def test_tenue_lue_sur_une_image():
    cv2 = pytest.importorskip("cv2")
    import numpy as np

    from session_clips.signals import Pose

    image = np.zeros((400, 200, 3), np.uint8)
    image[:] = (40, 120, 40)
    image[100:200, 50:150] = (40, 40, 210)  # haut rouge (BGR)
    image[200:300, 50:150] = (20, 20, 20)  # bas noir
    k = [(0.0, 0.0, 0.0)] * 17
    k[5], k[6], k[11], k[12], k[13], k[14] = (60, 100, 1), (140, 100, 1), (60, 200, 1), (140, 200, 1), (60, 300, 1), (140, 300, 1)
    hist, haut, bas = people.outfit(image, Pose(k))
    assert len(hist) == 144 and abs(sum(hist) - 2) < 1e-6
    assert colour_name(haut) == "rouge" and colour_name(bas) == "noir"
    assert cv2 is not None


def test_choix_de_la_photo():
    """Seb, 17/11 : pas de photo de dos ni collée à l'autre combattant."""
    from session_clips.people import _overlap, photo_score

    assert _overlap((0, 0, 10, 10), (5, 0, 20, 10)) == 0.5 and _overlap((0, 0, 10, 10), (20, 0, 30, 10)) == 0
    de_face_seul = photo_score(face=0.9, overlap=0.0, height=0.5)
    de_dos_grand = photo_score(face=0.0, overlap=0.0, height=0.9)
    de_face_colle = photo_score(face=0.9, overlap=0.5, height=0.6)
    assert de_face_seul > de_face_colle > de_dos_grand
