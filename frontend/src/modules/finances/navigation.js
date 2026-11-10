// Demander un sous-onglet du Financier depuis un autre écran (Bilan › Préparer
// → Pièces › Rapprocher). Financier.jsx écoute l'événement.
export const SOUS_ONGLET_EVENT = 'financier-sous-onglet'

export function requestSousOnglet(value) {
  window.dispatchEvent(new CustomEvent(SOUS_ONGLET_EVENT, { detail: value }))
}
