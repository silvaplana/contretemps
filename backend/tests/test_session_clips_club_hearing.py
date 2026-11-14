"""L'écoute du club (Seb, 14/11) : un cri de la séance est reconnu s'il
ressemble aux cris enregistrés dans Entraîner l'écoute, et rien n'est
inventé sur un passage calme. L'empreinte de wav2vec2 est remplacée ici par
le spectre du son : un « mot » = une note."""

import numpy as np
import pytest

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

    # Un autre cri proche (470 Hz) passe pour « Time » tant qu'on n'a que des Time…
    autre = _bruit(20, seed=4)
    _cri(autre, 5.0, 470)
    seuls_time = {"time": mots["time"]}
    assert [m for m, *_x in hear_club(autre, seuls_time)] == ["time"]
    # … mais plus une fois signalé « Mauvais » (Seb, 14/11).
    (tmp_path / "other").mkdir()
    f = tmp_path / "other" / "0.wav"
    f.write_text("")
    son = _bruit(2, seed=5)
    _cri(son, 0.6, 472)
    enregistrements[f.name, "other"] = son
    avec_faux = templates(tmp_path, lambda p: enregistrements[p.name, p.parent.name])
    assert hear_club(autre, {"time": avec_faux["time"], "other": avec_faux["other"]}) == []


def _deux_notes(son, t, premiere, seconde, duree=0.3):
    _cri(son, t, premiere, duree)
    _cri(son, t + duree, seconde, duree)


def test_l_ordre_des_sons_compte(monkeypatch, tmp_path):
    """Étude du 14/11 : la moyenne des empreintes perdait l'ordre des sons
    (« Time » et « Fight » partagent le « aï ») ; le cri entier, comparé dans
    l'ordre, distingue deux mots faits des mêmes sons."""
    monkeypatch.setattr(club_hearing, "embed", _spectre)
    sons = {}
    for mot, notes in (("time", (440, 1500)), ("combattez", (1500, 440))):
        (tmp_path / mot).mkdir()
        for i in range(4):
            f = tmp_path / mot / f"{i}.webm"
            f.write_text("")
            son = _bruit(2, seed=i)
            _deux_notes(son, 0.5, notes[0] * (1 + 0.01 * i), notes[1] * (1 + 0.01 * i))
            sons[f.name, mot] = son
    mots = templates(tmp_path, lambda p: sons[p.name, p.parent.name])
    seance = _bruit(20, seed=9)
    _deux_notes(seance, 3.0, 1505, 442)  # « Combat ! »
    _deux_notes(seance, 12.0, 443, 1510)  # « Time ! »
    assert [(m, round(t)) for m, t, *_x in hear_club(seance, mots)] == [("combattez", 3), ("time", 12)]


def test_meme_nombre_d_exemples_par_mot(monkeypatch, tmp_path):
    """Étude du 14/11 : 30 Time contre 6 Combat, le mot le plus enregistré
    gagnait plus souvent. Chaque mot est jugé sur ses N exemples les plus
    récents, N étant le nombre du mot le moins enregistré."""
    from session_clips.club_hearing import candidates

    monkeypatch.setattr(club_hearing, "embed", _spectre)
    vus = []
    monkeypatch.setattr(club_hearing, "_closeness", lambda v, exemples: vus.append(len(exemples)) or 0.5)
    exemple = np.ones((10, len(BANDS)))
    seance = _bruit(5)
    _cri(seance, 2.0, 440)
    candidates(seance, {"time": [exemple] * 30, "combattez": [exemple] * 6})
    assert vus == [6, 6]


def test_bruit_de_fond_d_autour():
    """Étude du 14/11 : le bruit de fond était la médiane de tout
    l'enregistrement ; dans un long passage bruyant (la salle qui
    s'échauffe), tout paraissait 30 dB plus fort. C'est maintenant le bruit
    des 10 s autour : le passage bruyant revient à 0 dB, un cri y ressort."""
    from session_clips.club_hearing import peaks
    from session_clips.hearing import loudness

    son = _bruit(60, seed=1)
    son[RATE * 20 : RATE * 40] *= 30  # 20 s de salle bruyante
    _cri(son, 30.0, 440, duree=0.4)  # un cri dans le bruit…
    son[int(RATE * 30) : int(RATE * 30.4)] *= 3
    _cri(son, 50.0, 440)  # … et un dans le calme
    volumes = loudness(son)
    assert volumes[int(26 / 0.05)] < 3  # le bruit de la salle, loin des bords
    assert {30, 50} <= {round(i * 0.05) for i in peaks(volumes)}


class _FauxTorch:
    """Juste ce qu'embed() demande à torch, en numpy (torch n'est installé que dans sparring-worker)."""

    class T:
        def __init__(self, a):
            self.a = a

        def float(self):
            return self

        def __getitem__(self, i):
            return _FauxTorch.T(self.a[i])

        def numpy(self):
            return self.a

    @staticmethod
    def from_numpy(a):
        return _FauxTorch.T(a)

    @staticmethod
    def inference_mode():
        import contextlib

        return contextlib.nullcontext()


def test_un_cri_a_cheval_sur_deux_tranches(monkeypatch):
    """Étude du 14/11 : le son est lu par tranches de 20 s ; chaque tranche
    est lue avec 1 s de plus de chaque côté, et les empreintes se suivent
    sans trou ni doublon (une toutes les 20 ms)."""
    import sys

    class Modele:
        def extract_features(self, x, num_layers):
            a = x.a  # 1 × échantillons
            n = (a.shape[1] - 400) // 320 + 1
            debut = a[0, : n * 320 : 320]  # l'empreinte = le premier échantillon de sa tranche
            return [_FauxTorch.T(np.stack([debut, debut], axis=1)[None])], None

    monkeypatch.setitem(sys.modules, "torch", _FauxTorch)
    monkeypatch.setitem(sys.modules, "torchaudio", object())
    monkeypatch.setattr(club_hearing, "_model", Modele())
    son = np.arange(RATE * 45, dtype=np.float32)
    empreintes = club_hearing.embed(son)
    assert len(empreintes) == pytest.approx(len(son) / 320, abs=2)
    assert np.array_equal(empreintes[:, 0], son[: len(empreintes) * 320 : 320])


def test_un_long_time_compte_une_fois():
    """Seb, 14/11 : un grand « Tiiime » de plus d'1 s donnait deux « Time »
    (deux pics de volume) ; tant que le son ne retombe pas, c'est un seul cri."""
    from session_clips.club_hearing import peaks

    calme, cri = [0.0] * 20, [30.0, 40.0, 35.0, 30.0] + [32.0] * 20 + [41.0, 33.0, 30.0]
    # Le plus fort de chaque cri : le 41 dB, à la 24e tranche du cri.
    assert peaks(calme + cri + calme + cri + calme) == [20 + 24, 20 + len(cri) + 20 + 24]


def test_le_cri_entier():
    """Étude du 14/11 : un Hajime ou un long Tiiime était coupé à 0,6 s.
    Le cri va jusqu'à ce que le son retombe de 12 dB, entre 0,3 et 1,5 s."""
    from session_clips.club_hearing import bounds

    volumes = [0.0] * 10 + [20.0] * 16 + [30.0] + [20.0] * 3 + [0.0] * 10
    assert bounds(volumes, 26) == (0.5, 1.5)
    assert bounds([0.0] * 10 + [30.0] + [0.0] * 10, 10) == pytest.approx((0.375, 0.675))
    long = [0.0] * 5 + [30.0] * 60 + [0.0] * 5
    debut, fin = bounds(long, 30)
    assert fin - debut == pytest.approx(1.5)
