import HelloAssoReglages from './HelloAssoReglages.jsx'

// Déclaration du module HelloAsso (spec/core.md §9 bis,
// spec/modules/helloasso.md) : pas d'onglet ; sa ligne de Fonctionnalités
// porte la connexion de l'école (`settings`).
export default {
  key: 'helloasso',
  tabs: [],
  settings: HelloAssoReglages,
}
