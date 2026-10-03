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
  // Plus d'onglet Vidéo (2026-10-03) : les vidéos se gèrent dans les chorégraphies.
  {
    key: 'messagerie',
    label: 'Messages',
    icon: 'messagerie',
    roles: ['admin', 'professeur', 'eleve'],
  },
  // Documents (demande du 2026-09-25, prototype) : tout le monde, juste
  // avant Profil.
  { key: 'docs', label: 'Docs', icon: 'docs', roles: ['admin', 'professeur', 'eleve'] },
  // Super User seulement (§2.5) : `superuser` n'est jamais ajouté aux autres
  // comptes, contrairement à admin/owner qu'IL reçoit en plus (voir
  // data/roles.js : rolesDe) — les autres ne voient donc jamais cet onglet.
  { key: 'supervision', label: 'Supervision', icon: 'supervision', roles: ['superuser'] },
  // Profil reste le dernier onglet (demande du 2026-10-01).
  { key: 'profil', label: 'Profil', icon: 'profil', roles: ['admin', 'professeur', 'eleve'] },
]
