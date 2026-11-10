// Demander un sous-onglet du Financier depuis un autre écran (Bilan › Préparer
// → Pièces › Rapprocher). Financier.jsx écoute l'événement.
export const SOUS_ONGLET_EVENT = 'financier-sous-onglet'

export function requestSousOnglet(value) {
  window.dispatchEvent(new CustomEvent(SOUS_ONGLET_EVENT, { detail: value }))
}

// Ouvrir la fiche d'une pièce par-dessus l'écran en cours (Comptes › Balance) ;
// Financier.jsx écoute l'événement.
export const FICHE_PIECE_EVENT = 'financier-fiche-piece'

export function requestFichePiece(noteId) {
  window.dispatchEvent(new CustomEvent(FICHE_PIECE_EVENT, { detail: noteId }))
}
