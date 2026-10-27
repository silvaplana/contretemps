import HelloAssoCampagne from './HelloAssoCampagne.jsx'
import HelloAssoReglages from './HelloAssoReglages.jsx'
import HelloAssoTarifs from './HelloAssoTarifs.jsx'

// Déclaration du module HelloAsso (spec/core.md §9 bis,
// spec/modules/helloasso.md) : pas d'onglet ; sa ligne de Fonctionnalités
// porte la connexion de l'école (`settings`) ; la fiche d'un membre, la
// campagne de la saison (`memberFields`).
export default {
  key: 'helloasso',
  tabs: [],
  settings: HelloAssoReglages,
  memberFields: HelloAssoCampagne,
  seasonPrices: HelloAssoTarifs,
}
