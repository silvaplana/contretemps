// Bascule maquette/réel — voir backend-architecture (mémoire projet) :
// UN SEUL endroit qui décide, jamais de `if (modeDemo)` dispersé dans les
// écrans. Les écrans appellent uniquement les fonctions de api/<domaine>.js
// (ex. api/auth.js), qui consultent ceci elles-mêmes — jamais l'inverse.
//
// Par défaut : mode démo (voir spec, décision explicite de l'utilisateur —
// "je préfère garder cet exemple en dur avant de brancher le backend qui
// risque de foirer au début"). Personne ne bascule encore en mode réel
// aujourd'hui ; le mécanisme existe pour le jour où on branchera l'API.

const CLE_STOCKAGE = 'contretemps_mode_demo'

export function estModeDemo() {
  try {
    return localStorage.getItem(CLE_STOCKAGE) !== 'non'
  } catch {
    // Stockage indisponible (navigation privée, etc.) : démo par défaut,
    // jamais bloquant.
    return true
  }
}

export function activerModeDemo() {
  try {
    localStorage.setItem(CLE_STOCKAGE, 'oui')
  } catch {
    /* pas grave : démo reste le comportement par défaut sans stockage */
  }
}

export function activerModeReel() {
  try {
    localStorage.setItem(CLE_STOCKAGE, 'non')
  } catch {
    /* pas grave : sans stockage, on retombe en démo au prochain chargement */
  }
}
