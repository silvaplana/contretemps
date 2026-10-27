"""Enregistrement des modules (spec/core.md §9 bis).

Chaque module se présente par un `MODULE = Module(...)` dans son propre
`module.py` (ou dans `<module>_contretemps/module.py` quand c'est l'appli qui
le relie à Contretemps). L'appli liste ses modules dans `app/modules.py` ;
`app/main.py` les vérifie puis les monte dans l'ordre de cette liste.
"""

from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace

from fastapi import FastAPI
from groups import rights


@dataclass(frozen=True)
class Role:
    """Un rôle qu'un module ajoute aux fiches (ex. « Accès au Financier »).
    Pas encore lu par le core : les rôles restent ceux de comptes/roles.py
    tant que l'étude « adhérents par saison » n'est pas codée."""

    key: str
    label: str


@dataclass(frozen=True)
class Right:
    """Un droit qu'un module ouvre (spec/core.md §5.3), ex.
    `Right("finances.access", "Accès au Financier")` : le core en fait un
    groupe 🔒 au nom du droit, contrôlé par `comptes.roles.has_right`."""

    key: str
    label: str


@dataclass(frozen=True)
class Module:
    key: str  # identifiant stable, en anglais
    label: str  # nom à l'écran
    # mount(app, core) : monte les routes du module et range ses services dans
    # `core` (ex. core.documents_client) pour l'appli et les modules suivants.
    mount: Callable[[FastAPI, SimpleNamespace], None]
    requires: tuple[str, ...] = ()  # modules à monter avant celui-ci
    roles: tuple[Role, ...] = ()
    rights: tuple[Right, ...] = ()
    # actions(core) : les actions que le module ouvre à l'assistant (son
    # actions.py, spec/modules/assistant-ia.md §3), une fois monté.
    actions: Callable[[SimpleNamespace], list] | None = None


def check(modules: list[Module]) -> None:
    """Refuse de démarrer si un module est en double ou si un module dont un
    autre a besoin n'est pas plus haut dans la liste."""
    vus: set[str] = set()
    for module in modules:
        if module.key in vus:
            raise RuntimeError(f"Module « {module.key} » listé deux fois dans app/modules.py.")
        manquants = [cle for cle in module.requires if cle not in vus]
        if manquants:
            raise RuntimeError(
                f"Le module « {module.key} » a besoin de {', '.join(manquants)} : "
                "à placer plus haut dans app/modules.py."
            )
        vus.add(module.key)


def actions(modules: list[Module], core: SimpleNamespace) -> dict[str, list]:
    """Les actions de l'assistant de chaque module, dans l'ordre de la liste."""
    return {module.key: module.actions(core) for module in modules if module.actions}


def mount_all(app: FastAPI, modules: list[Module], core: SimpleNamespace) -> None:
    """Monte les modules dans l'ordre et retient à quel module appartient
    chaque route, pour répondre « introuvable » quand le module est éteint
    dans l'organisation de l'appelant (activation.py)."""
    check(modules)
    app.state.module_of_route = {}
    for module in modules:
        for right in module.rights:
            rights.declare(right.key, right.label)
        avant = len(app.router.routes)
        module.mount(app, core)
        for route in app.router.routes[avant:]:
            app.state.module_of_route[id(route)] = module.key
