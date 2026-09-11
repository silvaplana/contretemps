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
# (cours choisis touchant plusieurs paliers) : on retient le plus cher.
_ORDRE_PALIERS = ["eveil", "initiation_moyen", "junior_et_plus"]

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
