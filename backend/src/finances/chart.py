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


# Rubriques du plan comptable des associations (règlement ANC 2018-06, sur le
# PCG), proposées comme natures dans la fiche d'un compte (Seb, 10/11) : le
# numéro donne la nature de calcul (6 dépense, 7 recette, sinon hors résultat).
OFFICIAL_NATURES: tuple[tuple[str, str], ...] = (
    ("10", "Fonds propres et réserves"),
    ("11", "Report à nouveau"),
    ("12", "Résultat de l'exercice"),
    ("13", "Subventions d'investissement"),
    ("15", "Provisions pour risques et charges"),
    ("16", "Emprunts et dettes assimilées"),
    ("19", "Fonds dédiés"),
    ("20", "Immobilisations incorporelles"),
    ("21", "Immobilisations corporelles"),
    ("27", "Immobilisations financières (dépôts, cautions)"),
    ("28", "Amortissements des immobilisations"),
    ("3", "Stocks"),
    ("40", "Fournisseurs"),
    ("41", "Adhérents, usagers"),
    ("42", "Personnel"),
    ("43", "Sécurité sociale et organismes sociaux"),
    ("44", "État et collectivités publiques"),
    ("45", "Fédérations et associations affiliées"),
    ("46", "Débiteurs et créditeurs divers"),
    ("47", "Comptes d'attente"),
    ("48", "Charges et produits constatés d'avance"),
    ("50", "Placements"),
    ("51", "Banques"),
    ("53", "Caisse"),
    ("58", "Virements internes"),
    ("60", "Achats"),
    ("61", "Services extérieurs"),
    ("62", "Autres services extérieurs"),
    ("63", "Impôts, taxes et versements assimilés"),
    ("64", "Charges de personnel"),
    ("65", "Autres charges de gestion courante"),
    ("66", "Charges financières"),
    ("67", "Charges exceptionnelles"),
    ("68", "Dotations aux amortissements et provisions"),
    ("69", "Impôts sur les bénéfices"),
    ("70", "Ventes et prestations de services"),
    ("74", "Subventions d'exploitation"),
    ("75", "Cotisations, dons et autres produits de gestion"),
    ("76", "Produits financiers"),
    ("77", "Produits exceptionnels"),
    ("78", "Reprises sur amortissements et provisions"),
    ("79", "Transferts de charges"),
    ("86", "Emplois des contributions volontaires en nature"),
    ("87", "Contributions volontaires en nature"),
)


# Les classes du plan comptable (premier chiffre du numéro) : le Plan comptable
# s'affiche par classe, et une nature appartient à la classe de ses comptes (Seb, 10/11).
CLASSES: tuple[tuple[str, str], ...] = (
    ("1", "Capitaux (fonds propres, emprunts)"),
    ("2", "Immobilisations"),
    ("3", "Stocks"),
    ("4", "Tiers"),
    ("5", "Financiers (banques, caisse)"),
    ("6", "Charges"),
    ("7", "Produits"),
    ("8", "Contributions volontaires en nature"),
)


def official_natures() -> list[dict]:
    """Les rubriques officielles pour le menu Nature : « 21 Immobilisations
    corporelles », avec leur nature de calcul."""
    def nature(prefix: str) -> str:
        return EXPENSE if prefix.startswith("6") else INCOME if prefix.startswith("7") else SUSPENSE

    return [{"prefix": p, "label": f"{p} {label}", "nature": nature(p)} for p, label in OFFICIAL_NATURES]


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


# Une remise de chèques (« REM CHQ 0012345 », « REMISE DE CHEQUES ») : la banque
# ne dit pas ce que payent les chèques, l'appli ne propose donc jamais un seul
# compte ; le trésorier la ventile (§8.10, étape 3).
_CHEQUE_DEPOSIT = re.compile(r"\bREM(ISE)?S?\b\s*(DE\s*)?CH(Q|EQ|EQUE|EQUES)\b")


def is_cheque_deposit(label: str, details: str = "") -> bool:
    return bool(_CHEQUE_DEPOSIT.search(normalize(f"{label} {details or ''}")))


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
