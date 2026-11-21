"""Incrustation dans le combat archivé du Timer étendu (Seb, 21/11 ;
session_clips/overlay.py)."""

import subprocess

import imageio_ffmpeg
import pytest

from session_clips import overlay as ov

DEMANDE = {"names": True, "winner": True, "chrono": True, "music": "rock", "announce": True, "rounds": 3,
           "phases": [{"t": 0, "n": 1, "total": 3}, {"t": 3, "n": 0, "total": 1}, {"t": 4, "n": 2, "total": 2}],
           "labels": ["Seb R.", None], "people": [1, None], "voices": ["Seb Richard", None], "result": 1}


def test_chrono_comme_au_timer():
    """« R1, R2… » seulement en plusieurs rounds, « REPOS » entre deux, le
    temps qui reste arrondi au-dessus comme le Timer."""
    assert ov.chrono_at(DEMANDE, 0) == ("R1", "0:03")
    assert ov.chrono_at(DEMANDE, 0.5) == ("R1", "0:03")
    assert ov.chrono_at(DEMANDE, 2.9) == ("R1", "0:01")
    assert ov.chrono_at(DEMANDE, 3.2) == ("REPOS", "0:01")
    assert ov.chrono_at(DEMANDE, 5.99) == ("R2", "0:01")
    assert ov.chrono_at({**DEMANDE, "rounds": 1, "phases": [{"t": 0, "n": 1, "total": 180}]}, 61) == ("", "1:59")
    assert ov.chrono_at({**DEMANDE, "phases": []}, 1) is None


def test_vainqueur_apres_le_gong():
    """Au gong la vidéo s'arrête ; la voix part une fois le gong fini et le
    bandeau monte quand le nom est dit."""
    plan = ov.timeline(DEMANDE, 6.0, None)
    sons = [(p.name, round(t, 2)) for p, t in plan["sounds"]]
    assert sons[0] == ("cloche-fin-de-round.mp3", 6.0)
    assert sons[1] == ("annonce-vainqueur.mp3", 6.0 + ov.GONG_GAP)
    assert sons[2][0] == "annonce-droite.mp3"  # pas de voix pour le nom : le coin droit
    assert plan["banner"] == pytest.approx(sons[2][1], abs=0.01) and plan["banner"] > 6 + ov.GONG_GAP
    assert plan["total"] > plan["banner"]
    # Sans résultat : ni gong ajouté ni arrêt sur image.
    assert ov.timeline({**DEMANDE, "result": None}, 6.0, None) == {"end": 6.0, "banner": None, "total": 6.0, "sounds": []}
    # Sans annonce : le bandeau juste après le gong.
    assert ov.timeline({**DEMANDE, "announce": False}, 6.0, None)["banner"] == 6.0 + ov.GONG_GAP


def test_video_incrustee(tmp_path):
    """La vidéo refaite : même taille, prolongée pour le vainqueur, avec du son."""
    source = tmp_path / "combat.webm"
    subprocess.run(
        [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error", "-f", "lavfi", "-i", "testsrc2=s=320x180:r=25:d=6",
         "-c:v", "libvpx", "-b:v", "300k", str(source)],
        check=True,
    )
    target = tmp_path / "combat-c.mp4"
    assert ov.render(source, target, DEMANDE, 1)
    assert ov.video_size(target) == (320, 180)
    assert ov.has_audio(target)
    assert ov.seconds(target) == pytest.approx(ov.timeline(DEMANDE, 6.0, None)["total"], abs=0.3)
