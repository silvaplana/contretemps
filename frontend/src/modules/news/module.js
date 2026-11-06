// Déclaration du module Actualités (spec/core.md §9 bis,
// spec/modules/actualites.md §2) : l'onglet Actus, juste après Admin, pour
// tout le monde.
export default {
  key: 'news',
  tabs: [{ key: 'actus', label: 'Actus', icon: 'news', roles: ['admin', 'professeur', 'eleve'] }],
}
