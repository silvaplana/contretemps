"""Repérer les sons du Timer de Fights dans la bande son (spec/modules/
video-combats.md §5, Seb 14/11) : la cloche d'un coup au début du round
(« Cloche du Timer », signe de début) et les trois coups de la fin (« Trois
coups du Timer », signe de fin).

Pas de modèle : le Timer joue toujours les mêmes fichiers (copiés dans
timer_sounds/ depuis frontend/src/modules/session-clips/sons/). Leurs notes
sont fixes (980, 1166, 1960 et 2950 Hz depuis la cloche « Salle de club »
du 21/11 ; une séance filmée avec l'ancienne cloche n'y est plus reconnue). On suit la force de ces
quatre notes toutes les 20 ms, et on compare 1,5 s de la séance à la même
chose dans chaque fichier (corrélation de 0 à 1). Le motif d'un coup et
celui de trois coups ne se ressemblent pas, même sous des voix."""

from __future__ import annotations

from functools import cache
from pathlib import Path

import numpy as np

from .hearing import _peak, loudness

RATE = 16000
HOP = 320  # 20 ms
WINDOW = 1024
PARTIALS = (980.0, 1166.0, 1960.0, 2950.0)
LENGTH = 75  # 1,5 s comparées
RINGING = 4.5  # secondes : la cloche sonne encore, ce n'est pas un nouveau son
MIN_SCORE = 0.38  # essais du 14/11 : vraies cloches ≥ 0,41 sous des voix, rien d'autre au-dessus de 0,30
SOUNDS = Path(__file__).parent / "timer_sounds"
KINDS = {"bell": "cloche-debut-de-round.mp3", "bells": "cloche-fin-de-round.mp3"}


def _notes(audio: np.ndarray) -> np.ndarray:
    """La force (dB) de chaque note de la cloche, toutes les 20 ms : 4 lignes."""
    n = 1 + max(len(audio) - WINDOW, 0) // HOP
    idx = np.arange(WINDOW)[None, :] + HOP * np.arange(n)[:, None]
    spec = np.abs(np.fft.rfft(audio[idx] * np.hanning(WINDOW), axis=1)) ** 2
    freqs = np.fft.rfftfreq(WINDOW, 1 / RATE)
    return np.array([10 * np.log10(spec[:, (freqs > f - 25) & (freqs < f + 25)].mean(axis=1) + 1e-12) for f in PARTIALS])


def _centred(x: np.ndarray) -> np.ndarray:
    x = x - x.mean(axis=-1, keepdims=True)
    return x / (np.sqrt((x**2).sum(axis=(-2, -1), keepdims=True)) + 1e-9)


@cache
def _template(kind: str) -> np.ndarray:
    from .hearing import _audio

    audio = _audio(SOUNDS / KINDS[kind])
    notes = _notes(np.concatenate([np.zeros(WINDOW, np.float32), audio]))
    start = int(np.argmax(notes[1] > notes[1].max() - 20))  # l'attaque du premier coup
    return _centred(notes[:, start : start + LENGTH])


def scores(audio: np.ndarray) -> dict[str, np.ndarray]:
    """Pour chaque son du Timer, sa ressemblance avec 1,5 s commençant à chaque tranche de 20 ms."""
    notes = _notes(audio)
    count = notes.shape[1] - LENGTH + 1
    if count <= 0:
        return {kind: np.zeros(0) for kind in KINDS}
    windows = np.lib.stride_tricks.sliding_window_view(notes, LENGTH, axis=1)[:, :count]  # 4 x n x L
    windows = _centred(np.transpose(windows, (1, 0, 2)))  # n x 4 x L
    return {kind: (windows * _template(kind)).sum(axis=(1, 2)) for kind in KINDS}


def bells(audio: np.ndarray) -> list[tuple[str, float, float, float]]:
    """« bell » (début du round) et « bells » (fin), au format des cris :
    (son, moment, ressemblance de 0 à 1, volume en dB)."""
    by_kind = scores(audio)
    if not len(by_kind["bell"]):
        return []
    best = np.maximum(by_kind["bell"], by_kind["bells"])
    volumes = loudness(audio)
    # Les passages qui ressemblent à un son du Timer, d'un seul tenant ; dans chaque groupe, le premier pic presque aussi
    # bon que le meilleur : le début du son (la fin de trois coups, qui sonne
    # encore, ressemble aussi à un coup seul).
    above = [i for i in range(len(best)) if best[i] >= MIN_SCORE]
    groups: list[list[int]] = []
    for i in above:
        if groups and (i - groups[-1][-1]) * HOP / RATE < 1.0:
            groups[-1].append(i)
        else:
            groups.append([i])
    out: list[tuple[str, float, float, float]] = []
    for group in groups:
        top = max(best[i] for i in group)
        i = next(i for i in group if best[i] >= 0.85 * top and (i + 1 >= len(best) or best[i] >= best[i + 1]))
        t = i * HOP / RATE
        if out and t - out[-1][1] < RINGING:
            continue  # la cloche d'avant qui sonne encore
        j = max(range(max(i - 3, 0), min(i + 4, len(best))), key=lambda k: best[k])  # à 60 ms près
        kind = "bell" if by_kind["bell"][j] >= by_kind["bells"][j] else "bells"
        out.append((kind, round(t, 1), round(float(best[i]), 2), _peak(volumes, t, t)))
    return out
