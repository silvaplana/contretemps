"""Calcul des droits du module documents (src/documents/access.py), sans
base : chemins et droits fabriqués à la main."""

from documents.access import effective_level
from documents.models import DocAcl, DocNode
from documents.ports import DEFAULT_PRIVATE_EDITORS, Member


def membre(person_id=1, admin=False, groups=(), superuser=False):
    return Member(
        person_id=person_id, org_id=1, display_name="X", is_admin=admin, is_superuser=superuser,
        has_personal_space=True, groups=frozenset(groups),
    )


def dossier(i, restricted=False, system_kind=None, period_id=None):
    return DocNode(id=i, restricted=restricted, system_kind=system_kind, period_id=period_id)


def droit(node_id, qui, niveau, type_="group"):
    return DocAcl(node_id=node_id, principal_type=type_, principal_id=qui, level=niveau)


def niveau(m, space, path, acl=None, owner=None, fermees=frozenset()):
    return effective_level(m, space, owner, path, acl or {}, DEFAULT_PRIVATE_EDITORS, set(fermees))


PROF = membre(2, groups={"role:professeur"})
ELEVE = membre(3, groups={"role:eleve", "course:7"})
ADMIN = membre(4, admin=True, groups={"role:admin"})
SUPERUSER = membre(5, superuser=True)


def test_defauts_des_racines():
    assert niveau(ELEVE, "public", []) == "view"
    assert niveau(ELEVE, "private", [dossier(1)]) is None
    assert niveau(PROF, "private", [dossier(1)]) == "edit"
    assert niveau(ADMIN, "private", [dossier(1)]) == "manage"


def test_heritage_par_ajout():
    a, b = dossier(1), dossier(2)
    acl = {1: [droit(1, "course:7", "view")]}
    assert niveau(ELEVE, "private", [a, b], acl) == "view"
    # Un droit plus bas ajoute, ne retire jamais.
    acl[2] = [droit(2, "3", "edit", "member")]
    assert niveau(ELEVE, "private", [a, b], acl) == "edit"
    assert niveau(PROF, "private", [a, b], acl) == "edit"


def test_dossier_restreint_arrete_l_heritage():
    a, b = dossier(1, restricted=True), dossier(2)
    assert niveau(PROF, "private", [a, b]) is None
    assert niveau(ADMIN, "private", [a, b]) == "manage"
    acl = {1: [droit(1, "2", "view", "member")]}
    assert niveau(PROF, "private", [a, b], acl) == "view"


def test_espace_personnel():
    assert niveau(PROF, "personal", [dossier(1)], owner=2) == "manage"
    assert niveau(ADMIN, "personal", [dossier(1)], owner=2) is None


def test_saison_close_plafonnee_a_la_lecture_admin_compris():
    saison = dossier(1, system_kind="period", period_id=9)
    assert niveau(ADMIN, "private", [saison, dossier(2)], fermees={9}) == "view"
    assert niveau(PROF, "private", [saison], fermees={9}) == "view"
    assert niveau(ELEVE, "private", [saison], fermees={9}) is None
    assert niveau(PROF, "private", [saison], fermees={8}) == "edit"


def test_dossier_reserve_au_groupe_et_au_superuser():
    """Financier (spec/core.md §6.1) : le trésorier et le Super User, pas
    les autres admins."""
    saison, financier = dossier(1, system_kind="period"), dossier(2, restricted=True, system_kind="reserved")
    acl = {2: [droit(2, "role:tresorier", "manage")]}
    tresorier = membre(6, admin=True, groups={"role:admin", "role:tresorier"})
    assert niveau(tresorier, "private", [saison, financier], acl) == "manage"
    assert niveau(SUPERUSER, "private", [saison, financier], acl) == "manage"
    assert niveau(ADMIN, "private", [saison, financier], acl) is None
