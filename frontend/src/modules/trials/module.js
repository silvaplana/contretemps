import Essais from './Essais.jsx'

// Déclaration du module Essai (spec/core.md §11, spec/modules/essai.md) :
// pas d'onglet ; le sous-onglet « Essais » d'Admin, après Élèves. La page
// publique (`<adresse de l'école>/essai`) est ouverte par main.jsx.
export default {
  key: 'trials',
  tabs: [],
  adminTabs: [{ value: 'essais', label: 'Essais', Ecran: Essais, after: 'eleves' }],
}
