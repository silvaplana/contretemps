"""Plan comptable d'une organisation (spec/modules/financier.md §8.2) : la
liste par défaut d'une association (numéros du plan comptable associatif,
libellés courts), les mots-clés qui font proposer un compte pour une ligne
de banque, et la proposition elle-même.

La proposition ne s'écrit jamais en base : le trésorier confirme (voir
accounting.py). Deux sources, dans l'ordre : l'historique confirmé (même
libellé de banque, sans ce qui change d'une fois à l'autre → même compte),
puis les mots-clés des comptes de la bonne nature.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

from .models import EXPENSE, INCOME, SUSPENSE, THIRD_PARTY


@dataclass(frozen=True)
class DefaultAccount:
    number: str
    label: str
    nature: str
    keywords: tuple[str, ...] = ()
    event: str | None = None


# Liste par défaut d'une nouvelle organisation (courte : l'organisation
# ajoute et renomme). Les comptes de tiers et d'attente ne servent qu'au
# niveau Complet mais existent dès le départ.
DEFAULT_CHART: tuple[DefaultAccount, ...] = (
    DefaultAccount("606", "Fournitures et petit équipement", EXPENSE, ("AMAZON", "DECATHLON", "CASTORAMA", "LEROY MERLIN", "IKEA", "MATOS")),
    DefaultAccount("613", "Locations", EXPENSE, ("LOCATION", "LOYER")),
    DefaultAccount("616", "Assurances", EXPENSE, ("MAIF", "MACIF", "AXA", "ASSURANCE")),
    DefaultAccount("618", "Documentation, formation", EXPENSE, ("FORMATION",)),
    DefaultAccount("622", "Honoraires", EXPENSE, ("HONORAIRE",)),
    DefaultAccount("623", "Publicité, communication", EXPENSE, ("FLYER", "IMPRIM", "ONLINEPRINTERS", "OVH", "IONOS")),
    DefaultAccount("625", "Déplacements, réceptions", EXPENSE, ("TOTAL", "SNCF", "PEAGE", "CARREFOUR", "AUCHAN", "LECLERC")),
    DefaultAccount("626", "Frais postaux et télécom", EXPENSE, ("LA POSTE", "ORANGE", "FREE MOBILE", "SFR")),
    DefaultAccount("627", "Services bancaires", EXPENSE, ("FACT SGT", "FRAIS", "COTIS CB", "COMMISSION")),
    DefaultAccount("628", "Cotisations, licences", EXPENSE, ("LICENCE", "FFST", "FEDERATION")),
    DefaultAccount("635", "Impôts et taxes", EXPENSE, ("SACEM", "SPRE", "DGFIP", "IMPOT")),
    DefaultAccount("641", "Salaires", EXPENSE, ("SALAIRE",)),
    DefaultAccount("645", "Charges sociales", EXPENSE, ("URSSAF", "PLAN SANTE", "MUTUELLE")),
    DefaultAccount("658", "Charges diverses", EXPENSE, ()),
    DefaultAccount("706", "Cours, stages", INCOME, ("HELLOASSO", "STRIPE", "REM CHQ", "REMISE")),
    DefaultAccount("707", "Ventes, billetterie, buvette", INCOME, ("BILLET", "ENTREE", "GALA")),
    DefaultAccount("740", "Subventions", INCOME, ("SUBVENTION", "ASP AGENCE", "MAIRIE", "REGION", "DEPARTEMENT")),
    DefaultAccount("754", "Dons", INCOME, ("DON",)),
    DefaultAccount("756", "Cotisations", INCOME, ("COTISATION", "ADHESION")),
    DefaultAccount("758", "Produits divers", INCOME, ("SOUTIEN ASSO", "REMBOURSEMENT")),
    DefaultAccount("768", "Intérêts", INCOME, ("INTERET",)),
    DefaultAccount("401", "Fournisseurs", THIRD_PARTY),
    DefaultAccount("411", "Adhérents", THIRD_PARTY),
    DefaultAccount("467", "Autres tiers", THIRD_PARTY),
    DefaultAccount("471", "Compte d'attente", SUSPENSE),
)


def normalize(text: str) -> str:
    """"Intérêts  Livret" → "INTERETS LIVRET" (sans accents ni majuscules,
    espaces simples) ; même règle que categories.py."""
    decomposed = unicodedata.normalize("NFD", " ".join((text or "").split()))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).upper()


def label_key(label: str) -> str:
    """Le libellé de banque sans ce qui change d'une fois à l'autre (les
    mots avec des chiffres : date, numéro de carte) : « CARTE 26/09/26
    DECATHLON 0010 CB*9481 » → « CARTE DECATHLON CB ». Vide si rien ne reste."""
    words = [w for w in re.split(r"[\s*]+", normalize(label)) if w and not any(ch.isdigit() for ch in w)]
    return " ".join(words)


@dataclass
class Proposal:
    """Un compte proposé pour une ligne, et pourquoi (phrase à l'écran)."""

    account_id: int
    reason: str
    history: int = field(default=0)


def propose(
    accounts: list,
    label: str,
    details: str,
    amount: int,
    history: dict[str, Counter] | None = None,
) -> Proposal | None:
    """Compte proposé pour une opération. `accounts` : les comptes actifs du
    plan (objets avec id, number, label, nature, keywords) ; `history` :
    {clé de libellé: Counter(account_id)} des opérations déjà confirmées."""
    if amount == 0:
        return None
    key = label_key(label)
    if history and key and key in history:
        account_id, count = history[key].most_common(1)[0]
        if any(a.id == account_id for a in accounts):
            return Proposal(account_id, f"« {key.title()} » est allé dans ce compte {count} fois", count)
    wanted = EXPENSE if amount < 0 else INCOME
    text = normalize(f"{label} {details}")
    # Le mot-clé le plus long l'emporte (« FACT SGT » avant « FACT »).
    best: tuple[int, int, str] | None = None
    for account in accounts:
        if account.nature != wanted:
            continue
        for keyword in account.keywords or ():
            k = normalize(keyword)
            if k and k in text and (best is None or len(k) > len(best[2])):
                best = (account.id, len(k), k)
    if best is None:
        return None
    return Proposal(best[0], f"« {best[2].title()} » est un mot-clé de ce compte")
