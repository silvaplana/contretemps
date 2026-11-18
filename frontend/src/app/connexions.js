import * as sessionApi from '../api/session.js'

// Admin › École › Connexions (spec/core.md, « Connexions ») : un module pas encore
// connecté y envoie l'Administrateur principal (« Connecter la boîte mail »).
// Le volet s'ouvre au prochain affichage d'Admin › École.
export function ouvrirConnexions() {
  sessionApi.sauvegarderEcran('admin', 'ecole')
  sessionApi.sauvegarderEcran('connexions', 'ouvrir')
  ouvrirOnglet('admin')
}

// Ouvre un onglet de la barre du bas (App.jsx écoute l'événement).
export function ouvrirOnglet(onglet) {
  window.dispatchEvent(new CustomEvent('app-ouvrir-onglet', { detail: onglet }))
}
