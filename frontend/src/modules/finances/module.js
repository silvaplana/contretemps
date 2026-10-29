import ReglagesFinancier from './ReglagesFinancier.jsx'

// Déclaration du module Financier (spec/core.md §9 bis) : trésoriers
// seulement (et le Super User, qui a tous les rôles). Sa ligne de
// Fonctionnalités porte le niveau des documents comptables (financier.md
// §8.1) et le réglage « Qui paie » (§8.3 bis).
export default {
  key: 'finances',
  tabs: [{ key: 'financier', label: 'Financier', icon: 'calculator', roles: ['tresorier'] }],
  settings: ReglagesFinancier,
}
