"""Lecture d'une vidéo de séance et détection des personnes et de leurs
postures avec YOLO pose (Ultralytics, licence AGPL : voir la spec §7).

Installé seulement dans le conteneur `sparring-worker` (backend/Dockerfile.sparring),
d'où les imports dans la fonction : le backend, lui, ne charge jamais YOLO.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

from .signals import Frame, Pose

SAMPLES_PER_SECOND = 5  # assez pour des gestes tenus une seconde, 6 fois moins de calcul qu'à 30 i/s
MIN_PERSON_CONFIDENCE = 0.4
MODEL = os.environ.get("SPARRING_MODEL", "yolo11n-pose.pt")


def detect(video_path: Path) -> Iterator[Frame]:
    import cv2
    from ultralytics import YOLO

    model = YOLO(MODEL)
    capture = cv2.VideoCapture(str(video_path))
    fps = capture.get(cv2.CAP_PROP_FPS) or 30.0
    step = max(1, round(fps / SAMPLES_PER_SECOND))
    index = 0
    try:
        while True:
            if not capture.grab():
                break
            if index % step == 0:
                ok, image = capture.retrieve()
                if not ok:
                    break
                result = model(image, verbose=False)[0]
                people = []
                if result.keypoints is not None and result.boxes is not None:
                    for points, confidence in zip(result.keypoints.data.tolist(), result.boxes.conf.tolist()):
                        if confidence >= MIN_PERSON_CONFIDENCE:
                            people.append(Pose([tuple(p) for p in points]))
                yield Frame(t=index / fps, people=people)
            index += 1
    finally:
        capture.release()
