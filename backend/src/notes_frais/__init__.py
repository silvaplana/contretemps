"""Module « notes de frais » (spec/modules/notes-de-frais.md) : chaque membre
saisit ses dépenses (photo du ticket lue par l'IA), les envoie en une note,
les trésoriers valident puis marquent remboursé.

Développé dans Contretemps pour devenir tel quel un module d'AppBase, comme
`documents` : il ne connaît pas Contretemps, tout passe par les ports de
`ports.py`, branchés dans `notes_frais_contretemps/adapter.py`.
"""

from .lecture import LecteurClaude
from .models import CategorieFrais, Depense, NoteFrais, PieceJustificative, Rib
from .ports import Membre, Organisation, Personne, Ports
from .receiver import NotesDeFraisReceiver
from .service import NotesDeFrais
from .stockage import StockageEnveloppes

__all__ = [
    "CategorieFrais",
    "Depense",
    "LecteurClaude",
    "Membre",
    "NoteFrais",
    "NotesDeFrais",
    "NotesDeFraisReceiver",
    "Organisation",
    "Personne",
    "PieceJustificative",
    "Ports",
    "Rib",
    "StockageEnveloppes",
]
