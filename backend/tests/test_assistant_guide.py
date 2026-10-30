"""Le guide de l'appli pour l'assistant (assistant/guide.py, spec/modules/
assistant-ia.md §6) : chaque module qui a des écrans a son guide.md, et
l'assistant ne lit que ceux des modules allumés auxquels la personne a droit."""

from app.main import MODULES, core_guide
from assistant.guide import guide_action
from comptes import Comptes
from ecoles import Ecoles

# Sans écran à elles : leurs écrans sont décrits par le guide d'un autre
# (Saisons et Notes de frais dans Admin et Profil ou le Financier, Vidéos
# dans les Chorégraphies), ou n'existent pas (l'assistant lui-même).
SANS_GUIDE = {"seasons", "videos", "assistant", "expense_notes"}


def test_chaque_module_avec_des_ecrans_a_son_guide():
    assert {m.key for m in MODULES if not m.guide} == SANS_GUIDE
    assert "Admin › École" in core_guide


def test_guide_selon_l_ecole_et_les_droits(db_session):
    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    guide = guide_action(MODULES, lambda db, org_id: {"messaging"}, core_guide)

    def lire(module):
        return guide.read(db_session, admin, ecole.id, guide.params(module=module))

    liste = lire(None)
    assert "Admin et Profil" in liste and "Présence" in liste
    assert "Messagerie" not in liste  # éteinte dans l'école
    assert "Financier" not in liste  # pas le droit d'accès au Financier
    assert lire("admin").startswith("Guide du module Admin et Profil")
    assert "Présent" in lire("Présence")


def test_outils_d_un_module_eteint_refuses(db_session, monkeypatch):
    """Les lectures écrites dans l'assistant mais propres à un module
    (présences, Docs…) suivent l'interrupteur du module, comme ses actions."""
    from types import SimpleNamespace

    from app.main import assistant_client
    from assistant.assistant import MODULE_DES_OUTILS, OUTILS

    noms = {o.get("name") for o in OUTILS}
    assert set(MODULE_DES_OUTILS) <= noms
    assert set(MODULE_DES_OUTILS.values()) <= {m.key for m in MODULES}

    ecole = Ecoles().create(db_session, nom="Contretemps", code_postal="83330")
    admin = Comptes().create(db_session, ecole_id=ecole.id, role="admin", nom="Dho", prenom="Julia")
    monkeypatch.setattr(assistant_client, "modules_eteints", lambda db, org_id: {"presence"})
    membre = SimpleNamespace(org_id=ecole.id, person_id=admin.id)
    texte, carte = assistant_client._executer(db_session, membre, "presences", {}, admin)
    assert carte is None and "n'est pas utilisé" in texte
