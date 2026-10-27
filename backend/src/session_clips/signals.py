"""Gestes repérés sur une image (spec/modules/video-combats.md §5) : le poing
levé avant un combat, le salut ou le X à la fin.

Une personne = ses 17 points du corps au format COCO (ceux que donne YOLO
pose), chacun `(x, y, confiance)` en pixels, `y` vers le bas. Les seuils
sont des premiers réglages, à revoir sur la vidéo de test.
"""

from __future__ import annotations

from dataclasses import dataclass

NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST, L_HIP, R_HIP = 0, 5, 6, 7, 8, 9, 10, 11, 12
MIN_CONFIDENCE = 0.3

Keypoint = tuple[float, float, float]


@dataclass
class Pose:
    keypoints: list[Keypoint]

    def point(self, i: int) -> tuple[float, float] | None:
        x, y, c = self.keypoints[i]
        return (x, y) if c >= MIN_CONFIDENCE else None

    def shoulder_width(self) -> float | None:
        left, right = self.point(L_SHOULDER), self.point(R_SHOULDER)
        if left is None or right is None:
            return None
        return max(abs(left[0] - right[0]), 1.0)


@dataclass
class Frame:
    t: float  # secondes depuis le début de la vidéo
    people: list[Pose]


def _arms(pose: Pose):
    """Les points utiles aux gestes des bras, ou None s'il en manque un."""
    points = [pose.point(i) for i in (NOSE, L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST)]
    width = pose.shoulder_width()
    if None in points or width is None:
        return None
    return (*points, width)


def _bent(shoulder, elbow, wrist) -> bool:
    """Le bras plié : angle au coude entre 45° et 135°."""
    a = (shoulder[0] - elbow[0], shoulder[1] - elbow[1])
    b = (wrist[0] - elbow[0], wrist[1] - elbow[1])
    norms = (a[0] ** 2 + a[1] ** 2) ** 0.5 * (b[0] ** 2 + b[1] ** 2) ** 0.5
    if norms == 0:
        return False
    cos = (a[0] * b[0] + a[1] * b[1]) / norms
    return -0.71 < cos < 0.71


def is_fist_up(pose: Pose) -> bool:
    """Un poing levé, bras plié : poing au-dessus de la tête, coude au moins
    à hauteur d'épaule. En garde, les coudes restent sous les épaules ; les
    bras croisés au-dessus de la tête sont le X, pas un poing levé."""
    arms = _arms(pose)
    if arms is None or is_x(pose):
        return False
    nose, l_sh, r_sh, l_el, r_el, l_wr, r_wr, width = arms
    return any(
        wrist[1] < nose[1] and elbow[1] <= shoulder[1] + 0.25 * width and _bent(shoulder, elbow, wrist)
        for shoulder, elbow, wrist in ((l_sh, l_el, l_wr), (r_sh, r_el, r_wr))
    )


def is_x(pose: Pose) -> bool:
    """Les avant-bras croisés au-dessus de la tête : poignets au-dessus du
    nez, croisés (le gauche passé à droite) ou presque l'un sur l'autre."""
    arms = _arms(pose)
    if arms is None:
        return False
    nose, l_sh, r_sh, _l_el, _r_el, l_wr, r_wr, width = arms
    if not (l_wr[1] < nose[1] and r_wr[1] < nose[1]):
        return False
    crossed = (l_wr[0] - r_wr[0]) * (l_sh[0] - r_sh[0]) < 0
    return crossed or abs(l_wr[0] - r_wr[0]) < 0.5 * width


def _standing(pose: Pose) -> bool:
    shoulders = [pose.point(i) for i in (L_SHOULDER, R_SHOULDER)]
    hips = [pose.point(i) for i in (L_HIP, R_HIP)]
    width = pose.shoulder_width()
    if None in shoulders or None in hips or width is None:
        return False
    torso = (hips[0][1] + hips[1][1]) / 2 - (shoulders[0][1] + shoulders[1][1]) / 2
    return torso > 1.2 * width


def are_saluting(a: Pose, b: Pose) -> bool:
    """Deux personnes debout, les mains jointes : un poignet de l'une tout
    près d'un poignet de l'autre."""
    if not (_standing(a) and _standing(b)):
        return False
    width = min(a.shoulder_width(), b.shoulder_width())
    wrists_a = [p for p in (a.point(L_WRIST), a.point(R_WRIST)) if p]
    wrists_b = [p for p in (b.point(L_WRIST), b.point(R_WRIST)) if p]
    return any(
        ((pa[0] - pb[0]) ** 2 + (pa[1] - pb[1]) ** 2) ** 0.5 < 0.5 * width for pa in wrists_a for pb in wrists_b
    )


def salute_in(frame: Frame) -> bool:
    people = frame.people
    return any(are_saluting(a, b) for i, a in enumerate(people) for b in people[i + 1 :])
