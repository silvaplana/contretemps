"""Module Essai (spec/modules/essai.md) : cours d'essai, page publique
d'inscription sans compte, QR codes, Admin > Essais."""

from .models import TrialSettings, TrialSignature, TrialStudent, TrialTerms

__all__ = ["TrialSettings", "TrialSignature", "TrialStudent", "TrialTerms"]
