// Demander un sous-onglet du Financier depuis un autre écran (Bilan › Préparer
// → Pièces › Rapprocher). Financier.jsx écoute l'événement.
export const SOUS_ONGLET_EVENT = 'financier-sous-onglet'

export function requestSousOnglet(value) {
  window.dispatchEvent(new CustomEvent(SOUS_ONGLET_EVENT, { detail: value }))
}

// Admin › École › Connexions ouvre Comptes avec le volet de la banque déplié
// (spec/core.md, « Connexions ») : demandé avant d'ouvrir l'onglet, lu une fois
// par Comptes.jsx à son affichage.
let banqueDemandee = false

export function demanderBanque() {
  banqueDemandee = true
}

export function prendreDemandeBanque() {
  const demandee = banqueDemandee
  banqueDemandee = false
  return demandee
}

// Ouvrir la fiche d'une pièce par-dessus l'écran en cours (Comptes › Balance) ;
// Financier.jsx écoute l'événement.
export const FICHE_PIECE_EVENT = 'financier-fiche-piece'

export function requestFichePiece(noteId) {
  window.dispatchEvent(new CustomEvent(FICHE_PIECE_EVENT, { detail: noteId }))
}

// Comptes › Balance demande Bilan › Préparer sur une saison, une étape dépliée
// (les soldes de départ manquent) : lu une fois par Bilan.jsx puis Preparer.jsx.
let etapeDemandee = null

export function demanderEtape(seasonId, etape) {
  etapeDemandee = { seasonId, etape }
  requestSousOnglet('bilan')
}

export function prendreSaisonDemandee() {
  return etapeDemandee?.seasonId ?? null
}

export function prendreEtapeDemandee() {
  const e = etapeDemandee?.etape ?? null
  etapeDemandee = null
  return e
}
