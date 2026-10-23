// Déclaration du module Messagerie instantanée (spec/core.md §9 bis). Ses
// écrans sont encore dans screens/messagerie/.
export default {
  key: 'messaging',
  tabs: [
    { key: 'messagerie', label: 'Messages', icon: 'messagerie', roles: ['admin', 'professeur', 'eleve'] },
  ],
}
