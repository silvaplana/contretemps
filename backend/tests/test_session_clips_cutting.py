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
from session_clips.signals import Frame, Pose, are_shaking_hands, are_touching_fists_up, is_fist_up, is_x
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
    elif arms == "cross":  # bras croisés devant la poitrine
        k[7], k[8] = (x + 25, 120, 1), (x - 25, 120, 1)
        k[9], k[10] = (x - 15, 105, 1), (x + 15, 105, 1)
    elif arms == "touch":  # bras droit tendu vers le haut, vers l'autre
        k[7], k[8] = (x + 25, 110, 1), (x + 30, 60, 1)
        k[9], k[10] = (x + 25, 140, 1), (x + 20 + wrist_dx, 30, 1)
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
    # Bras croisés devant soi (Seb, 13/11), mais pas la garde ni un buste de profil.
    assert is_x(pose(arms="cross")) and not is_x(pose(arms="guard")) and not is_x(pose())
    profil = pose(arms="cross")
    profil.keypoints[5], profil.keypoints[6] = (105, 80, 1), (95, 80, 1)
    assert not is_x(profil)
    # Ni la garde, ni les bras tendus en Y, ni les bras baissés.
    assert not is_fist_up(pose(arms="guard")) and not is_fist_up(pose(arms="y")) and not is_fist_up(pose())
    # La poignée de main : deux personnes debout, mains jointes sous les épaules.
    assert are_shaking_hands(pose(x=100, arms="hand"), pose(x=145, arms="hand", wrist_dx=-50))
    assert not are_shaking_hands(pose(x=100, arms="hand"), pose(x=300))
    # Les poings touchés en l'air : la même chose au-dessus des épaules.
    assert are_touching_fists_up(pose(x=100, arms="touch"), pose(x=140, arms="touch", wrist_dx=-40))
    assert not are_touching_fists_up(pose(x=100, arms="hand"), pose(x=145, arms="hand", wrist_dx=-50))
    # Vidéos de Seb en plein cadre (12/11) : les poings dépassent des poignets,
    # qui restent à un demi-buste l'un de l'autre.
    assert are_touching_fists_up(pose(x=100, arms="touch"), pose(x=140, arms="touch"))
    assert are_shaking_hands(pose(x=100, arms="hand"), pose(x=145, arms="hand"))


def frames(spec, fps=5):
    """`spec` : liste de (secondes, personnes)."""
    out, t = [], 0.0
    for seconds, people in spec:
        for _ in range(int(seconds * fps)):
            out.append(Frame(t=round(t, 2), people=people))
            t += 1 / fps
    return out


def test_combats_reperes():
    y2 = [pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]  # poings touchés en l'air
    fight = [pose(100), pose(300)]
    salute = [pose(100, "hand"), pose(145, "hand", wrist_dx=-50)]
    x = [pose(100, "x"), pose(300, "x")]
    video = frames([
        (3, fight),  # échauffement : pas de poing levé, pas de combat
        (2, y2), (30, fight), (1, salute),  # combat 1, fini par le salut
        (5, []),
        (2, y2), (20, fight), (1, x),  # combat 2, fini par le X
        (2, y2), (1, fight), (1, x),  # trop court : ignoré
        (2, y2), (15, fight), (6, []),  # combat 3 : la zone vide ne le finit pas
        (2, y2), (12, fight),  # combat 4, coupé par la fin de la vidéo
    ])
    fights = find_fights(video)
    assert len(fights) == 4
    assert [f.fighters for f in fights] == [2, 2, 2, 2]
    assert fights[0].start == pytest.approx(3, abs=0.3) and fights[0].end == pytest.approx(36, abs=0.5)
    # Seb, 13/11 : une zone qui a l'air vide (pièce sombre) ne finit jamais un
    # combat ; il va jusqu'au poing levé suivant (68 + 2 + 15 + 6).
    assert fights[2].end == pytest.approx(91, abs=0.5)
    assert [f.check_reason for f in fights] == [None, None, None, REASON_NO_END]


def test_nouveau_poing_leve_termine_le_combat():
    y2 = [pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]  # poings touchés en l'air
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

    y2 = [pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]  # poings touchés en l'air
    fight = [pose(100), pose(300)]
    detecteur = lambda _path: frames([(2, y2), (12, fight), (1, [pose(100, "x"), pose(300, "x")]), (5, []), (2, y2), (15, fight)])
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
    assert premier.nom == "Fights · 27/10/2026 · Adultes · 19 h · combat 1"
    assert premier.compresse and premier.poster and 13 <= premier.duree_secondes <= 16
    assert (tmp_path / premier.lien_fichier).exists()
    # La vidéo brute est gardée jusqu'à la validation.
    assert core.videos_client.get(db_session, session.raw_video_id) is not None

    # « Usage des ressources » : clips et vidéo entière rangés sous « Sparring ».
    usage = core.videos_client.usage_ecole(db_session, session.org_id)
    assert [r.libelle for r in usage.rubriques] == ["Fights"]
    assert usage.rubriques[0].octets == usage.total_octets > 0
    assert {v.rubrique for v in usage.top_videos} == {"Fights"}


def test_time_crie_termine_le_combat():
    """Le « Time ! » de l'entraîneur (hearing.py) finit le combat comme un
    geste de fin, s'il est coché."""
    from session_clips.hearing import is_time

    assert is_time(" Time!") and is_time("taïme") and not is_time("temps") and not is_time("Tim")
    touch = [pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]
    fight = [pose(100), pose(300)]
    video = frames([(1, touch), (19, fight)])
    assert [f.end for f in find_fights(video, sounds=[12.0])] == [13.0]
    assert find_fights(video, sounds=[12.0])[0].check_reason is None
    # Décoché : le combat va jusqu'au bout de la vidéo.
    assert find_fights(video, enabled=("fists_touch", "x"), sounds=[12.0])[0].check_reason == REASON_NO_END


def test_cadrage_serre(tmp_path):
    """Cadrage « Serré » (framing.py) : le cadre suit les deux corps, plus
    petit que l'image, et ffmpeg coupe le clip à sa taille."""
    from session_clips.cutting import cut_clip
    from session_clips.framing import track, video_size

    source = tmp_path / "salle.mp4"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "testsrc=s=1280x720:d=6:r=25", "-pix_fmt", "yuv420p", str(source)],
        check=True,
    )
    assert video_size(source) == (1280, 720)
    # Deux personnes à gauche de l'image, qui glissent vers la droite.
    video = [Frame(t=i / 5, people=[pose(100 + 10 * i), pose(160 + 10 * i)]) for i in range(30)]
    assert track(video, 0, 5, "wide", (1280, 720)) is None
    serre = track(video, 0, 5, "tight", (1280, 720))
    moyen = track(video, 0, 5, "medium", (1280, 720))
    assert serre[0][3] < moyen[0][3] < 1  # serré, plus petit que moyen
    assert serre[-1][1] > serre[0][1]  # le cadre suit vers la droite
    dest = tmp_path / "clip.mp4"
    assert cut_clip(source, 0, 5, dest, serre, (1280, 720))
    assert video_size(dest)[0] < 1280 and not dest.with_suffix(".cmd").exists()


def test_ecoute_impossible_ne_bloque_pas_la_lecture(monkeypatch, tmp_path):
    """Whisper en panne : pas de « Time ! », mais la vidéo est lue (Seb, 12/11)."""
    from session_clips import hearing

    def panne(_path):
        raise RuntimeError("modèle introuvable")

    monkeypatch.setattr(hearing, "_hear", panne)
    assert hearing.hear(tmp_path / "video.mp4") == []


def test_ecoute_des_cris_brefs(monkeypatch, tmp_path, capsys):
    """« Go ! » et « Time ! » criés seuls (Seb, 12/11, essai « Go time ») :
    écoute en anglais, cris brefs gardés, et ce qui est compris va au journal."""
    import sys
    import types

    from session_clips import hearing

    reglages = {}

    class Modele:
        def __init__(self, *_a, **_k):
            pass

        def transcribe(self, _path, **kwargs):
            reglages.update(kwargs)
            mot = lambda w, t, p: types.SimpleNamespace(word=w, start=t, end=t + 0.3, probability=p)
            return [types.SimpleNamespace(words=[mot(" Go!", 3.9, 0.9), mot(" Time!", 7.3, 0.31)])], None

    monkeypatch.setitem(sys.modules, "faster_whisper", types.SimpleNamespace(WhisperModel=Modele))
    monkeypatch.setattr(hearing, "_models", {})
    # 10 s de bruit de fond, un cri fort à 4 s ; rien à 7,3 s (Seb, 14/11 :
    # chaque cri vient avec sa note de confiance et son volume).
    import numpy as np

    son = np.random.default_rng(0).normal(0, 0.01, 16000 * 10).astype(np.float32)
    son[16000 * 4 : 16000 * 4 + 3200] *= 30
    monkeypatch.setattr(hearing, "_audio", lambda _path: son)
    [(go, t_go, note_go, fort_go), (time, t_time, note_time, fort_time)] = hearing.hear(tmp_path / "go-time.mp4")
    assert (go, t_go, note_go, time, t_time, note_time) == ("go", 3.9, 0.9, "time", 7.3, 0.31)
    assert fort_go > 20 and fort_time < 3
    import json

    json.dumps(hearing.hear(tmp_path / "go-time.mp4"))  # gardé tel quel dans le .sounds.json (Seb, 14/11 : « Découpe impossible »)
    assert reglages["language"] == "en" and reglages["vad_parameters"]["min_speech_duration_ms"] <= 100
    assert "Go!@3.9~0.90 Time!@7.3~0.31" in capsys.readouterr().out


def test_son_lu_par_ffmpeg(tmp_path):
    """Le son est lu par ffmpeg (16 kHz mono) et non par PyAV, qui plantait
    dans l'image sparring-worker (12/11) : aucun « Go » ni « Time » entendu."""
    import subprocess

    import imageio_ffmpeg

    from session_clips import hearing

    video = tmp_path / "son.mp4"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc=s=320x240:d=2:r=25",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-shortest", "-pix_fmt", "yuv420p", str(video)],
        check=True,
    )
    son = hearing._audio(video)
    assert 1.8 * 16000 < len(son) < 2.2 * 16000 and son.dtype.name == "float32" and abs(son).max() > 0.05


def test_go_crie_commence_le_combat():
    """« Go ! » pour commencer, « Time ! » pour finir (Seb, 12/11) ; les
    poings touchés juste avant le « Go ! » ne font qu'un début."""
    from session_clips.hearing import word_kind

    assert word_kind(" Go!") == "go" and word_kind("Time.") == "time" and word_kind("gauche") is None
    fight = [pose(100), pose(300)]
    video = frames([(20, fight)])
    assert [(f.start, f.end) for f in find_fights(video, sounds=[("go", 2.0), ("time", 12.0)])] == [(2.0, 13.0)]
    touch = [pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]
    video = frames([(1, touch), (19, fight)])
    assert [(f.start, f.end) for f in find_fights(video, sounds=[("go", 1.5), ("time", 12.0)])] == [(0.0, 13.0)]


def test_go_puis_time_meme_court():
    """« Go ! » à 5,6 s puis « Time ! » à 6,9 s (essai « Go time » de Seb,
    12/11) : les deux cris disent le combat, même court."""
    video = frames([(9, [pose(100), pose(300)])])
    assert [(f.start, f.end) for f in find_fights(video, sounds=[("go", 5.6), ("time", 6.9)])] == [(5.6, 7.9)]


def test_deux_go_time_a_la_suite():
    """Séance de Seb, 13/11 : « Go ! » 11 s, « Time ! » 11,8 s, « Go ! » 13,4 s,
    « Time ! » 23,2 s, pièce sombre (personne vu après 15 s). Deux combats :
    les deux « Go ! » ne se fondent pas (un « Time ! » entre eux), un « Time ! »
    crié tout de suite compte, et la zone vide ne passe pas avant le cri."""
    sons = [("go", 11.0), ("time", 11.8), ("go", 13.4), ("time", 23.2)]
    video = frames([(15, [pose(100), pose(300)]), (15, [])])
    assert [(f.start, f.end) for f in find_fights(video, sounds=sons)] == [(11.0, 12.8), (13.4, 24.2)]


def test_time_go_time_go():
    """Seb, 13/11 : dans le désordre, « Time ! » 5 s, « Go ! » 10 s, « Time ! »
    20 s, « Go ! » 25 s : un seul combat, du « Go ! » au « Time ! ». Le
    premier « Time ! » ne ferme rien, le dernier « Go ! » n'a pas de fin."""
    sons = [("time", 5.0), ("go", 10.0), ("time", 20.0), ("go", 25.0)]
    video = frames([(40, [pose(100), pose(300)])])
    assert [(f.start, f.end) for f in find_fights(video, sounds=sons)] == [(10.0, 21.0)]


def test_seance_9_poings_touches_puis_go_time():
    """Séance 9 de Seb (13/11, réglages : poings touchés, Go, X, Time).
    Combat 1 : poings touchés en l'air, lus comme deux poings levés (37,6 s) :
    deux poings levés ne sont pas des poings touchés (Seb, 13/11), pas de combat.
    Combat 2 : « Go ! » 45,5 s (redit à 47,4 s), « Time ! » 65,5 s ; Whisper
    entend aussi un « go » 0,5 s avant le « Time ! », qui ne coupe pas le combat."""
    y2 = [pose(100, "fist"), pose(300, "fist")]
    fight = [pose(100), pose(300)]
    video = frames([(37.6, fight), (2, y2), (33.4, fight)])
    sons = [("go", 45.5), ("go", 47.4), ("go", 65.0), ("time", 65.5)]
    fights = find_fights(video, ("fists_touch", "go", "x", "time"), sons)
    assert [(round(f.start, 1), round(f.end, 1)) for f in fights] == [(45.5, 66.5)]


def test_bras_croises_chacun_finit_le_combat():
    """Seb, 13/11 : la fin, c'est chacun qui croise les bras devant soi, tenu
    au moins 0,5 s ; un seul qui croise les bras ne finit rien."""
    touch = [pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]
    fight = [pose(100), pose(300)]
    un = [pose(100, "cross"), pose(300)]
    deux = [pose(100, "cross"), pose(300, "cross")]
    video = frames([(1, touch), (10, fight), (1, un), (10, fight), (1, deux), (5, fight), (1, touch), (3, fight)])
    fights = find_fights(video, ("fists_touch", "x"))
    assert [(round(f.start, 1), round(f.end, 1)) for f in fights][0] == (0.0, 23.0)


def test_pas_de_cri_dans_un_bout_trop_court(tmp_path):
    """Le dernier morceau de la séance 9 dure 1 s : Whisper y « entend » Go,
    Time, Go (les mots qu'on lui souffle). Un morceau de moins de 2 s n'est
    pas écouté."""
    from session_clips.cutting import _heard

    fichier = tmp_path / "m.sounds.json"
    fichier.write_text('[["go", 0.0], ["time", 0.8], ["go", 0.8]]')
    assert _heard(fichier, 1.09) == []
    assert _heard(fichier, 72.9) == [["go", 0.0], ["time", 0.8], ["go", 0.8]]
    assert _heard(tmp_path / "absent.json", 30) == []


def test_cris_forts_et_mots_surs():
    """Seb, 14/11 : l'écoute invente les mots qu'on lui souffle sur un passage
    calme. Deux cases des réglages : seulement les cris forts (6 dB au-dessus
    du bruit de fond), seulement les mots sûrs (note ≥ 0,5). Un cri entendu
    avant (sans note ni volume) est gardé."""
    from session_clips.lab import Settings, heard

    sons = [["fight", 6.8, 0.9, 25.0], ["time", 18.4, 0.8, 1.0], ["hajime", 17.4, 0.2, 20.0], ["go", 3.0]]
    assert heard(sons, Settings()) == [("fight", 6.8), ("time", 18.4), ("hajime", 17.4), ("go", 3.0)]
    assert heard(sons, Settings(loud_only=True)) == [("fight", 6.8), ("hajime", 17.4), ("go", 3.0)]
    assert heard(sons, Settings(sure_only=True)) == [("fight", 6.8), ("time", 18.4), ("go", 3.0)]
    assert heard(sons, Settings(loud_only=True, sure_only=True)) == [("fight", 6.8), ("go", 3.0)]
    # Les seuils se règlent au curseur (Seb, 14/11).
    assert heard(sons, Settings(loud_only=True, loud_db=30.0)) == [("go", 3.0)]
    assert heard(sons, Settings(sure_only=True, sure_min=0.1)) == [("fight", 6.8), ("time", 18.4), ("hajime", 17.4), ("go", 3.0)]


def test_frise_avec_volume_et_note():
    """Seb, 14/11 : dans la frise, chaque cri montre son volume et sa note,
    même s'il est écarté par les réglages (pour régler le seuil)."""
    from session_clips.cutting import _signs

    cris = [["fight", 6.8, 0.9, 25.0], ["time", 18.4, 0.3, 1.0]]
    signes = _signs(frames([(20, [pose(100), pose(300)])]), cris, [], None)
    assert [(s["kind"], s["db"], s["note"]) for s in signes] == [("fight", 25.0, 0.9), ("time", 1.0, 0.3)]


def test_fight_et_hajime_commencent_le_combat():
    """Seb, 13/11 : « Go » se confond avec « allez » ; « Fight ! » et
    « Hajime ! » (« ha-dji-mé ») commencent aussi un combat, jusqu'au « Time ! »."""
    from session_clips.hearing import heard_words, word_kind

    assert word_kind("Fight!") == "fight" and word_kind("Hajimé") == "hajime" and word_kind("fait") is None
    assert heard_words([("Ha", 2.0), ("jime!", 2.3), ("time", 9.0), ("allez", 10.0)]) == [("hajime", 2.0), ("time", 9.0)]
    video = frames([(40, [pose(100), pose(300)])])
    sons = [("fight", 2.0), ("time", 12.0), ("hajime", 20.0), ("time", 30.0)]
    assert [(f.start, f.end) for f in find_fights(video, sounds=sons)] == [(2.0, 13.0), (20.0, 31.0)]


def test_combat_crie_commence_le_combat():
    """Seb, 14/11 : « Combat ! » crié commence aussi un combat."""
    from session_clips.hearing import word_kind

    assert word_kind("Combat!") == "combat" and word_kind("Combats") == "combat"
    video = frames([(20, [pose(100), pose(300)])])
    assert [(f.start, f.end) for f in find_fights(video, sounds=[("combat", 2.0), ("time", 12.0)])] == [(2.0, 13.0)]


def test_bras_leves_des_deux_commencent_le_combat():
    """Seb, 13/11 : les deux combattants lèvent les deux bras au-dessus de la
    tête, tenu 0,5 s ; un seul ne compte pas, la garde non plus."""
    from session_clips.signals import is_arms_up

    assert is_arms_up(pose(arms="y")) and not is_arms_up(pose(arms="guard")) and not is_arms_up(pose(arms="fist"))
    fight = [pose(100), pose(300)]
    un = [pose(100, "y"), pose(300)]
    deux = [pose(100, "y"), pose(300, "y")]
    croises = [pose(100, "cross"), pose(300, "cross")]
    video = frames([(2, un), (3, fight), (1, deux), (10, fight), (1, croises), (3, fight)])
    fights = find_fights(video, ("arms_up", "x"))
    assert [(round(f.start, 1), round(f.end, 1)) for f in fights] == [(5.0, 17.0)]


def test_video_couchee_redressee():
    """Séance 9 (13/11) : filmée couchée, les postures sont allongées et aucun
    geste ne se lit. L'analyse les redresse d'un quart de tour (Seb, 14/11)."""
    from session_clips.signals import quarter_turn

    touch = [pose(100, "touch"), pose(140, "touch", wrist_dx=-40)]
    fight = [pose(100), pose(300)]
    croises = [pose(100, "cross"), pose(300, "cross")]
    debout = frames([(1, touch), (10, fight), (1, croises), (3, fight)])
    for way in (1, -1):
        fights = find_fights(quarter_turn(debout, way), ("fists_touch", "x"))
        assert [(round(f.start, 1), round(f.end, 1)) for f in fights] == [(0.0, 12.0)]


def test_cris_d_avant_reecoutes():
    """Des cris gardés avant le 14/11, sans note ni volume : « Relancer la
    découpe » réécoute le morceau pour que les cases du 14/11 servent."""
    from session_clips.cutting import _unrated

    import tempfile
    from pathlib import Path

    tmp = Path(tempfile.mkdtemp())
    fichier = tmp / "m.sounds.json"
    fichier.write_text('[["go", 1.0]]')
    assert _unrated(fichier)
    fichier.write_text('[["go", 1.0, 0.9, 12.0]]')
    assert not _unrated(fichier)
    fichier.write_text("[]")
    assert not _unrated(fichier) and not _unrated(tmp / "absent.json")
