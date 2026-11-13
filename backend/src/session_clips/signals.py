"""Gestes repérés sur une image (spec/modules/video-combats.md §5) : le poing
levé ou les poings touchés en l'air avant un combat, la poignée de main ou
les bras croisés à la fin.

Une personne = ses 17 points du corps au format COCO (ceux que donne YOLO
pose), chacun `(x, y, confiance)` en pixels, `y` vers le bas. Seuils réglés
le 12/11/2026 sur deux vidéos de Seb (combattants de profil : la longueur du
buste sert d'unité, la largeur d'épaules est trop petite de profil).
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
    """Les bras croisés (Seb, 13/11 : « chacun croise les bras devant soi,
    au milieu ou plus ou moins haut ») : les deux poignets au-dessus des
    hanches, chacun passé du côté de l'autre bras. Face à la caméra
    seulement (épaules écartées d'au moins un tiers de buste) : de profil,
    une garde a l'air croisée. Plus de X en l'air : des poignets
    rapprochés sans se croiser, c'est la garde."""
    points = [pose.point(i) for i in (L_SHOULDER, R_SHOULDER, L_ELBOW, R_ELBOW, L_WRIST, R_WRIST)]
    unit = torso(pose)
    if None in points or not unit:
        return False
    l_sh, r_sh, _, _, l_wr, r_wr = points
    hips = l_sh[1] + unit
    if l_wr[1] >= hips or r_wr[1] >= hips:
        return False
    facing = abs(l_sh[0] - r_sh[0]) >= unit / 3
    return facing and (l_wr[0] - r_wr[0]) * (l_sh[0] - r_sh[0]) < 0


def _mean(points):
    points = [p for p in points if p is not None]
    if not points:
        return None
    return sum(p[0] for p in points) / len(points), sum(p[1] for p in points) / len(points)


def torso(pose: Pose) -> float | None:
    """Hauteur du buste (épaules → hanches) : l'unité des distances."""
    shoulders = _mean([pose.point(L_SHOULDER), pose.point(R_SHOULDER)])
    hips = _mean([pose.point(L_HIP), pose.point(R_HIP)])
    if shoulders is None or hips is None or hips[1] <= shoulders[1]:
        return None
    return hips[1] - shoulders[1]


def hips_x(pose: Pose) -> float | None:
    hips = _mean([pose.point(L_HIP), pose.point(R_HIP)])
    return hips[0] if hips else None


def _upright(pose: Pose) -> bool:
    """Debout et droit : les épaules au-dessus des hanches (pas penché dans
    un corps-à-corps)."""
    shoulders = _mean([pose.point(L_SHOULDER), pose.point(R_SHOULDER)])
    unit = torso(pose)
    return unit is not None and abs(shoulders[0] - hips_x(pose)) < 0.4 * unit


def _wrists(pose: Pose):
    return [w for w in (pose.point(L_WRIST), pose.point(R_WRIST)) if w is not None]


def _joined(a: Pose, b: Pose, reach: float):
    """Les poignets de l'une et de l'autre qui se touchent, ou None."""
    unit = min(torso(a) or 0, torso(b) or 0)
    if not unit:
        return None
    for wa in _wrists(a):
        for wb in _wrists(b):
            if ((wa[0] - wb[0]) ** 2 + (wa[1] - wb[1]) ** 2) ** 0.5 < reach * unit:
                return wa, wb
    return None


def _shoulders_top(pose: Pose) -> float | None:
    points = [p for p in (pose.point(L_SHOULDER), pose.point(R_SHOULDER)) if p]
    return min(p[1] for p in points) if points else None


def are_touching_fists_up(a: Pose, b: Pose) -> bool:
    """Les poings qui se touchent, bras vers le haut : un poignet de chacun,
    au-dessus de ses épaules, tout près de celui de l'autre. Bras bien levés
    (poignets à un demi-buste au-dessus des épaules), les poignets peuvent
    être un peu plus loin : les poings dépassent des poignets (vidéos de Seb
    en plein cadre, 12/11/2026)."""
    unit = min(torso(a) or 0, torso(b) or 0)
    if not unit:
        return False
    for reach, lift in ((0.35, 0.0), (0.65, 0.4)):
        for wa in _wrists(a):
            for wb in _wrists(b):
                close = ((wa[0] - wb[0]) ** 2 + (wa[1] - wb[1]) ** 2) ** 0.5 < reach * unit
                if close and wa[1] < _shoulders_top(a) - lift * unit and wb[1] < _shoulders_top(b) - lift * unit:
                    return True
    return False


def are_shaking_hands(a: Pose, b: Pose) -> bool:
    """La poignée de main, bras vers le bas : deux personnes debout et
    droites, mains jointes sous les épaules. Qu'elles restent immobiles est
    vérifié sur la durée (fights.py) : un accrochage en plein combat bouge."""
    if not (_upright(a) and _upright(b)):
        return False
    joined = _joined(a, b, 0.65)  # les mains dépassent des poignets
    return joined is not None and joined[0][1] > _shoulders_top(a) and joined[1][1] > _shoulders_top(b)


def main_pair(frame: Frame) -> list[Pose]:
    """Les deux plus grands corps de l'image : un reflet dans une vitre ou
    quelqu'un au fond est plus petit."""
    people = [p for p in frame.people if torso(p)]
    return sorted(people, key=torso, reverse=True)[:2]
