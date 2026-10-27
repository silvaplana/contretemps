"""Découpe d'une séance de Sparring (spec/modules/video-combats.md §5) :
gestes sur des postures fabriquées, repérage des combats, puis découpe
d'une vraie vidéo par ffmpeg avec un détecteur simulé (sans YOLO)."""

import datetime as dt
import subprocess

import imageio_ffmpeg
import pytest

from app.main import core
from comptes import Comptes
from ecoles import Ecoles
from session_clips.cutting import REASON_NAMES, cut_session, sessions_to_cut
from session_clips.fights import REASON_NO_END, find_fights
from session_clips.models import ClipSession
from session_clips.signals import Frame, Pose, are_saluting, is_fist_up, is_x
from videos.stockage import chemin_relatif, dossier_ecole


def pose(x=100, arms="down", wrist_dx=0.0):
    """Une personne debout, épaules de 40 px, tête à y=50, hanches à y=160."""
    k = [(0.0, 0.0, 0.0)] * 17
    k[0] = (x, 50, 1)  # nez
    k[5], k[6] = (x + 20, 80, 1), (x - 20, 80, 1)  # épaules (gauche à droite de l'image)
    k[11], k[12] = (x + 15, 160, 1), (x - 15, 160, 1)
    if arms == "fist":  # poing droit levé, bras plié, coude à hauteur d'épaule
        k[7], k[8] = (x + 25, 110, 1), (x - 45, 80, 1)
        k[9], k[10] = (x + 25, 140, 1), (x - 45, 30, 1)
    elif arms == "guard":  # garde : poings devant le visage, coudes bas
        k[7], k[8] = (x + 25, 120, 1), (x - 25, 120, 1)
        k[9], k[10] = (x + 10, 45, 1), (x - 10, 45, 1)
    elif arms == "y":
        k[7], k[8] = (x + 40, 60, 1), (x - 40, 60, 1)
        k[9], k[10] = (x + 60, 20, 1), (x - 60, 20, 1)
    elif arms == "x":
        k[7], k[8] = (x + 25, 60, 1), (x - 25, 60, 1)
        k[9], k[10] = (x - 10, 25, 1), (x + 10, 25, 1)  # croisés
    elif arms == "hand":
        k[7], k[8] = (x + 25, 110, 1), (x - 25, 110, 1)
        k[9], k[10] = (x + 20 + wrist_dx, 120, 1), (x - 25, 140, 1)
    else:
        k[7], k[8] = (x + 25, 110, 1), (x - 25, 110, 1)
        k[9], k[10] = (x + 25, 140, 1), (x - 25, 140, 1)
    return Pose(k)


def test_gestes():
    assert is_fist_up(pose(arms="fist")) and not is_x(pose(arms="fist"))
    assert is_x(pose(arms="x")) and not is_fist_up(pose(arms="x"))
    # Ni la garde, ni les bras tendus en Y, ni les bras baissés.
    assert not is_fist_up(pose(arms="guard")) and not is_fist_up(pose(arms="y")) and not is_fist_up(pose())
    # Le salut : deux personnes debout, mains jointes.
    assert are_saluting(pose(x=100, arms="hand"), pose(x=145, arms="hand", wrist_dx=-50))
    assert not are_saluting(pose(x=100, arms="hand"), pose(x=300))


def frames(spec, fps=5):
    """`spec` : liste de (secondes, personnes)."""
    out, t = [], 0.0
    for seconds, people in spec:
        for _ in range(int(seconds * fps)):
            out.append(Frame(t=round(t, 2), people=people))
            t += 1 / fps
    return out


def test_combats_reperes():
    y2 = [pose(100, "fist"), pose(300, "fist")]
    fight = [pose(100), pose(300)]
    salute = [pose(100, "hand"), pose(145, "hand", wrist_dx=-50)]
    x = [pose(100, "x"), pose(300)]
    video = frames([
        (3, fight),  # échauffement : pas de poing levé, pas de combat
        (2, y2), (30, fight), (1, salute),  # combat 1, fini par le salut
        (5, []),
        (2, y2), (20, fight), (1, x),  # combat 2, fini par le X
        (2, y2), (3, fight), (1, x),  # trop court : ignoré
        (2, y2), (15, fight), (6, []),  # combat 3, fini par la zone vide
        (2, y2), (12, fight),  # combat 4, coupé par la fin de la vidéo
    ])
    fights = find_fights(video)
    assert len(fights) == 4
    assert [f.fighters for f in fights] == [2, 2, 2, 2]
    assert fights[0].start == pytest.approx(3, abs=0.3) and fights[0].end == pytest.approx(36.6, abs=0.5)
    assert fights[2].end == pytest.approx(87, abs=0.5)  # dès que la zone se vide (70 + 2 + 15)
    assert [f.check_reason for f in fights] == [None, None, None, REASON_NO_END]


def test_nouveau_poing_leve_termine_le_combat():
    y2 = [pose(100, "fist"), pose(300, "fist")]
    fight = [pose(100), pose(300)]
    fights = find_fights(frames([(2, y2), (15, fight), (2, y2), (15, fight)]))
    assert len(fights) == 2 and fights[0].end == pytest.approx(fights[1].start)


def _fausse_seance(db, secondes=40):
    ecole = Ecoles().create(db, nom="Fight Lab", code_postal="13600")
    coach = Comptes().create(db, ecole_id=ecole.id, role="professeur", nom="Durand", prenom="Flo")
    fichier = dossier_ecole(ecole.id) / "brute.mp4"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"testsrc=s=640x360:d={secondes}:r=25", "-pix_fmt", "yuv420p", str(fichier)],
        check=True,
    )
    raw = core.videos_client.create(
        db, ecole_id=ecole.id, nom="Séance", lien_fichier=chemin_relatif(ecole.id, fichier.name), uploaded_by=coach.id
    )
    session = ClipSession(org_id=ecole.id, title="Adultes · 19 h", held_on=dt.date(2026, 10, 27),
                          raw_video_id=raw.id, created_by=coach.id)
    db.add(session)
    db.commit()
    return session


def test_decoupe_une_seance(db_session, tmp_path, monkeypatch):
    monkeypatch.setattr("videos.stockage.DOSSIER_VIDEOS_LIVE", tmp_path)
    monkeypatch.setattr("session_clips.cutting.DOSSIER_VIDEOS_LIVE", tmp_path)
    monkeypatch.setattr("videos.videos.DOSSIER_VIDEOS_LIVE", tmp_path)
    session = _fausse_seance(db_session)
    assert [s.id for s in sessions_to_cut(db_session)] == [session.id]

    y2 = [pose(100, "fist"), pose(300, "fist")]
    fight = [pose(100), pose(300)]
    detecteur = lambda _path: frames([(2, y2), (12, fight), (1, [pose(100, "x"), pose(300)]), (5, []), (2, y2), (15, fight)])
    sc = core.session_clips_client
    assert cut_session(db_session, sc, session, detecteur) == 2
    # Rejouable : un 2e passage remplace les clips au lieu de les doubler.
    assert cut_session(db_session, sc, session, detecteur) == 2

    assert session.status == "ready" and sessions_to_cut(db_session) == []
    clips = sc.clips_by_session(db_session, [session.id])[session.id]
    assert [c.position for c in clips] == [1, 2]
    assert all(c.to_check for c in clips)
    assert [c.check_reason for c in clips] == [REASON_NAMES, REASON_NO_END]
    assert sc.participants(db_session, [c.id for c in clips])[clips[0].id] == [None, None]
    videos = sc.video_map(db_session, [c.video_id for c in clips])
    premier = videos[clips[0].video_id]
    assert premier.nom == "Sparring · 27/10/2026 · Adultes · 19 h · combat 1"
    assert premier.compresse and premier.poster and 13 <= premier.duree_secondes <= 16
    assert (tmp_path / premier.lien_fichier).exists()
    # La vidéo brute est gardée jusqu'à la validation.
    assert core.videos_client.get(db_session, session.raw_video_id) is not None

    # « Usage des ressources » : clips et vidéo entière rangés sous « Sparring ».
    usage = core.videos_client.usage_ecole(db_session, session.org_id)
    assert [r.libelle for r in usage.rubriques] == ["Sparring"]
    assert usage.rubriques[0].octets == usage.total_octets > 0
    assert {v.rubrique for v in usage.top_videos} == {"Sparring"}
