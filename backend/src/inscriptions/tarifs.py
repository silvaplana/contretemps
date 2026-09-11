"""Calcul du tarif d'inscription (voir spec/SPEC-inscription.md et le vrai
PDF "dossier d'inscription", page "TARIFS saison 2026-2027") — pur Python,
sans DB, pour rester testable sans FastAPI/SQLAlchemy.

Palier par cours : table déterministe, même philosophie que
`eleves/import_excel.py:MAPPING_COLONNES_COURS_PAR_DEFAUT` — pas d'IA,
l'ensemble des cours est fini et connu à l'avance.

Liste des 17 cours et paliers, voir spec/SPEC.md §6.5 :
- "eveil" : palier propre, tarif fixe (pas de notion de nb de cours/semaine).
- "initiation_moyen" : Class Ini, Jazz Ini, Class Moy, Jazz Moy, Street Moyen.
- "junior_et_plus" : tous les autres (Junior/Inter/AV/Adulte/Pointes) — le
  plus élevé, "Contempo Adulte" y est rattaché par défaut faute de tarif
  adulte distinct pour l'instant (décision explicite avec l'utilisateur).
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

PALIER_PAR_COURS: dict[str, str] = {
    "Éveil": "eveil",
    "Class Ini": "initiation_moyen",
    "Jazz Ini": "initiation_moyen",
    "Class Moy": "initiation_moyen",
    "Jazz Moy": "initiation_moyen",
    "Street Moyen": "initiation_moyen",
    "Jazz Junior": "junior_et_plus",
    "Street Junior Inter": "junior_et_plus",
    "Class Inter": "junior_et_plus",
    "Jazz Inter": "junior_et_plus",
    "Pointes inter": "junior_et_plus",
    "Pointes AV": "junior_et_plus",
    "Class AV": "junior_et_plus",
    "Jazz AV": "junior_et_plus",
    "Contempo Junior": "junior_et_plus",
    "Contempo Inter avance": "junior_et_plus",
    "Contempo Adulte": "junior_et_plus",
}

# Ordre de "gravité" d'un palier vers un autre — sert au cas mixte
# (cours choisis touchant plusieurs paliers) : on retient le plus cher
# (celui du cours le plus avancé parmi les cours choisis, pas le moins
# cher).
_ORDRE_PALIERS = ["eveil", "initiation_moyen", "junior_et_plus"]

# Libellé lisible d'un palier — voir pdf.py (facture) et
# frontend-inscription/src/tarifs.js:LIBELLE_PALIER (même wording,
# gardé synchronisé à la main).
LIBELLE_PALIER: dict[str, str] = {
    "eveil": "Éveil",
    "initiation_moyen": "Initiation ou Moyen",
    "junior_et_plus": "À partir de Junior",
}

# Toujours 3 échéances par an, jamais de trimestre facturé l'été (voir
# spec/SPEC-inscription.md).
NB_TRIMESTRES = 3

ADHESION = 40.0
REDUCTION_FAMILLE = 5.0

# Éveil : tarif fixe, indépendant du nombre de cours/semaine (il n'y en a
# qu'un). Montant mensuel (payé de septembre à juin) et montant
# trimestriel (3 échéances/an) — voir dossier d'inscription, page tarifs.
_TARIF_EVEIL = {"mensuel": 36.0, "trimestriel": 110.0}

# Initiation/Moyen et Junior-et-plus : montant selon le nombre de
# cours/semaine choisis (index 0 = 1 cours/semaine). "Junior-et-plus" va
# jusqu'à 5 cours/semaine + un 6e palier "illimité" (index 5).
_BAREME_INITIATION_MOYEN = {
    "mensuel": [42.0, 50.0, 55.0],
    "trimestriel": [125.0, 150.0, 160.0],
}
_BAREME_JUNIOR_ET_PLUS = {
    "mensuel": [42.0, 55.0, 62.0, 68.0, 72.0, 75.0],
    "trimestriel": [125.0, 160.0, 180.0, 200.0, 210.0, 220.0],
}


@dataclass
class TarifResultat:
    palier: str
    nb_cours_semaine: int
    montant_adhesion: float
    montant_mensuel_septembre: float
    montant_trimestriel: float
    reduction_famille_appliquee: bool
    alerte_palier_mixte: bool


def palier_par_defaut(nom_cours: str) -> str | None:
    return PALIER_PAR_COURS.get(nom_cours)


def _tarif_pour_palier(palier: str, nb_cours: int) -> tuple[float, float]:
    """(montant_mensuel_septembre, montant_trimestriel) pour ce palier et
    ce nombre de cours/semaine. `nb_cours` au-delà du barème -> dernier
    palier connu ("illimité")."""
    if palier == "eveil":
        return _TARIF_EVEIL["mensuel"], _TARIF_EVEIL["trimestriel"]
    bareme = _BAREME_INITIATION_MOYEN if palier == "initiation_moyen" else _BAREME_JUNIOR_ET_PLUS
    index = min(max(nb_cours, 1), len(bareme["mensuel"])) - 1
    return bareme["mensuel"][index], bareme["trimestriel"][index]


def calculer_tarif(
    noms_cours: list[str], reduction_famille: bool = False
) -> TarifResultat:
    """Calcule le tarif pour les cours choisis. Si les cours touchent
    plusieurs paliers à la fois (cas rare), retient le palier le plus
    cher pour l'ensemble des cours, avec `alerte_palier_mixte=True` — le
    tarif reste informatif en phase 1 (paiement réel encore par chèque,
    toujours validé par un humain)."""
    paliers = {PALIER_PAR_COURS[nom] for nom in noms_cours if nom in PALIER_PAR_COURS}
    if not paliers:
        paliers = {"initiation_moyen"}
    palier_retenu = max(paliers, key=_ORDRE_PALIERS.index)
    alerte_palier_mixte = len(paliers) > 1

    nb_cours = len(noms_cours)
    montant_mensuel, montant_trimestriel = _tarif_pour_palier(palier_retenu, nb_cours)

    if reduction_famille:
        montant_mensuel = max(0.0, montant_mensuel - REDUCTION_FAMILLE)
        montant_trimestriel = max(0.0, montant_trimestriel - REDUCTION_FAMILLE)

    return TarifResultat(
        palier=palier_retenu,
        nb_cours_semaine=nb_cours,
        montant_adhesion=ADHESION,
        montant_mensuel_septembre=montant_mensuel,
        montant_trimestriel=montant_trimestriel,
        reduction_famille_appliquee=reduction_famille,
        alerte_palier_mixte=alerte_palier_mixte,
    )


@dataclass
class Echeance:
    montant: float
    # None = payée immédiatement (à la création du Checkout Intent) ;
    # sinon date de prélèvement (voir helloasso.py:creer_checkout_intent,
    # champ `terms`).
    date_prelevement: dt.date | None


def dates_trimestres(saison: str) -> list[dt.date]:
    """Vraies dates d'encaissement des 3 trimestres d'une saison (ex.
    "2026-2027") : 1er octobre, 1er janvier, 1er avril — mêmes dates que
    celles annoncées à la famille pour le chèque (voir
    Confirmation.jsx/FormulaireInscription.jsx, texte "encaissés en
    octobre/janvier/avril"), pour que chèque et HelloAsso restent
    cohérents entre eux."""
    annee_debut, annee_fin = (int(x) for x in saison.split("-"))
    return [
        dt.date(annee_debut, 10, 1),
        dt.date(annee_fin, 1, 1),
        dt.date(annee_fin, 4, 1),
    ]


def calculer_echeances_helloasso(
    montant_adhesion: float,
    montant_trimestriel: float,
    nb_echeances: int,
    saison: str,
    aujourdhui: dt.date | None = None,
) -> list[Echeance]:
    """1 échéance (tout maintenant) ou 3 (une par trimestre, aux vraies
    dates — voir dates_trimestres, décision utilisateur : cohérent avec
    le chèque plutôt que des dates relatives à la date d'inscription).

    L'adhésion est TOUJOURS payée immédiatement (elle ne peut jamais être
    différée à une date future chez HelloAsso, voir `initialAmount` de
    l'API). Un trimestre dont la vraie date est déjà passée ou tombe le
    même mois que l'inscription (l'API HelloAsso refuse toute échéance
    dans le mois de l'échéance initiale) est payé immédiatement lui
    aussi — seuls les trimestres réellement à venir deviennent des
    `terms` HelloAsso, plafonnés au jour 1 du mois (jamais après le 27,
    contrainte de l'API)."""
    if nb_echeances not in (1, 3):
        raise ValueError("nb_echeances doit être 1 ou 3")

    if nb_echeances == 1:
        total = montant_adhesion + montant_trimestriel * NB_TRIMESTRES
        return [Echeance(montant=total, date_prelevement=None)]

    aujourdhui = aujourdhui or dt.date.today()
    montant_immediat = montant_adhesion
    echeances_futures: list[Echeance] = []
    for date_echeance in dates_trimestres(saison):
        deja_du = (date_echeance.year, date_echeance.month) <= (aujourdhui.year, aujourdhui.month)
        if deja_du:
            montant_immediat += montant_trimestriel
        else:
            echeances_futures.append(Echeance(montant=montant_trimestriel, date_prelevement=date_echeance))

    return [Echeance(montant=montant_immediat, date_prelevement=None), *echeances_futures]
