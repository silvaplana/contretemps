// Déclaration du module Documents (spec/core.md §9 bis) : onglet Docs pour
// tout le monde.
export default {
  key: 'documents',
  tabs: [{ key: 'docs', label: 'Docs', icon: 'docs', roles: ['admin', 'professeur', 'eleve'] }],
}
