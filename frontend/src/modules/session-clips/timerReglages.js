// Les réglages du Timer, gardés sur l'appareil. Timer étendu (Seb, 21/11) :
// dès qu'une des trois cases de Fights › ⋮ › Paramètres du Timer est cochée.
const REGLAGES = 'sc-timer'
const DEPART = { mode: 'un', round: 180, repos: 60, nombre: 3, prevenir: true, film: false, noms: false, vainqueur: false }

export function lire() {
  try {
    return { ...DEPART, ...JSON.parse(localStorage.getItem(REGLAGES) || '{}') }
  } catch {
    return DEPART
  }
}

export function ecrire(r) {
  try {
    localStorage.setItem(REGLAGES, JSON.stringify(r))
  } catch {
    // stockage refusé : réglages pour cette fois
  }
}

export const estEtendu = (r) => r.film || r.noms || r.vainqueur
