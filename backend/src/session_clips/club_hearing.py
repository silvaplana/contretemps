"""L'écoute du club (spec/modules/video-combats.md §5, Seb 14/11) : au lieu
de faire écrire des phrases à Whisper (qui invente des mots sur un passage
calme), on compare chaque cri de la séance aux cris enregistrés par le club
dans Fights › ⋮ › Entraîner l'écoute (voice.py).

1. Un modèle de parole déjà entraîné (wav2vec2 de torchaudio, sans mots)
   donne une empreinte du son toutes les 20 ms.
2. Un cri, enregistré ou entendu en séance, est pris en entier : autour de
   son pic de volume, jusqu'à ce que le son retombe de DIP dB (0,3 à 1,5 s).
   Les empreintes sont centrées (moins la moyenne de tous les exemples).
3. Deux cris se comparent dans l'ordre de leurs sons (DTW) : « Time » et un
   autre mot en « aï » ne se ressemblent plus seulement par leur voyelle
   (étude du 14/11).
4. Chaque mot est jugé sur le même nombre d'exemples (les plus récents) ;
   un cri est le mot le plus proche s'il dépasse un seuil et bat le 2e
   d'un écart, tous deux réglés par « Rejouer tous les essais » (voice.py).

Installé seulement dans `sparring-worker` (torchaudio), d'où les imports
dans les fonctions, comme hearing.py."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .hearing import FRAME, loudness

NOT_WORDS = ("other", "noise")  # comme voice.NOT_WORDS
WORDS = ("combattez", "time")  # comme voice.WORDS (« fight » retiré le 14/11, « combat » devenu « combattez » et « hajime » retiré le 15/11)

RATE = 16000
STEP = 0.02  # une empreinte toutes les 20 ms
SHORTEST = 0.3  # secondes : un cri dure au moins ça…
LONGEST = 1.5  # … et au plus ça (un grand « Tiiime »)
MIN_DB = 6.0  # un pic moins fort que le bruit de fond + 6 dB n'est pas un cri
GAP = 1.0  # deux cris à moins d'1 s : le plus fort
DIP = 12.0  # entre deux cris, le son retombe d'au moins 12 dB ; c'est aussi le bord d'un cri
NEIGHBOURS = 3  # la ressemblance à un mot : la moyenne de ses 3 enregistrements les plus proches
# Avant le premier rejeu (puis réglés par lui, voice.run_replays) :
MIN_SCORE = 0.3  # ressemblance au mot, de −1 à 1
MIN_MARGIN = 0.02  # avance sur le 2e mot (ou sur un faux cri déjà signalé)

_model = None
_templates: dict = {}


def embed(audio: np.ndarray) -> np.ndarray:
    """L'empreinte du son, une ligne toutes les 20 ms (wav2vec2, couche du milieu)."""
    global _model
    import torch
    import torchaudio

    if _model is None:
        _model = torchaudio.pipelines.WAV2VEC2_BASE.get_model().eval()
    # Par tranches de 20 s (un morceau de 2 min d'un coup prendrait des Go de
    # mémoire), avec 1 s de son en plus de chaque côté : un cri à cheval sur
    # deux tranches n'est pas abîmé. On garde les empreintes du milieu.
    step, pad, hop = RATE * 20, RATE, 320
    out = []
    with torch.inference_mode():
        for a in range(0, len(audio), step):
            start = max(a - pad, 0)
            part = audio[start : a + step + pad]
            if len(part) < 400:  # moins d'une empreinte
                break
            layers, _ = _model.extract_features(torch.from_numpy(np.ascontiguousarray(part)).float()[None], num_layers=8)
            first = (a - start) // hop
            out.append(layers[-1][0].numpy()[first : first + step // hop])
    return np.concatenate(out) if out else np.zeros((0, 768), np.float32)


def bounds(volumes: list[float], peak: int) -> tuple[float, float]:
    """Le cri entier autour du pic (tranche `peak`) : jusqu'à ce que le son
    retombe de DIP dB, entre SHORTEST et LONGEST secondes (début, fin)."""
    floor = volumes[peak] - DIP
    a = peak
    while a > 0 and volumes[a - 1] > floor:
        a -= 1
    b = peak + 1
    while b < len(volumes) and volumes[b] > floor:
        b += 1
    start, end = a * FRAME, b * FRAME
    if end - start < SHORTEST:
        middle = (peak + 0.5) * FRAME
        start, end = max(middle - SHORTEST / 2, 0.0), max(middle - SHORTEST / 2, 0.0) + SHORTEST
    if end - start > LONGEST:  # le plus fort du cri, autour du pic
        middle = (peak + 0.5) * FRAME
        start = min(max(middle - LONGEST / 2, start), end - LONGEST)
        end = start + LONGEST
    return start, end


def _part(features: np.ndarray, start: float, end: float) -> np.ndarray:
    a = max(int(start / STEP), 0)
    return features[a : max(int(end / STEP), a + 1)]


def _normed(seq: np.ndarray, centre: np.ndarray) -> np.ndarray:
    x = seq - centre
    return x / (np.linalg.norm(x, axis=1, keepdims=True) + 1e-9)


def similarity(a: np.ndarray, b: np.ndarray) -> float:
    """La ressemblance de deux suites d'empreintes normées, dans l'ordre (DTW,
    coût 1 − cosinus, pas en diagonale comptés double) : de −1 à 1."""
    cost = 1.0 - a @ b.T
    n, m = cost.shape
    d = np.full((n + 1, m + 1), np.inf)
    d[0, 0] = 0.0
    for i in range(1, n + 1):
        prev, c = d[i - 1], cost[i - 1]
        # Depuis la ligne d'avant (en haut, en diagonale), puis le pas à gauche
        # (row[j] = min(x[j], row[j−1] + c[j])) d'un coup : min cumulé moins la somme.
        x = np.minimum(prev[1:] + c, prev[:-1] + 2 * c)
        total = np.cumsum(c)
        d[i, 1:] = total + np.minimum.accumulate(x - total)
    return float(1.0 - d[n, m] / (n + m))


def peaks(volumes: list[float]) -> list[int]:
    """Les tranches des cris possibles : pics d'au moins MIN_DB, à plus d'1 s
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
    return sorted(kept)


def templates(voice_dir: Path, read_audio, exclude: frozenset[str] = frozenset()) -> dict[str, list[np.ndarray]]:
    """Les empreintes des cris enregistrés (le cri entier), mot par mot
    (dossier du mot), du plus ancien au plus récent, sauf ceux de `exclude`
    (« mot/fichier » : les exemples venus du test qu'on rejoue, Seb 14/11).
    Chaque empreinte est calculée une fois par fichier."""
    out: dict[str, list[np.ndarray]] = {}
    files = [p for p in voice_dir.glob("*/*") if p.is_file() and p.parent.name in WORDS + NOT_WORDS]
    for p in sorted(files, key=lambda p: (p.stat().st_mtime, p.name)):
        if f"{p.parent.name}/{p.name}" in exclude:
            continue
        key = (str(p), p.stat().st_mtime)
        if key not in _templates:
            audio = read_audio(p)
            volumes = loudness(audio)
            _templates[key] = (
                _part(embed(audio), *bounds(volumes, int(np.argmax(volumes))))
                if len(audio) >= RATE * SHORTEST and volumes
                else None
            )
        if _templates[key] is not None and len(_templates[key]):
            out.setdefault(p.parent.name, []).append(_templates[key])
    return out


def _closeness(v: np.ndarray, examples: list[np.ndarray]) -> float:
    scores = sorted((similarity(v, e) for e in examples), reverse=True)
    return float(np.mean(scores[:NEIGHBOURS]))


def candidates(audio: np.ndarray, words: dict[str, list[np.ndarray]]) -> list[tuple[str, float, float, float, float]]:
    """Chaque cri de la séance et le mot le plus proche : (mot, moment,
    ressemblance, avance sur le 2e, volume en dB). Un cri plus proche d'un
    faux cri signalé (« other », « noise ») que d'un mot n'en est pas un."""
    names = [w for w in words if w in WORDS and words[w]]
    if not names or len(audio) < RATE * SHORTEST:
        return []
    # Même nombre d'exemples par mot (les plus récents) : sinon le mot le
    # plus enregistré gagne plus souvent (étude du 14/11 : Time ×30, Combat ×6).
    n = min(len(words[w]) for w in names)
    groups = {w: words[w][-n:] for w in names}
    wrong = [e for k in NOT_WORDS for e in words.get(k, [])]
    every = [e for g in groups.values() for e in g] + wrong
    centre = np.concatenate(every).mean(axis=0)
    groups = {w: [_normed(e, centre) for e in g] for w, g in groups.items()}
    wrong = [_normed(e, centre) for e in wrong]
    volumes = loudness(audio)
    features = embed(audio)
    out = []
    for i in peaks(volumes):
        start, end = bounds(volumes, i)
        seq = _part(features, start, end)
        if not len(seq):
            continue
        v = _normed(seq, centre)
        scores = sorted(((_closeness(v, g), w) for w, g in groups.items()), reverse=True)
        score, word = scores[0]
        rivals = [s for s, _w in scores[1:]] + ([_closeness(v, wrong)] if wrong else [])
        margin = score - max(rivals) if rivals else 1.0
        db = round(float(volumes[i]), 1)
        out.append((word, round(start, 1), round(score, 3), round(margin, 3), db))
    return out


def pick(found: list, min_score: float = MIN_SCORE, min_margin: float = MIN_MARGIN) -> list[tuple[str, float, float, float]]:
    """Les cris retenus, au format des cris : (mot, moment, ressemblance de 0 à 1, volume en dB)."""
    return [(w, t, round(max(s, 0.0), 2), db) for w, t, s, m, db in found if s >= min_score and m >= min_margin]


NEAR_SCORE = 0.10  # un cri « presque » : ressemblance à moins de 0,10 sous le seuil…
NEAR_MARGIN = 0.5  # … et avance d'au moins la moitié de l'écart demandé


def pick_with_near(found: list, min_score: float = MIN_SCORE, min_margin: float = MIN_MARGIN) -> list[tuple]:
    """Les cris retenus, puis les « presque » (Seb, 15/11 : gris pointillé dans
    la frise), marqués d'un 5e élément True ; ils ne comptent pas pour la découpe
    (lab.kept). Le bruit, loin du seuil, n'est pas gardé."""
    out: list[tuple] = []
    for w, t, s, m, db in found:
        if s >= min_score and m >= min_margin:
            out.append((w, t, round(max(s, 0.0), 2), db))
        elif s >= min_score - NEAR_SCORE and m >= min_margin * NEAR_MARGIN:
            out.append((w, t, round(max(s, 0.0), 2), db, True))
    return out


def hear_club(audio: np.ndarray, words: dict[str, list[np.ndarray]], min_score: float = MIN_SCORE,
              min_margin: float = MIN_MARGIN) -> list[tuple[str, float, float, float]]:
    """Les cris de la séance qui ressemblent aux cris enregistrés."""
    return pick(candidates(audio, words), min_score, min_margin)
