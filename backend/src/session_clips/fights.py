"""Repérer les combats dans une vidéo de séance (spec/modules/video-combats.md
§5, étape 2) à partir des gestes de chaque image (signals.py).

Début : au moins deux personnes lèvent le poing. Fin : le salut, sinon le X,
sinon la zone vide quelques secondes, sinon le poing levé suivant ou la fin de la
vidéo. Les durées sont des premiers réglages, à revoir sur la vidéo de test.
"""

from __future__ import annotations

from dataclasses import dataclass

from .signals import Frame, is_fist_up, is_x, salute_in

START_HOLD = 1.5  # secondes de poing levé pour lancer un combat
END_HOLD = 0.6  # secondes de salut ou de X pour le finir
EMPTSTART_HOLD = 4.0  # secondes de zone vide pour le finir
MIN_FIGHT = 10.0  # un combat plus court est ignoré (poing levé puis X aussitôt)
MARGIN = 1.0  # secondes gardées après la fin

# Motifs affichés dans « À vérifier » (vocabulaire de l'écran, pas technique).
REASON_NO_END = "La fin du combat n'a pas été repérée : vérifiez la fin du clip."


@dataclass
class Fight:
    start: float
    end: float
    fighters: int  # combien ont levé le poing : 2 au combat, 1 à n en danse
    check_reason: str | None = None


def find_fights(frames: list[Frame]) -> list[Fight]:
    fights: list[Fight] = []
    current: Fight | None = None
    start_since = end_since = emptstart_since = None
    start_count = 0

    def close(end: float, reason: str | None = None) -> None:
        nonlocal current
        if current is not None and end - current.start >= MIN_FIGHT:
            current.end = end
            current.check_reason = reason
            fights.append(current)
        current = None

    for frame in frames:
        t = frame.t
        raising = sum(1 for p in frame.people if is_fist_up(p))
        if raising >= 2:
            if start_since is None:
                start_since, start_count = t, raising
            start_count = max(start_count, raising)
            if t - start_since >= START_HOLD and (current is None or current.start < start_since):
                close(start_since)  # un nouveau poing levé termine le combat en cours
                current = Fight(start=start_since, end=t, fighters=start_count)
        else:
            start_since = None
        if current is None:
            continue

        ending = salute_in(frame) or any(is_x(p) for p in frame.people)
        if ending and t - current.start > START_HOLD:
            end_since = t if end_since is None else end_since
            if t - end_since >= END_HOLD:
                close(t + MARGIN)
                end_since = None
                continue
        else:
            end_since = None

        if not frame.people:
            emptstart_since = t if emptstart_since is None else emptstart_since
            if t - emptstart_since >= EMPTSTART_HOLD:
                close(emptstart_since)
                emptstart_since = None
        else:
            emptstart_since = None

    if current is not None and frames:
        close(frames[-1].t, REASON_NO_END)
    return fights
