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

function tarifPourPalier(palier, nbCours) {
  if (palier === 'eveil') return TARIF_EVEIL
  const bareme = palier === 'initiation_moyen' ? BAREME_INITIATION_MOYEN : BAREME_JUNIOR_ET_PLUS
  const index = Math.min(Math.max(nbCours, 1), bareme.mensuel.length) - 1
  return { mensuel: bareme.mensuel[index], trimestriel: bareme.trimestriel[index] }
}

// `nomsCours` : noms de cours choisis (voir PALIER_PAR_COURS). Renvoie
// null si aucun cours choisi (rien à afficher encore).
export function calculerTarifIndicatif(nomsCours) {
  if (nomsCours.length === 0) return null
  const paliers = new Set(nomsCours.map((nom) => PALIER_PAR_COURS[nom]).filter(Boolean))
  if (paliers.size === 0) paliers.add('initiation_moyen')
  const palierRetenu = [...paliers].sort(
    (a, b) => ORDRE_PALIERS.indexOf(b) - ORDRE_PALIERS.indexOf(a)
  )[0]
  const { mensuel, trimestriel } = tarifPourPalier(palierRetenu, nomsCours.length)
  return {
    palier: palierRetenu,
    montantAdhesion: ADHESION,
    montantMensuel: mensuel,
    montantTrimestriel: trimestriel,
    alertePalierMixte: paliers.size > 1,
  }
}
