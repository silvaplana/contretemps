// Essai du style « Franche » (Seb, 21 novembre ; spec/core.md §7 bis) : un
// réglage gardé sur l'appareil, éteint par défaut. Allumé, il pose
// data-style="franche" sur la racine, et style-franche.css s'applique ;
// seulement sur un fond sombre (Assofight) : rien ne change pour Contretemps.
const CLE = 'style-essai'

export function essaiAllume() {
  try {
    return localStorage.getItem(CLE) === 'franche'
  } catch {
    return false
  }
}

export function appliquerEssai(sombre) {
  if (sombre && essaiAllume()) document.documentElement.dataset.style = 'franche'
  else delete document.documentElement.dataset.style
}

export function basculerEssai(sombre) {
  try {
    if (essaiAllume()) localStorage.removeItem(CLE)
    else localStorage.setItem(CLE, 'franche')
  } catch {
    // Stockage refusé : l'essai reste éteint.
  }
  appliquerEssai(sombre)
}
