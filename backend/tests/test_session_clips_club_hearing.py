"""L'écoute du club (Seb, 14/11) : un cri de la séance est reconnu s'il
ressemble aux cris enregistrés dans Entraîner l'écoute, et rien n'est
inventé sur un passage calme. L'empreinte de wav2vec2 est remplacée ici par
le spectre du son : un « mot » = une note."""

import numpy as np

from session_clips import club_hearing
from session_clips.club_hearing import RATE, hear_club, templates

BANDS = np.linspace(100, 3000, 30)


def _spectre(audio):
    n = RATE // 50  # 20 ms
    frames = audio[: len(audio) // n * n].reshape(-1, n)
    freqs = np.fft.rfftfreq(n, 1 / RATE)
    mag = np.abs(np.fft.rfft(frames, axis=1))
    return np.stack([mag[:, (freqs >= f - 50) & (freqs < f + 50)].sum(axis=1) for f in BANDS], axis=1)


def _bruit(secondes, seed=0):
    return np.random.default_rng(seed).normal(0, 0.01, int(RATE * secondes)).astype(np.float32)


def _cri(son, t, hz, duree=0.4):
    a = int(t * RATE)
    x = np.arange(int(duree * RATE)) / RATE
    son[a : a + len(x)] += 0.5 * np.sin(2 * np.pi * hz * x).astype(np.float32)


def test_cris_du_club(monkeypatch, tmp_path):
    monkeypatch.setattr(club_hearing, "embed", _spectre)
    enregistrements = {}
    for mot, hz in (("time", 440), ("hajime", 1500)):
        (tmp_path / mot).mkdir()
        for i in range(5):
            f = tmp_path / mot / f"{i}.webm"
            f.write_text("")
            son = _bruit(2, seed=i)
            _cri(son, 0.6 + 0.1 * i, hz * (1 + 0.01 * i))
            enregistrements[f.name, mot] = son
    mots = templates(tmp_path, lambda p: enregistrements[p.name, p.parent.name])
    assert {m: len(e) for m, e in mots.items()} == {"time": 5, "hajime": 5}

    seance = _bruit(20, seed=9)
    _cri(seance, 3.0, 1510)  # « Hajime ! »
    _cri(seance, 12.0, 445)  # « Time ! »
    trouves = hear_club(seance, mots)
    assert [(m, round(t)) for m, t, _note, _db in trouves] == [("hajime", 3), ("time", 12)]
    assert all(note > 0.8 and db > 20 for _m, _t, note, db in trouves)
    # Rien d'inventé sur un passage calme.
    assert hear_club(_bruit(20, seed=3), mots) == []
    # Sans cri enregistré, l'écoute du club n'entend rien.
    assert hear_club(seance, {}) == []


def test_un_long_time_compte_une_fois():
    """Seb, 14/11 : un grand « Tiiime » de plus d'1 s donnait deux « Time »
    (deux pics de volume) ; tant que le son ne retombe pas, c'est un seul cri."""
    from session_clips.club_hearing import FRAME, peaks

    calme, cri = [0.0] * 20, [30.0, 40.0, 35.0, 30.0] + [32.0] * 20 + [41.0, 33.0, 30.0]
    # Le plus fort de chaque cri : le 41 dB, à la 24e tranche du cri.
    assert [round(t, 2) for t in peaks(calme + cri + calme + cri + calme)] == [
        round((20 + 24) * FRAME, 2),
        round((20 + len(cri) + 20 + 24) * FRAME, 2),
    ]
