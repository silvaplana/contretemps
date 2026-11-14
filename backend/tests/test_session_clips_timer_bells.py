"""Seb, 14/11 : repérer les sons du Timer de Fights dans la vidéo, la cloche
du début (un coup) et la fin (trois coups), même avec du bruit et des voix,
sans confondre avec les bips de fin du repos."""

from pathlib import Path

import numpy as np

from session_clips.hearing import _audio
from session_clips.timer_bells import RATE, bells

SONS = Path(__file__).resolve().parents[2] / "frontend/src/modules/session-clips/sons"


def _poser(fond, t, son, volume=0.3):
    a = int(t * RATE)
    fond[a : a + len(son)] += volume * son[: len(fond) - a]


def test_cloche_et_trois_coups():
    rng = np.random.default_rng(1)
    fond = rng.normal(0, 0.02, RATE * 40).astype(np.float32)
    # Des « voix » : du bruit modulé, fort, entre 150 et 3000 Hz.
    voix = np.convolve(rng.normal(0, 1, len(fond)), np.hanning(12), "same") * (np.sin(np.arange(len(fond)) / 1600) > 0.3)
    fond += (0.05 * voix).astype(np.float32)
    _poser(fond, 2.0, _audio(SONS / "bips-fin-du-repos.mp3"))
    _poser(fond, 5.0, _audio(SONS / "cloche-debut-de-round.mp3"))
    _poser(fond, 30.0, _audio(SONS / "cloche-fin-de-round.mp3"), volume=0.1)  # plus loin, sous les voix
    trouves = bells(fond)
    assert [(k, round(t)) for k, t, _n, _db in trouves] == [("bell", 5), ("bells", 30)]
    assert all(db > 6 for *_x, db in trouves)


def test_rien_sans_cloche():
    rng = np.random.default_rng(2)
    fond = rng.normal(0, 0.02, RATE * 20).astype(np.float32)
    _poser(fond, 2.0, _audio(SONS / "bips-fin-du-repos.mp3"))
    _poser(fond, 8.0, _audio(SONS / "clac-clac-10-secondes.mp3"))
    assert bells(fond) == []


def test_memes_sons_que_le_timer():
    """Les cloches comparées sont celles que joue le Timer."""
    from session_clips.timer_bells import KINDS, SOUNDS as COPIES

    for nom in KINDS.values():
        assert (COPIES / nom).read_bytes() == (SONS / nom).read_bytes()
