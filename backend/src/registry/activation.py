"""Modules allumés ou éteints pour chaque organisation (spec/core.md §9 bis.3).

Le core le vérifie une fois pour toutes les routes d'un module
(`route_enabled`, branchée sur l'appli entière dans app/main.py) : aucun
module ne peut l'oublier.
"""

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from db import get_db

from .models import OrgModule


def disabled(db: Session, org_id: int) -> set[str]:
    """Les modules éteints dans cette organisation (tous allumés par défaut)."""
    return set(
        db.scalars(select(OrgModule.module_key).where(OrgModule.org_id == org_id, OrgModule.enabled.is_(False)))
    )


def listing(db: Session, org_id: int, modules: list) -> list[dict]:
    off = disabled(db, org_id)
    return [
        {"key": m.key, "label": m.label, "requires": list(m.requires), "enabled": m.key not in off}
        for m in modules
    ]


def set_enabled(db: Session, org_id: int, modules: list, key: str, enabled: bool) -> None:
    """Allumer un module allume aussi ceux dont il a besoin ; on n'éteint pas
    un module dont un module allumé a besoin (ValueError). Rien n'est effacé."""
    by_key = {m.key: m for m in modules}
    if key not in by_key:
        raise LookupError(key)
    off = disabled(db, org_id)
    if enabled:
        keys, todo = set(), [key]
        while todo:
            k = todo.pop()
            if k not in keys:
                keys.add(k)
                todo.extend(by_key[k].requires)
    else:
        besoin = [m.label for m in modules if key in m.requires and m.key not in off]
        if besoin:
            raise ValueError(f"{', '.join(besoin)} a besoin de ce module : éteignez d'abord {', '.join(besoin)}.")
        keys = {key}
    for k in keys:
        row = db.get(OrgModule, (org_id, k))
        if row is None:
            row = OrgModule(org_id=org_id, module_key=k)
            db.add(row)
        row.enabled = enabled
    db.commit()


def route_enabled(request: Request, db: Session = Depends(get_db)) -> None:
    """Une route d'un module éteint dans l'organisation de l'appelant répond
    « introuvable ». Passe après la session (comptes/rbac.py :
    session_requise) : sans appelant (route publique) ou pour le Super User,
    qui n'appartient à aucune organisation, rien n'est vérifié ici."""
    key = getattr(request.app.state, "module_of_route", {}).get(id(request.scope.get("route")))
    appelant = getattr(request.state, "appelant", None)
    if key is None or appelant is None or appelant.ecole_id is None:
        return
    if key in disabled(db, appelant.ecole_id):
        raise HTTPException(status_code=404, detail="Introuvable")
