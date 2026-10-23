// Déclaration du module Chorégraphies (spec/core.md §9 bis). Plus d'onglet
// Vidéo (2026-10-03) : les vidéos se gèrent dans les chorégraphies.
export default {
  key: 'choregraphies',
  tabs: [
    {
      key: 'choregraphie',
      label: 'Chorégraphies',
      icon: 'choregraphie',
      roles: ['admin', 'professeur', 'eleve'],
    },
  ],
}
