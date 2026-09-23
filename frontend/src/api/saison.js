// Saison AFFICHÉE (voir spec/SPEC.md §2.6) : celle que l'appli montre.
// `null` = la saison courante (cas normal, et le seul possible pour un
// non-admin). Un admin peut choisir une ancienne saison dans Admin > École
// (voir screens/admin/SaisonsSection.jsx) : toute l'appli la montre alors,
// en lecture seule.
//
// Gardée en mémoire seulement (pas en localStorage) : un rechargement ou
// une reconnexion ramène toujours à la saison courante, pour qu'un admin ne
// se retrouve jamais, le lendemain, coincé sans le savoir dans une saison
// terminée.
//
// Le choix part au serveur avec chaque requête vers l'API, dans l'en-tête
// `X-Saison-Id` (voir api/identite.js) : c'est le serveur qui filtre les
// données par saison et refuse toute écriture dans une ancienne saison
// (backend/src/saisons/portee.py).

import { useSyncExternalStore } from 'react'

export const ENTETE_SAISON = 'X-Saison-Id'

let saisonConsultee = null
const abonnes = new Set()

export function lireSaisonConsultee() {
  return saisonConsultee
}

// `saison` : { id, nom } d'une ancienne saison, ou null pour revenir à la
// saison courante.
export function consulterSaison(saison) {
  saisonConsultee = saison ? { id: saison.id, nom: saison.nom } : null
  abonnes.forEach((f) => f())
}

function sAbonner(f) {
  abonnes.add(f)
  return () => abonnes.delete(f)
}

export function useSaisonConsultee() {
  return useSyncExternalStore(sAbonner, lireSaisonConsultee)
}

// --- Réponses du serveur liées aux saisons (voir api/identite.js) ---

// Émis quand le serveur signale que la fiche connectée appartient à une
// saison terminée : `{ code: 'nouvelle_saison', compteId }` (la personne a
// été reprise, l'appli bascule sur sa nouvelle fiche) ou
// `{ code: 'hors_saison' }` (pas reprise : déconnexion). Et quand il refuse
// une écriture dans une ancienne saison : `{ code: 'lecture_seule' }`.
export const EVENEMENT_SAISON = 'contretemps:saison'

export function signalerSaison(detail) {
  window.dispatchEvent(new CustomEvent(EVENEMENT_SAISON, { detail }))
}
