// Onglets de la barre de navigation basse (voir spec/SPEC.md §3 et §4),
// avec les rôles qui y ont accès — partagé entre BottomNav.jsx (affichage)
// et App.jsx (retomber sur un onglet accessible après un switch de profil).
export const TABS = [
  { key: 'admin', label: 'Admin', icon: 'admin', roles: ['admin'] },
  { key: 'presence', label: 'Présence', icon: 'presence', roles: ['admin', 'professeur'] },
  {
    key: 'choregraphie',
    label: 'Chorégraphie',
    icon: 'choregraphie',
    roles: ['admin', 'professeur', 'eleve'],
  },
  { key: 'video', label: 'Vidéo', icon: 'video', roles: ['admin', 'professeur', 'eleve'] },
  {
    key: 'messagerie',
    label: 'Messagerie',
    icon: 'messagerie',
    roles: ['admin', 'professeur', 'eleve'],
  },
  { key: 'profil', label: 'Profil', icon: 'profil', roles: ['admin', 'professeur', 'eleve'] },
]
