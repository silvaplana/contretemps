"""Qui est qui ? (spec/modules/video-combats.md §5, étape 3, Seb 17/11).

Le worker relit chaque combat découpé d'une séance, suit ses deux
combattants et garde de chacun sa tenue (couleurs du haut et du bas), son
visage quand on le voit (empreinte SFace) et une petite image. Les
combattants de la séance sont regroupés par personne ; le coach dit qui est
chaque personne, et les combats où elle apparaît reçoivent ce nom. Une
personne pas encore nommée est comparée aux personnes nommées des autres
séances : l'appli propose un nom.

Tout tient dans `<dossier de l'école>/people/<séance>.json`, sans table.
OpenCV, YOLO et NumPy ne sont importés que dans les fonctions du worker
(conteneur `sparring-worker`) : le backend, qui nomme et propose, n'en a pas
besoin.
"""

from __future__ import annotations

import base64
import json
import os
import traceback
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from saisons.portee import toutes_saisons
from videos.stockage import DOSSIER_VIDEOS_LIVE, dossier_ecole

from .models import Clip, ClipParticipant, ClipSession, Piece
from .signals import Pose

if TYPE_CHECKING:
    import numpy as np

PER_SECOND = 2  # images lues par seconde de combat
SAME = 0.35  # sous cette distance, deux combattants sont la même personne
PROPOSE = 0.30  # sous cette distance, on propose le nom d'une autre séance
FACE_SAME = 0.45  # deux visages qui se ressemblent au moins autant : « même visage »
FACE_FULL = 0.6  # ressemblance de visages qui compte pour une distance nulle
MAX_FACES = 8  # visages gardés par combattant
FACE_SCORE = 0.6  # certitude minimale de YuNet qu'il y a un visage
MIN_SAMPLES = 3  # images en dessous desquelles un combattant est ignoré
BINS = (8, 3, 3)  # teinte, saturation, luminosité
OUTSIDER = "outsider"

NOSE, L_EAR, R_EAR = 0, 3, 4
L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_KNEE, R_KNEE = 5, 6, 11, 12, 13, 14
CONFIDENT = 0.4

FACES_DIR = Path(os.environ.get("SPARRING_FACES_DIR", str(DOSSIER_VIDEOS_LIVE.parent / "models" / "faces")))
_ZOO = "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models"
FACE_MODELS = {
    "yunet.onnx": f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "sface.onnx": f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec.onnx",
}


@dataclass
class Fighter:
    """Un combattant d'un combat, tel que la vidéo le montre."""

    outfit: np.ndarray  # histogramme du haut puis du bas, chacun de somme 1
    face: np.ndarray | None  # empreinte du visage, de norme 1
    shirt: str  # couleurs médianes, « #rrggbb »
    short: str
    image: str | None  # petite image en data URL


# --- Distances ---


def distance(a_outfit, a_face, b_outfit, b_face) -> float:
    """0 = la même personne à coup sûr, 1 = rien à voir (listes ou tableaux)."""
    d = 1.0 - sum(min(x, y) for x, y in zip(a_outfit, b_outfit)) / 2
    if a_face is not None and b_face is not None:
        sim = _dot(a_face, b_face)
        d = (d + min(max((FACE_FULL - sim) / FACE_FULL, 0.0), 1.0)) / 2
    return d


def _dot(a, b) -> float:
    return float(sum(x * y for x, y in zip(a, b)))


def _mean_outfit(outfits: list[np.ndarray]) -> np.ndarray:
    import numpy as np

    m = np.mean(outfits, axis=0)
    half = m.size // 2
    return np.concatenate([_unit_sum(m[:half]), _unit_sum(m[half:])])


def _unit_sum(v: np.ndarray) -> np.ndarray:
    import numpy as np

    total = v.sum()
    return v / total if total > 0 else v


def _mean_face(faces: list[np.ndarray]) -> np.ndarray | None:
    import numpy as np

    if not faces:
        return None
    m = np.mean(faces, axis=0)
    norm = np.linalg.norm(m)
    return m / norm if norm > 0 else None


def group(fighters: list[tuple[int, Fighter]]) -> list[int]:
    """Regroupe les combattants (combat, combattant) par personne : renvoie
    le numéro de personne (0, 1…) de chacun. Les deux groupes les plus
    proches fusionnent tant que leur distance moyenne est sous SAME ; deux
    combattants d'un même combat ne sont jamais la même personne."""
    import numpy as np

    n = len(fighters)
    d = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            a, b = fighters[i][1], fighters[j][1]
            d[i, j] = d[j, i] = distance(a.outfit, a.face, b.outfit, b.face)
    groups = [[i] for i in range(n)]
    while True:
        best = None
        for gi in range(len(groups)):
            for gj in range(gi + 1, len(groups)):
                clips_i = {fighters[k][0] for k in groups[gi]}
                if any(fighters[k][0] in clips_i for k in groups[gj]):
                    continue
                avg = float(np.mean([d[a, b] for a in groups[gi] for b in groups[gj]]))
                if avg < SAME and (best is None or avg < best[0]):
                    best = (avg, gi, gj)
        if best is None:
            break
        _, gi, gj = best
        groups[gi] += groups.pop(gj)
    # Numérotés dans l'ordre d'apparition.
    groups.sort(key=min)
    out = [0] * n
    for number, g in enumerate(groups):
        for k in g:
            out[k] = number
    return out


# --- Couleurs ---

_HUES = [(15, "rouge"), (40, "orange"), (70, "jaune"), (165, "vert"), (260, "bleu"), (290, "violet"), (345, "rose"), (361, "rouge")]


def colour_name(hex_colour: str) -> str:
    r, g, b = (int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5))
    high, low = max(r, g, b), min(r, g, b)
    if high < 0.25:
        return "noir"
    saturation = (high - low) / high
    if saturation < 0.2:
        return "blanc" if high > 0.75 else "gris"
    if high == low:
        hue = 0.0
    elif high == r:
        hue = (60 * (g - b) / (high - low)) % 360
    elif high == g:
        hue = 60 * (b - r) / (high - low) + 120
    else:
        hue = 60 * (r - g) / (high - low) + 240
    return next(name for limit, name in _HUES if hue < limit)


def outfit_label(shirt: str, short: str) -> str:
    return f"Haut {colour_name(shirt)}, bas {colour_name(short)}"


def _hist(hsv: np.ndarray) -> np.ndarray:
    import numpy as np

    pixels = hsv.reshape(-1, 3).astype(float)
    h, _ = np.histogramdd(pixels, bins=BINS, range=((0, 180), (0, 256), (0, 256)))
    return _unit_sum(h.flatten())


def _hex(bgr: np.ndarray) -> str:
    import numpy as np

    b, g, r = (int(x) for x in np.median(bgr.reshape(-1, 3), axis=0))
    return f"#{r:02x}{g:02x}{b:02x}"


# --- Lecture d'une image (OpenCV) ---


def _point(pose: Pose, i: int):
    x, y, c = pose.keypoints[i]
    return (x, y) if c >= CONFIDENT else None


def body_box(pose: Pose) -> tuple[float, float, float, float] | None:
    points = [(x, y) for x, y, c in pose.keypoints if c >= CONFIDENT]
    if len(points) < 5:
        return None
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def regions(pose: Pose) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int]] | None:
    """Les rectangles du haut (épaules → hanches) et du bas (hanches →
    genoux), resserrés pour ne garder que le tissu."""
    need = [_point(pose, i) for i in (L_SHOULDER, R_SHOULDER, L_HIP, R_HIP, L_KNEE, R_KNEE)]
    if None in need:
        return None
    ls, rs, lh, rh, lk, rk = need

    def box(top, bottom):
        x0, x1 = min(p[0] for p in top + bottom), max(p[0] for p in top + bottom)
        y0, y1 = sum(p[1] for p in top) / 2, sum(p[1] for p in bottom) / 2
        if y1 - y0 < 6:
            return None
        width = max(x1 - x0, (y1 - y0) * 0.4)
        cx = (x0 + x1) / 2
        return (
            int(cx - width * 0.35),
            int(y0 + (y1 - y0) * 0.15),
            int(cx + width * 0.35),
            int(y1 - (y1 - y0) * 0.15),
        )

    top, bottom = box([ls, rs], [lh, rh]), box([lh, rh], [lk, rk])
    return (top, bottom) if top and bottom else None


def outfit(image: np.ndarray, pose: Pose) -> tuple[np.ndarray, str, str] | None:
    import cv2
    import numpy as np

    found = regions(pose)
    if found is None:
        return None
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    height, width = image.shape[:2]
    hists, colours = [], []
    for x0, y0, x1, y1 in found:
        x0, x1, y0, y1 = max(x0, 0), min(x1, width), max(y0, 0), min(y1, height)
        if x1 - x0 < 4 or y1 - y0 < 4:
            return None
        hists.append(_hist(hsv[y0:y1, x0:x1]))
        colours.append(_hex(image[y0:y1, x0:x1]))
    return np.concatenate(hists), colours[0], colours[1]


class Faces:
    """YuNet (repérer un visage) et SFace (son empreinte), d'OpenCV.
    Téléchargés une fois ; sans eux, on s'en tient à la tenue."""

    def __init__(self) -> None:
        self.detector = self.recognizer = None
        try:
            import cv2

            FACES_DIR.mkdir(parents=True, exist_ok=True)
            for name, url in FACE_MODELS.items():
                path = FACES_DIR / name
                if not path.exists():
                    tmp = path.with_suffix(".part")
                    urllib.request.urlretrieve(url, tmp)
                    tmp.rename(path)
            self.detector = cv2.FaceDetectorYN.create(str(FACES_DIR / "yunet.onnx"), "", (160, 160), FACE_SCORE)
            self.recognizer = cv2.FaceRecognizerSF.create(str(FACES_DIR / "sface.onnx"), "")
        except Exception:
            traceback.print_exc()
            print("Visages : modèles absents, reconnaissance par la tenue seulement.")

    def feature(self, image: np.ndarray, pose: Pose) -> np.ndarray | None:
        """L'empreinte du visage de la personne, ou None s'il ne se voit pas."""
        if self.detector is None:
            return None
        import cv2

        head = [p for p in (_point(pose, i) for i in range(NOSE, R_EAR + 1)) if p is not None]
        shoulders = [_point(pose, i) for i in (L_SHOULDER, R_SHOULDER)]
        if len(head) < 3 or None in shoulders:
            return None
        cx, cy = sum(p[0] for p in head) / len(head), sum(p[1] for p in head) / len(head)
        size = max(abs(shoulders[0][0] - shoulders[1][0]), max(p[0] for p in head) - min(p[0] for p in head), 12) * 1.6
        height, width = image.shape[:2]
        x0, y0 = int(max(cx - size, 0)), int(max(cy - size, 0))
        x1, y1 = int(min(cx + size, width)), int(min(cy + size, height))
        if x1 - x0 < 16 or y1 - y0 < 16:
            return None
        crop = image[y0:y1, x0:x1]
        # Lue à sa taille ; agrandie seulement si elle est petite (un visage
        # de 35 px au fond de la salle).
        if min(crop.shape[:2]) < 160:
            scale = 160 / min(crop.shape[:2])
            crop = cv2.resize(crop, (int(crop.shape[1] * scale), int(crop.shape[0] * scale)))
        self.detector.setInputSize((crop.shape[1], crop.shape[0]))
        _, faces = self.detector.detect(crop)
        if faces is None or len(faces) == 0:
            return None
        best = max(faces, key=lambda f: f[-1])
        import numpy as np

        aligned = self.recognizer.alignCrop(crop, best)
        v = self.recognizer.feature(aligned).flatten().astype(float)
        norm = np.linalg.norm(v)
        return v / norm if norm > 0 else None


def _two_biggest(people: list[Pose]) -> list[tuple[Pose, tuple]]:
    boxes = [(p, body_box(p)) for p in people]
    boxes = [(p, b) for p, b in boxes if b is not None]
    boxes.sort(key=lambda x: (x[1][2] - x[1][0]) * (x[1][3] - x[1][1]), reverse=True)
    return boxes[:2]


def _centre(box) -> tuple[float, float]:
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def follow(frames: list[list[tuple[Pose, tuple]]]) -> list[list[tuple[int, Pose, tuple]]]:
    """Rattache les deux combattants d'une image à ceux de la précédente
    (0 ou 1) par la position de leur centre."""
    last: list[tuple[float, float] | None] = [None, None]
    out = []
    for people in frames:
        if len(people) == 2 and None not in last:
            a, b = (_centre(box) for _, box in people)
            straight = _dist(a, last[0]) + _dist(b, last[1])
            crossed = _dist(a, last[1]) + _dist(b, last[0])
            order = [0, 1] if straight <= crossed else [1, 0]
        elif len(people) == 1 and None not in last:
            c = _centre(people[0][1])
            order = [0] if _dist(c, last[0]) <= _dist(c, last[1]) else [1]
        else:
            order = list(range(len(people)))
        frame = []
        for slot, (pose, box) in zip(order, people):
            last[slot] = _centre(box)
            frame.append((slot, pose, box))
        out.append(frame)
    return out


def _dist(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def read_clip(path: Path, faces: Faces) -> list[Fighter | None]:
    """Les deux combattants d'un combat découpé (None : pas assez vu)."""
    import numpy as np  # noqa: F401
    import cv2
    from ultralytics import YOLO

    from .detector import MODEL

    model = YOLO(MODEL)
    capture = cv2.VideoCapture(str(path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / PER_SECOND))
    images, seen = [], []
    index = 0
    try:
        while capture.grab():
            if index % step == 0:
                ok, image = capture.retrieve()
                if not ok:
                    break
                result = model(image, verbose=False)[0]
                people = []
                if result.keypoints is not None:
                    people = [Pose([tuple(p) for p in points]) for points in result.keypoints.data.tolist()]
                images.append(image)
                seen.append(_two_biggest(people))
            index += 1
    finally:
        capture.release()

    samples: list[dict] = [{"outfits": [], "faces": [], "shirts": [], "shorts": [], "best": None} for _ in range(2)]
    for image, frame in zip(images, follow(seen)):
        for slot, pose, box in frame:
            s = samples[slot]
            found = outfit(image, pose)
            if found is None:
                continue
            s["outfits"].append(found[0])
            s["shirts"].append(found[1])
            s["shorts"].append(found[2])
            area = (box[2] - box[0]) * (box[3] - box[1])
            if s["best"] is None or area > s["best"][0]:
                s["best"] = (area, image, box)
            if len(s["faces"]) < MAX_FACES:
                face = faces.feature(image, pose)
                if face is not None:
                    s["faces"].append(face)
    out: list[Fighter | None] = []
    for s in samples:
        if len(s["outfits"]) < MIN_SAMPLES:
            out.append(None)
            continue
        out.append(
            Fighter(
                outfit=_mean_outfit(s["outfits"]),
                face=_mean_face(s["faces"]),
                shirt=_median_hex(s["shirts"]),
                short=_median_hex(s["shorts"]),
                image=_crop(*s["best"][1:]),
            )
        )
    return out


def _median_hex(colours: list[str]) -> str:
    import numpy as np

    rgb = np.median([[int(c[i : i + 2], 16) for i in (1, 3, 5)] for c in colours], axis=0)
    return "#" + "".join(f"{int(x):02x}" for x in rgb)


def _crop(image: np.ndarray, box) -> str | None:
    import numpy as np

    import cv2

    x0, y0, x1, y1 = box
    margin = (y1 - y0) * 0.12
    height, width = image.shape[:2]
    x0, y0 = int(max(x0 - margin, 0)), int(max(y0 - margin, 0))
    x1, y1 = int(min(x1 + margin, width)), int(min(y1 + margin, height))
    crop = image[y0:y1, x0:x1]
    if crop.size == 0:
        return None
    scale = 200 / crop.shape[0]
    crop = cv2.resize(crop, (max(1, int(crop.shape[1] * scale)), 200))
    ok, data = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return "data:image/jpeg;base64," + base64.b64encode(data.tobytes()).decode() if ok else None


# --- La séance ---


def _path(org_id: int, session_id: int) -> Path:
    return dossier_ecole(org_id) / "people" / f"{session_id}.json"


def load(org_id: int, session_id: int) -> dict | None:
    path = _path(org_id, session_id)
    try:
        return json.loads(path.read_text()) if path.exists() else None
    except ValueError:
        return None


def save(org_id: int, session_id: int, data: dict) -> None:
    path = _path(org_id, session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":")))


def forget(org_id: int, session_id: int) -> None:
    _path(org_id, session_id).unlink(missing_ok=True)


def _clip_ids(db: Session, session_id: int) -> list[int]:
    return list(db.scalars(select(Clip.id).where(Clip.session_id == session_id).order_by(Clip.position, Clip.id)))


def sessions_to_recognize(db: Session) -> list[ClipSession]:
    """Les séances découpées (vidéo envoyée ou caméra de la salle) dont les
    combats n'ont pas encore été relus, ou ont changé depuis."""
    with toutes_saisons(db):
        candidates = db.scalars(
            select(ClipSession)
            .where(
                ClipSession.status == "ready",
                exists().where(Clip.session_id == ClipSession.id),
                ClipSession.raw_video_id.is_not(None) | exists().where(Piece.session_id == ClipSession.id),
            )
            .order_by(ClipSession.id)
        ).all()
    out = []
    for session in candidates:
        data = load(session.org_id, session.id)
        if data is None or data.get("clips") != _clip_ids(db, session.id):
            out.append(session)
    return out


Reader = Callable[[Path, Faces], list[Fighter | None]]


def recognize(db: Session, videos, session: ClipSession, faces: Faces, read: Reader = read_clip) -> int:
    """Relit les combats de la séance et regroupe leurs combattants par
    personne ; renvoie le nombre de personnes. Les noms déjà donnés suivent
    la personne qui leur ressemble le plus."""
    clip_ids = _clip_ids(db, session.id)
    fighters: list[tuple[int, int, Fighter]] = []
    with toutes_saisons(db):
        for clip in db.scalars(select(Clip).where(Clip.id.in_(clip_ids))):
            video = videos.get(db, clip.video_id)
            if video is None:
                continue
            for slot, fighter in enumerate(read(DOSSIER_VIDEOS_LIVE / video.lien_fichier, faces)):
                if fighter is not None:
                    fighters.append((clip.id, slot, fighter))
    numbers = group([(c, f) for c, _, f in fighters])
    persons: list[dict] = []
    for number in range(max(numbers, default=-1) + 1):
        mine = [f for (_, _, f), n in zip(fighters, numbers) if n == number]
        face = _mean_face([f.face for f in mine if f.face is not None])
        persons.append(
            {
                "n": number + 1,
                "outfit": [round(x, 4) for x in _mean_outfit([f.outfit for f in mine]).tolist()],
                "face": [round(x, 4) for x in face.tolist()] if face is not None else None,
                "shirt": mine[0].shirt,
                "short": mine[0].short,
                "image": next((f.image for f in mine if f.image), None),
                "member": None,
            }
        )
    places: dict[str, list[int | None]] = {str(c): [None, None] for c in clip_ids}
    for (clip_id, slot, _), number in zip(fighters, numbers):
        places[str(clip_id)][slot] = number + 1

    old = load(session.org_id, session.id)
    if old:
        for previous in old["persons"]:
            if previous.get("member") is None:
                continue
            best = _closest(previous, [p for p in persons if p["member"] is None])
            if best is not None and best[0] < SAME:
                best[1]["member"] = previous["member"]
    data = {"clips": clip_ids, "persons": persons, "places": places}
    save(session.org_id, session.id, data)
    for person in persons:
        if person["member"] is not None:
            _fill(db, data, person["n"], person["member"], None)
    db.commit()
    return len(persons)


def failed(session: ClipSession, db: Session) -> None:
    """Une relecture ratée n'est pas retentée en boucle : la séance est
    notée relue, sans personne."""
    save(session.org_id, session.id, {"clips": _clip_ids(db, session.id), "persons": [], "places": {}, "failed": True})


def _person_distance(a: dict, b: dict) -> float:
    return distance(a["outfit"], a["face"], b["outfit"], b["face"])


def _closest(person: dict, others: list[dict]):
    scored = [(_person_distance(person, o), o) for o in others]
    return min(scored, key=lambda x: x[0]) if scored else None


def _fill(db: Session, data: dict, number: int, who, before) -> None:
    """Met `who` (un membre, OUTSIDER ou None) aux places de la personne :
    une place vide, ou qui avait son ancien nom `before`. Un nom mis à la
    main n'est jamais écrasé."""
    for clip_id, places in data["places"].items():
        if number not in places:
            continue
        rows = {
            r.slot: r
            for r in db.scalars(select(ClipParticipant).where(ClipParticipant.clip_id == int(clip_id)))
        }
        if not rows:
            continue
        current = {s: (OUTSIDER if r.outsider else r.person_id) for s, r in rows.items()}
        if who not in (None, OUTSIDER) and who in current.values():
            continue
        slot = places.index(number)
        if slot not in rows or current[slot] not in (None, before):
            free = [s for s, v in current.items() if v is None]
            if who is None or not free:
                continue
            slot = free[0]
        rows[slot].outsider = who == OUTSIDER
        rows[slot].person_id = who if who not in (None, OUTSIDER) else None


def name(db: Session, session: ClipSession, number: int, who) -> dict:
    """Le coach dit qui est la personne `number` (un membre, OUTSIDER ou
    None pour retirer le nom)."""
    data = load(session.org_id, session.id)
    person = next((p for p in (data or {}).get("persons", []) if p["n"] == number), None)
    if person is None:
        raise LookupError("Personne introuvable")
    # Une même personne peut avoir été coupée en deux (lumière, tenue
    # changée) : deux personnes peuvent recevoir le même nom.
    before = person["member"]
    person["member"] = who
    _fill(db, data, number, who, before)
    save(session.org_id, session.id, data)
    db.commit()
    return data


def proposals(db: Session, session: ClipSession, data: dict) -> dict[int, tuple[int, str]]:
    """Pour chaque personne pas encore nommée, le membre qui lui ressemble le
    plus dans les autres séances de l'école, et pourquoi."""
    named_here = {p["member"] for p in data["persons"]}
    known: list[tuple[dict, ClipSession]] = []
    folder = dossier_ecole(session.org_id) / "people"
    with toutes_saisons(db):
        for path in folder.glob("*.json") if folder.exists() else []:
            if path.stem == str(session.id) or not path.stem.isdigit():
                continue
            other = db.get(ClipSession, int(path.stem))
            if other is None or other.org_id != session.org_id:
                continue
            other_data = load(session.org_id, other.id) or {}
            for p in other_data.get("persons", []):
                if isinstance(p.get("member"), int) and p["member"] not in named_here:
                    known.append((p, other))
    out: dict[int, tuple[int, str]] = {}
    for person in data["persons"]:
        if person["member"] is not None or not known:
            continue
        scored = sorted(((_person_distance(person, p), p, s) for p, s in known), key=lambda x: x[0])
        d, best, _ = scored[0]
        if d >= PROPOSE:
            continue
        member = best["member"]
        same_member = [(p, s) for dd, p, s in scored if p["member"] == member and dd < PROPOSE]
        faces = [s for p, s in same_member if _face_sim(person, p) >= FACE_SAME]
        if faces:
            days = " et le ".join(_day(s) for s in sorted({s.held_on: s for s in faces}.values(), key=lambda s: s.held_on)[-2:])
            out[person["n"]] = (member, f"même visage, vu le {days}")
        else:
            out[person["n"]] = (member, f"même tenue le {_day(same_member[0][1])}")
    return out


def _face_sim(a: dict, b: dict) -> float:
    if a["face"] is None or b["face"] is None:
        return -1.0
    return _dot(a["face"], b["face"])


def _day(session: ClipSession) -> str:
    return f"{session.held_on.day}/{session.held_on.month}"
