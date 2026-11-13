"""Repérer les combats dans une vidéo de séance (spec/modules/video-combats.md
§5) à partir des gestes de chaque image (signals.py).

D'abord les signes, tenus un moment (`find_signs`) : au début, les poings
touchés en l'air ou un cri (« Go ! », « Fight ! », « Hajime ! ») ; à la fin, la
poignée de main (immobiles), les bras croisés ou le « Time ! » crié. Puis les combats (`find_fights`), avec
les seuls signes cochés par le club : du signe de début au premier signe de
fin, sinon à la zone vide quelques secondes, sinon au début du combat
suivant ou à la fin de la vidéo. Durées réglées le 12/11/2026 sur deux
vidéos de Seb.
"""

from __future__ import annotations

from dataclasses import dataclass

from .signals import Frame, are_shaking_hands, are_touching_fists_up, hips_x, is_arms_up, is_x, main_pair, torso

# « go », « fight », « hajime » : crié par l'entraîneur (hearing.py ; « Fight ! » et
# « Hajime ! » ajoutés le 13/11 : « go », trop court, se confond avec « allez »).
SHOUTED_STARTS = ("go", "fight", "hajime")
START_SIGNS = ("fists_touch", "arms_up", *SHOUTED_STARTS)
END_SIGNS = ("handshake", "x", "time")  # « time » : le « Time ! » crié (hearing.py)
SIGNS = START_SIGNS + END_SIGNS
SOUNDS = (*SHOUTED_STARTS, "time")
# Un son entendu : (« go » ou « time », secondes). Un nombre seul est un
# « time » (morceaux lus avant le « Go ! », 12/11/2026).
Sound = tuple[str, float] | float
# Secondes pendant lesquelles un signe doit être tenu pour compter.
HOLD = {"fists_touch": 0.5, "arms_up": 0.5, "handshake": 0.5, "x": 0.5}  # au moins 0,5 s (Seb, 13/11)
GAP = 0.45  # une image manquée (à 5 images/s) ne coupe pas un geste
MERGE = 2.0  # deux poings touchés à moins de 2 s : un seul début
STILL = 0.3  # poignée de main : les hanches bougent de moins de 0,3 buste
END_DELAY = 1.0  # bras qui redescendent juste après le début : pas une fin
MIN_FIGHT = 5.0  # un combat plus court est ignoré (début puis fin aussitôt),
# sauf « Go ! » puis « Time ! » criés : les deux cris disent le combat (Seb, 12/11)
ECHO = 1.0  # un « go » moins d'1 s avant un « Time ! », en plein combat : ignoré
MARGIN = 1.0  # au moins 1 s gardée après le début du signe de fin (le « Time ! »)

# Motifs affichés dans « À vérifier » (vocabulaire de l'écran, pas technique).
REASON_NO_END = "La fin du combat n'a pas été repérée : vérifiez la fin du clip."


@dataclass
class Sign:
    kind: str  # une des SIGNS
    start: float
    end: float


@dataclass
class Fight:
    start: float
    end: float
    fighters: int
    check_reason: str | None = None


def _runs(frames: list[Frame], seen) -> list[tuple[int, int]]:
    """Les suites d'images où `seen(frame)` est vrai, à une image manquée près."""
    runs, first, last = [], None, None
    for i, frame in enumerate(frames):
        if seen(frame):
            if first is not None and frame.t - frames[last].t > GAP:
                runs.append((first, last))
                first = None
            first = i if first is None else first
            last = i
    if first is not None:
        runs.append((first, last))
    return runs


def _pair(frame: Frame, test) -> bool:
    pair = main_pair(frame)
    return len(pair) == 2 and test(*pair)


def _still(frames: list[Frame]) -> bool:
    """Les deux restent sur place (les hanches bougent peu)."""
    spots = [sorted(hips_x(p) for p in main_pair(f)) for f in frames if len(main_pair(f)) == 2]
    if len(spots) < 2:
        return False
    unit = min(torso(p) for p in main_pair(frames[0])) if len(main_pair(frames[0])) == 2 else 0
    return all(max(s[k] for s in spots) - min(s[k] for s in spots) < STILL * unit for k in range(2))


def find_signs(frames: list[Frame], sounds: list[Sound] = ()) -> list[Sign]:
    """Tous les signes repérés, cochés ou non : la frise du Labo les montre.
    `sounds` : les « Go ! » et « Time ! » dits (hearing.py)."""
    tests = {
        # Le « Poing levé » est retiré (Seb, 13/11) : seuls comptent les poings
        # des deux combattants qui se touchent, bras levés.
        "fists_touch": lambda f: _pair(f, are_touching_fists_up),
        # Les deux bras levés, par les deux combattants (Seb, 13/11).
        "arms_up": lambda f: _pair(f, lambda a, b: is_arms_up(a) and is_arms_up(b)),
        "handshake": lambda f: _pair(f, are_shaking_hands),
        # Bras croisés : chacun des deux (Seb, 13/11).
        "x": lambda f: _pair(f, lambda a, b: is_x(a) and is_x(b)),
    }
    signs: list[Sign] = []
    for kind, test in tests.items():
        found: list[Sign] = []
        for first, last in _runs(frames, test):
            sign = Sign(kind, frames[first].t, frames[last].t)
            if kind in START_SIGNS and found and sign.start - found[-1].end < MERGE:
                found[-1].end = sign.end
                continue
            found.append(sign)
        for sign in found:
            if sign.end - sign.start + 1e-6 < HOLD[kind]:
                continue
            if kind == "handshake" and not _still([f for f in frames if sign.start <= f.t <= sign.end]):
                continue
            if kind == "handshake" and any(  # l'autre main, baissée, pendant les poings touchés
                s.kind == "fists_touch" and s.start <= sign.end and sign.start <= s.end for s in signs
            ):
                continue
            signs.append(sign)
    signs += [Sign(kind, t, t) for kind, t in map(as_sound, sounds)]
    return sorted(signs, key=lambda s: s.start)


def as_sound(x: Sound) -> tuple[str, float]:
    return ("time", float(x)) if isinstance(x, (int, float)) else (x[0], float(x[1]))


def find_fights(frames: list[Frame], enabled: tuple[str, ...] = SIGNS, sounds: list[Sound] = ()) -> list[Fight]:
    signs = [s for s in find_signs(frames, sounds) if s.kind in enabled]
    ends = [s for s in signs if s.kind in END_SIGNS]
    starts: list[Sign] = []
    for s in (s for s in signs if s.kind in START_SIGNS):
        # Un « go » entendu juste avant un « Time ! », en plein combat : un
        # écho du « Time ! », pas un nouveau combat (Seb, séance 9, 13/11).
        if (
            s.kind in SHOUTED_STARTS
            and starts
            and not any(e.start > starts[-1].start for e in ends if e.start < s.start)
            and any(0 <= e.start - s.start < ECHO for e in ends if e.kind == "time")
        ):
            continue
        # Poings touchés puis « Go ! » : un seul début ; mais pas par-dessus
        # un « Time ! » ou un geste de fin (Seb, 13/11 : Go, Time, Go, Time).
        if (
            starts
            and s.start - starts[-1].end < MERGE
            and not any(starts[-1].start < e.start < s.start for e in ends)
        ):
            starts[-1].end = max(starts[-1].end, s.end)
            continue
        starts.append(s)
    fights: list[Fight] = []
    for i, start in enumerate(starts):
        limit = starts[i + 1].start if i + 1 < len(starts) else None
        before = lambda t: limit is None or t < limit  # noqa: E731
        # END_DELAY : des bras qui redescendent ; un « Time ! » crié compte tout de suite.
        end = next(
            (e for e in ends if e.start >= start.end + (0 if e.kind == "time" else END_DELAY) and before(e.start)), None
        )
        reason = None
        shouted = end is not None and start.kind in SHOUTED_STARTS and end.kind == "time"
        # Une zone qui a l'air vide (pièce sombre) ne finit jamais un combat (Seb, 13/11).
        if end is not None:
            stop = max(end.end, end.start + MARGIN)  # le geste de fin en entier
            if limit is not None:
                stop = min(stop, limit)  # sans mordre sur le combat suivant
        elif limit is not None:
            stop = limit
        elif start.kind in SHOUTED_STARTS:
            continue  # un « Go ! » sans fin ne fait pas de combat (Seb, 13/11 : Time, Go, Time, Go)
        else:
            stop, reason = (frames[-1].t if frames else start.end), REASON_NO_END
        if shouted or stop - start.start >= MIN_FIGHT:
            fights.append(Fight(start.start, stop, 2, reason))
    return fights


def trim(fights: list[Fight], start_skip: float, end_skip: float) -> list[Fight]:
    """Réglages du club (Seb, 12/11) : démarrer `start_skip` secondes après
    le début du signe de début, couper `end_skip` secondes avant la fin.
    À 0, les gestes restent en entier. Il reste toujours au moins 1 s."""
    out = []
    for f in fights:
        start = min(f.start + start_skip, f.end - 1)
        end = max(f.end - end_skip, start + 1)
        out.append(Fight(start, end, f.fighters, f.check_reason))
    return out
