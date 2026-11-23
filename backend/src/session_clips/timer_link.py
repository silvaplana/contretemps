"""Le Timer télécommandé (spec/modules/video-combats.md §6.5 ter, Seb 23/11) :
un téléphone est la caméra (il filme, sonne, éclaire et tient le chrono),
un autre la télécommande (il donne les ordres et voit l'état de la caméra).

Les deux téléphones passent par le serveur, chacun toutes les demi-secondes :
la caméra dépose son état (et une petite image chaque seconde) et prend les
ordres en attente ; la télécommande dépose ses ordres et prend l'état. Une
seule caméra par organisation, comme Tournage. Rien en base : tout est en
mémoire (un seul processus d'API), perdu au redémarrage, ce qui ne gêne pas :
les téléphones redéposent tout une demi-seconde après.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

# Plus de nouvelles depuis 4 s : le lien est rompu (point gris).
GONE_AFTER = 4.0
FRAME_MAX = 200_000  # caractères de l'image (data:image/jpeg;base64,…)
ORDERS_MAX = 50


@dataclass
class _Link:
    state: dict | None = None
    frame: str | None = None
    frame_id: int = 0
    camera_seen: float = 0.0
    remote_seen: float = 0.0
    orders: list[dict] = field(default_factory=list)


_links: dict[int, _Link] = {}
_lock = threading.Lock()


def _link(org_id: int) -> _Link:
    return _links.setdefault(org_id, _Link())


def camera(org_id: int, state: dict | None, frame: str | None) -> tuple[list[dict], bool]:
    """La caméra donne son état (None : elle s'en va) ; elle reçoit les ordres
    en attente et sait si une télécommande la pilote."""
    now = time.monotonic()
    with _lock:
        link = _link(org_id)
        if state is None:
            link.state = link.frame = None
            link.camera_seen = 0.0
            link.orders = []
            return [], False
        link.state = state
        link.camera_seen = now
        if frame and len(frame) <= FRAME_MAX:
            link.frame = frame
            link.frame_id += 1
        orders, link.orders = link.orders, []
        return orders, now - link.remote_seen < GONE_AFTER


def remote(org_id: int, orders: list[dict], seen_frame: int) -> dict:
    """La télécommande donne ses ordres ; elle reçoit l'état de la caméra
    (None si aucune n'est là), et l'image si elle est plus neuve que la sienne."""
    now = time.monotonic()
    with _lock:
        link = _link(org_id)
        link.remote_seen = now
        linked = link.state is not None and now - link.camera_seen < GONE_AFTER
        if linked:
            link.orders = (link.orders + orders)[-ORDERS_MAX:]
        fresh = linked and link.frame is not None and link.frame_id != seen_frame
        return {
            "linked": linked,
            "state": link.state if linked else None,
            "frame": link.frame if fresh else None,
            "frame_id": link.frame_id,
        }


def reset() -> None:
    """Pour les tests."""
    with _lock:
        _links.clear()
