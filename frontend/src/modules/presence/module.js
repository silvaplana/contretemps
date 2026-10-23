// Déclaration du module Présence (spec/core.md §9 bis). Ses écrans sont
// encore dans screens/ et ouverts par App.jsx.
export default {
  key: 'presence',
  tabs: [{ key: 'presence', label: 'Présence', icon: 'presence', roles: ['admin', 'professeur'] }],
}
