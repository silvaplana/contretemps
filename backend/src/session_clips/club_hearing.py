"""L'écoute du club (spec/modules/video-combats.md §5, Seb 14/11) : au lieu
de faire écrire des phrases à Whisper (qui invente des mots sur un passage
calme), on compare chaque cri de la séance aux cris enregistrés par le club
dans Fights › ⋮ › Entraîner l'écoute (voice.py).

1. Un modèle de parole déjà entraîné (wav2vec2 de torchaudio, sans mots)
   donne une empreinte du son toutes les 20 ms.
2. Chaque cri, enregistré ou entendu en séance, est résumé par l'empreinte
   moyenne de ses 0,6 s les plus fortes.
3. Un pic de volume de la séance est un cri s'il ressemble plus à un mot
   enregistré qu'aux passages sans cri de la même vidéo (pris au hasard).
   Sa note « sûr » est sa ressemblance au mot (0 à 1).

Installé seulement dans `sparring-worker` (torchaudio), d'où les imports
dans les fonctions, comme hearing.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .hearing import FRAME, loudness

NOT_WORDS = ("other", "noise")  # comme voice.NOT_WORDS

RATE = 16000
WINDOW = 0.6  # secondes autour du pic : un cri bref
MIN_DB = 6.0  # un pic moins fort que le bruit de fond + 6 dB n'est pas un cri
GAP = 1.0  # deux cris à moins d'1 s : le plus fort
DIP = 12.0  # entre deux cris, le son retombe d'au moins 12 dB
NEIGHBOURS = 3  # la ressemblance à un mot : la moyenne de ses 3 enregistrements les plus proches
BACKGROUND = 40  # passages sans cri tirés au hasard dans la vidéo

_model = None
_templates: dict = {}


def embed(audio: np.ndarray) -> np.ndarray:
    """L'empreinte du son, une ligne toutes les 20 ms (wav2vec2, couche du milieu)."""
    global _model
    import torch
    import torchaudio

    if _model is None:
        _model = torchaudio.pipelines.WAV2VEC2_BASE.get_model().eval()
    # Par tranches de 20 s : un morceau de 2 min d'un coup prendrait des Go de mémoire.
    step = RATE * 20
    out = []
    with torch.inference_mode():
        for a in range(0, len(audio), step):
            part = audio[a : a + step]
            if len(part) < 400:  # moins d'une empreinte
                break
            layers, _ = _model.extract_features(torch.from_numpy(np.ascontiguousarray(part)).float()[None], num_layers=8)
            out.append(layers[-1][0].numpy())
    return np.concatenate(out)


def _summary(features: np.ndarray, start: float, length: float) -> np.ndarray:
    """L'empreinte moyenne d'un passage, normée (pour comparer par produit scalaire)."""
    step = 0.02
    a = max(int(start / step), 0)
    b = max(int((start + length) / step), a + 1)
    v = features[a:b].mean(axis=0)
    return v / (np.linalg.norm(v) + 1e-9)


def _loudest(volumes: list[float], length: float = WINDOW) -> float:
    """Le début du passage de `length` secondes le plus fort."""
    n = max(int(length / FRAME), 1)
    if len(volumes) <= n:
        return 0.0
    sums = np.convolve(volumes, np.ones(n), "valid")
    return float(np.argmax(sums)) * FRAME


def peaks(volumes: list[float]) -> list[float]:
    """Les moments des cris possibles : pics d'au moins MIN_DB, à plus d'1 s
    l'un de l'autre, et un seul par cri : deux pics comptent pour deux cris
    seulement si le son retombe d'au moins DIP dB entre eux (Seb, 14/11 : un
    grand « Tiiime » donnait deux « Time »)."""
    order = sorted(range(len(volumes)), key=lambda i: volumes[i], reverse=True)
    kept: list[int] = []

    def apart(i: int, k: int) -> bool:
        a, b = sorted((i, k))
        return abs(i - k) * FRAME >= GAP and min(volumes[a : b + 1]) < volumes[i] - DIP

    for i in order:
        if volumes[i] < MIN_DB:
            break
        if all(apart(i, k) for k in kept):
            kept.append(i)
    return sorted(k * FRAME for k in kept)


def templates(voice_dir: Path, read_audio, exclude: frozenset[str] = frozenset()) -> dict[str, list[np.ndarray]]:
    """Les empreintes des cris enregistrés, mot par mot (dossier du mot), sauf
    ceux de `exclude` (« mot/fichier » : les exemples venus du test qu'on
    rejoue, Seb 14/11). Chaque empreinte est calculée une fois par fichier."""
    out: dict[str, list[np.ndarray]] = {}
    for p in sorted(p for p in voice_dir.glob("*/*") if p.is_file()):
        if f"{p.parent.name}/{p.name}" in exclude:
            continue
        key = (str(p), p.stat().st_mtime)
        if key not in _templates:
            audio = read_audio(p)
            _templates[key] = (
                _summary(embed(audio), _loudest(loudness(audio)), WINDOW) if len(audio) >= RATE * WINDOW else None
            )
        if _templates[key] is not None:
            out.setdefault(p.parent.name, []).append(_templates[key])
    return out


def _closeness(v: np.ndarray, examples: list[np.ndarray]) -> float:
    scores = sorted((float(v @ e) for e in examples), reverse=True)
    return float(np.mean(scores[:NEIGHBOURS]))


def hear_club(audio: np.ndarray, words: dict[str, list[np.ndarray]]) -> list[tuple[str, float, float, float]]:
    """Les cris de la séance qui ressemblent aux cris enregistrés :
    (mot, moment, ressemblance de 0 à 1, volume en dB)."""
    # « other » (un autre mot) et « noise » (rien) : les réponses Mauvais et
    # Inventé après un test (voice.answer_test, Seb 14/11), pas des mots à trouver.
    wrong = [e for k in NOT_WORDS for e in words.get(k, [])]
    words = {k: e for k, e in words.items() if k not in NOT_WORDS}
    if not words or len(audio) < RATE * WINDOW:
        return []
    volumes = loudness(audio)
    features = embed(audio)
    duration = len(audio) / RATE
    found = peaks(volumes)
    # Les passages sans cri : au hasard, loin des pics (toujours les mêmes pour une vidéo).
    rng = np.random.default_rng(len(audio))
    background = [
        _summary(features, t, WINDOW)
        for t in rng.uniform(0, max(duration - WINDOW, 0), BACKGROUND * 2)
        if all(abs(t - p) > GAP for p in found)
    ][:BACKGROUND]
    out = []
    for t in found:
        start = max(t - WINDOW / 2, 0.0)
        v = _summary(features, start, WINDOW)
        scores = {word: _closeness(v, examples) for word, examples in words.items()}
        word, score = max(scores.items(), key=lambda x: x[1])
        if background and score <= _closeness(v, background):
            continue  # ressemble plus à un passage sans cri
        if wrong and score <= _closeness(v, wrong):
            continue  # ressemble plus à un faux cri déjà signalé
        db = round(float(max(volumes[int(start / FRAME) : int((start + WINDOW) / FRAME) + 1])), 1)
        out.append((word, round(start, 1), round(max(score, 0.0), 2), db))
    return out
