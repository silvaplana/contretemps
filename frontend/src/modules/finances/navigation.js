// Demander un sous-onglet du Financier depuis un autre écran (Bilan › Préparer
// → Pièces › Rapprocher). Financier.jsx écoute l'événement.
export const SOUS_ONGLET_EVENT = 'financier-sous-onglet'

export function requestSousOnglet(value) {
  window.dispatchEvent(new CustomEvent(SOUS_ONGLET_EVENT, { detail: value }))
}

// Bilan › « Voir les Comptes » / « Voir les Pièces » (Seb, 10/11) : sur
// ordinateur, un volet à côté du bilan ; sur téléphone, l'écran en entier.
export const A_COTE_EVENT = 'financier-a-cote'

export function requestACote(value) {
  window.dispatchEvent(new CustomEvent(A_COTE_EVENT, { detail: value }))
}
