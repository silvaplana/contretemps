// Déclaration du module Financier (spec/core.md §9 bis) : trésoriers
// seulement (et le Super User, qui a tous les rôles).
export default {
  key: 'finances',
  tabs: [{ key: 'financier', label: 'Financier', icon: 'calculator', roles: ['tresorier'] }],
}
