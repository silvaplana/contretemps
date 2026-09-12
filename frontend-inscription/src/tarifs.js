// Calcul de tarif INDICATIF, juste pour le confort visuel immédiat côté
// formulaire — recopie de backend/src/inscriptions/tarifs.py (même
// mapping, même barème). Le tarif qui fait foi est TOUJOURS celui
// renvoyé par le serveur à la soumission (voir Confirmation.jsx) — si un
// jour les deux divergent, c'est celui-ci qu'il faut corriger.

export const PALIER_PAR_COURS = {
  Éveil: 'eveil',
  'Class Ini': 'initiation_moyen',
  'Jazz Ini': 'initiation_moyen',
  'Class Moy': 'initiation_moyen',
  'Jazz Moy': 'initiation_moyen',
  'Street Moyen': 'initiation_moyen',
  'Jazz Junior': 'junior_et_plus',
  'Street Junior Inter': 'junior_et_plus',
  'Class Inter': 'junior_et_plus',
  'Jazz Inter': 'junior_et_plus',
  'Pointes inter': 'junior_et_plus',
  'Pointes AV': 'junior_et_plus',
  'Class AV': 'junior_et_plus',
  'Jazz AV': 'junior_et_plus',
  'Contempo Junior': 'junior_et_plus',
  'Contempo Inter avance': 'junior_et_plus',
  'Contempo Adulte': 'junior_et_plus',
}

const ORDRE_PALIERS = ['eveil', 'initiation_moyen', 'junior_et_plus']

const TARIF_EVEIL = { mensuel: 36, trimestriel: 110 }
const BAREME_INITIATION_MOYEN = {
  mensuel: [42, 50, 55],
  trimestriel: [125, 150, 160],
}
const BAREME_JUNIOR_ET_PLUS = {
  mensuel: [42, 55, 62, 68, 72, 75],
  trimestriel: [125, 160, 180, 200, 210, 220],
}

export const ADHESION = 40

// Libellé lisible d'un palier — voir Tarif indicatif (FormulaireInscription.jsx)
// et Confirmation.jsx. Le palier retenu est celui du cours le plus "âgé"
// (le plus avancé) parmi les cours choisis (voir calculerTarifIndicatif
// ci-dessous et ORDRE_PALIERS).
export const LIBELLE_PALIER = {
  eveil: 'Éveil',
  initiation_moyen: 'Initiation ou Moyen',
  junior_et_plus: 'À partir de Junior',
}

function tarifPourPalier(palier, nbCours) {
  if (palier === 'eveil') return TARIF_EVEIL
  const bareme = palier === 'initiation_moyen' ? BAREME_INITIATION_MOYEN : BAREME_JUNIOR_ET_PLUS
  const index = Math.min(Math.max(nbCours, 1), bareme.mensuel.length) - 1
  return { mensuel: bareme.mensuel[index], trimestriel: bareme.trimestriel[index] }
}

const REDUCTION_FAMILLE = 5
const NB_TRIMESTRES = 3 // toujours 3 échéances par an, jamais l'été.

// `nomsCours` : noms de cours choisis (voir PALIER_PAR_COURS).
// `reductionFamille` : case "Réduction famille" cochée (voir
// FormulaireInscription.jsx) — même montant (-5€/trimestre) que
// backend/src/inscriptions/tarifs.py:REDUCTION_FAMILLE. Renvoie null si
// aucun cours choisi (rien à afficher encore).
export function calculerTarifIndicatif(nomsCours, reductionFamille = false) {
  if (nomsCours.length === 0) return null
  const paliers = new Set(nomsCours.map((nom) => PALIER_PAR_COURS[nom]).filter(Boolean))
  if (paliers.size === 0) paliers.add('initiation_moyen')
  // Palier retenu = celui du cours le plus avancé parmi les cours
  // choisis (voir ORDRE_PALIERS) — pas le moins cher.
  const palierRetenu = [...paliers].sort(
    (a, b) => ORDRE_PALIERS.indexOf(b) - ORDRE_PALIERS.indexOf(a)
  )[0]
  const { trimestriel } = tarifPourPalier(palierRetenu, nomsCours.length)
  // `montantTrimestrielBrut` : prix du palier tel quel (barème), affiché
  // dans le libellé — la réduction n'y est jamais mêlée, elle reste une
  // mention à part (voir FormulaireInscription.jsx/Confirmation.jsx).
  // `montantTroisTrimestres`/`totalAnnee`, eux, restent calculés avec la
  // réduction déduite : c'est le montant réellement dû.
  const montantTrimestriel = reductionFamille
    ? Math.max(0, trimestriel - REDUCTION_FAMILLE)
    : trimestriel
  const montantTroisTrimestres = montantTrimestriel * NB_TRIMESTRES
  return {
    palier: palierRetenu,
    montantAdhesion: ADHESION,
    montantTrimestrielBrut: trimestriel,
    montantTrimestriel,
    montantTroisTrimestres,
    totalAnnee: ADHESION + montantTroisTrimestres,
    reductionFamilleAppliquee: reductionFamille,
    alertePalierMixte: paliers.size > 1,
  }
}

// Vraies dates d'encaissement des 3 trimestres d'une saison (ex.
// "2026-2027") : 1er octobre, 1er janvier, 1er avril — recopie de
// backend/src/inscriptions/tarifs.py:dates_trimestres (même saison,
// mêmes dates), pour que le texte d'information chèque et l'aperçu
// HelloAsso 3x restent cohérents avec ce que le serveur calcule
// réellement.
export function datesTrimestres(saison) {
  const [anneeDebut, anneeFin] = saison.split('-').map(Number)
  return [new Date(anneeDebut, 9, 1), new Date(anneeFin, 0, 1), new Date(anneeFin, 3, 1)]
}

const MOIS = [
  'janvier', 'février', 'mars', 'avril', 'mai', 'juin',
  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre',
]

export function libelleMoisAnnee(date) {
  return `${MOIS[date.getMonth()]} ${date.getFullYear()}`
}

// Mois d'encaissement encore à venir, pour le texte d'info chèque en 3
// fois — même règle de repli que
// backend/src/inscriptions/tarifs.py:calculer_echeances_helloasso : un
// trimestre déjà entamé ou passé est encaissé tout de suite (avec
// l'adhésion), pas à une date qui serait déjà dépassée.
export function moisEncaissementsAVenir(saison, aujourdhui = new Date()) {
  return datesTrimestres(saison)
    .filter(
      (date) =>
        date.getFullYear() > aujourdhui.getFullYear() ||
        (date.getFullYear() === aujourdhui.getFullYear() && date.getMonth() > aujourdhui.getMonth())
    )
    .map(libelleMoisAnnee)
}
