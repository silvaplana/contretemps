"""Calcul du niveau d'accès d'une personne sur un nœud (spec §4.4).

Fonctions pures : elles reçoivent le chemin (de la racine au nœud) et les
droits déjà chargés, sans toucher à la base. Testées à part
(tests/test_documents_acces.py).

Règles, dans l'ordre :

0. dossier d'une saison close : plafonné à Lecture pour tout le monde ;
1. superuser : Gestion partout, dossiers réservés compris (il a tous les
   droits, spec/core.md §6.1), sauf l'espace Personnel des autres ;
   admins : pareil, sauf aussi les dossiers réservés à un groupe (§4.7 bis,
   ex. Financier, réservé aux trésoriers) ;
2. espace Personnel : le propriétaire a Gestion, personne d'autre ;
2 bis. élément d'un bac « Échanges » adressé à quelqu'un (§4.7 ter) : seuls
   qui l'a déposé et ses destinataires le voient (en plus de la règle 1) ;
3. héritage par ajout : on remonte le chemin et on garde le plus fort des
   droits trouvés pour la personne et ses groupes. Un dossier « Restreint »
   arrête la remontée : seuls ses droits (et ceux d'en dessous) comptent ;
4. défauts des racines (si aucun dossier restreint n'a arrêté la remontée) :
   Public → Lecture pour tous ; Privé → Écriture pour les rôles éditeurs.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .models import (
    LEVEL_EDIT,
    LEVEL_MANAGE,
    LEVEL_VIEW,
    SYSTEM_PERIOD,
    SYSTEM_RESERVED,
    DocAcl,
    DocNode,
)
from .ports import Member

ORDER = {None: 0, LEVEL_VIEW: 1, LEVEL_EDIT: 2, LEVEL_MANAGE: 3}


def at_least(level: str | None, needed: str) -> bool:
    return ORDER[level] >= ORDER[needed]


def strongest(levels: Iterable[str | None]) -> str | None:
    best = None
    for level in levels:
        if ORDER[level] > ORDER[best]:
            best = level
    return best


def matches(acl: DocAcl, member: Member) -> bool:
    if acl.principal_type == "member":
        return acl.principal_id == str(member.person_id)
    return acl.principal_id in member.groups


def addressed_to(node: DocNode, member: Member) -> bool:
    """Élément adressé (§4.7 ter) : `member` l'a-t-il déposé ou reçu ?"""
    if node.created_by == member.person_id:
        return True
    if node.for_type == "member":
        return node.for_id == str(member.person_id)
    return node.for_id in member.groups


def root_level(space: str, member: Member, private_editors: Sequence[str]) -> str | None:
    if space == "public":
        return LEVEL_VIEW
    if space == "private" and any(g in member.groups for g in private_editors):
        return LEVEL_EDIT
    return None


def closed_period(path: Sequence[DocNode], closed_period_ids: set[int]) -> bool:
    return any(n.system_kind == SYSTEM_PERIOD and n.period_id in closed_period_ids for n in path)


def effective_level(
    member: Member,
    space: str,
    owner_person_id: int | None,
    path: Sequence[DocNode],
    acl_by_node: dict[int, list[DocAcl]],
    private_editors: Sequence[str],
    closed_period_ids: set[int],
) -> str | None:
    """Niveau de `member` sur le dernier nœud de `path` (chemin depuis la
    racine de l'espace ; vide = la racine elle-même)."""
    level = _level_without_lock(member, space, owner_person_id, path, acl_by_node, private_editors)
    if level is not None and not member.writes_closed_periods and closed_period(path, closed_period_ids):
        return LEVEL_VIEW
    return level


def _level_without_lock(member, space, owner_person_id, path, acl_by_node, private_editors):
    if space == "personal":
        if owner_person_id == member.person_id:
            return LEVEL_MANAGE
        return None
    if member.is_superuser:
        return LEVEL_MANAGE
    reserve = any(n.system_kind == SYSTEM_RESERVED for n in path)
    if member.is_admin and not reserve:
        return LEVEL_MANAGE
    adresse = next((n for n in path if n.for_id), None)
    if adresse is not None and not addressed_to(adresse, member):
        return None
    found: list[str | None] = []
    stopped = False
    for node in reversed(path):
        found += [a.level for a in acl_by_node.get(node.id, []) if matches(a, member)]
        if node.restricted:
            stopped = True
            break
    if not stopped:
        found.append(root_level(space, member, private_editors))
    return strongest(found)
