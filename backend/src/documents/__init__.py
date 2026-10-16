"""Module « documents » : dossiers et fichiers, rangés en arborescence dans
trois espaces (Public, Privé, Personnel), avec droits hérités, statuts,
versions et corbeille.

Développé dans Contretemps pour devenir tel quel le module `documents`
d'AppBase (voir appbase/spec/modules/documents.md et
documents-phase-contretemps.md, §1 « Règles pour rester extractible ») :

- identifiants en anglais, textes d'interface en français ;
- **ne connaît pas Contretemps** : tout ce dont il a besoin (qui appelle,
  ses groupes, les saisons) passe par les ports de `ports.py`, branchés
  dans `documents_contretemps/adapter.py` ;
- vocabulaire générique : organisation (l'école), membre (un compte),
  groupe (un rôle ou un cours), période (une saison).
"""

from .models import DocAcl, DocActivity, DocAppVersion, DocNode, DocResponse, DocVersion, StoredFile
from .receiver import DocumentsReceiver
from .service import Documents
from .storage import LocalStorage

__all__ = [
    "DocAcl",
    "DocActivity",
    "DocAppVersion",
    "DocNode",
    "DocResponse",
    "DocVersion",
    "Documents",
    "DocumentsReceiver",
    "LocalStorage",
    "StoredFile",
]
