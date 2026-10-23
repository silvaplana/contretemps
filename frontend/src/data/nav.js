import { MODULES } from '../app/modules.js'

// Onglets de la barre de navigation basse (voir spec/SPEC.md §3 et §4),
// avec les rôles qui y ont accès — partagé entre BottomNav.jsx (affichage)
// et App.jsx (retomber sur un onglet accessible après un switch de profil).
// Le core n'a que Admin, Supervision et Profil ; les onglets des modules
// viennent de leur déclaration (spec/core.md §9 bis), entre Admin et
// Supervision, dans l'ordre de app/modules.js.
export const TABS = [
  { key: 'admin', label: 'Admin', icon: 'admin', roles: ['admin'] },
  ...MODULES.flatMap((module) => module.tabs),
  // Super User seulement (§2.5) : `superuser` n'est jamais ajouté aux autres
  // comptes, contrairement à admin/owner qu'IL reçoit en plus (voir
  // data/roles.js : rolesDe) — les autres ne voient donc jamais cet onglet.
  { key: 'supervision', label: 'Supervision', icon: 'supervision', roles: ['superuser'] },
  // Profil reste le dernier onglet (demande du 2026-10-01).
  { key: 'profil', label: 'Profil', icon: 'profil', roles: ['admin', 'professeur', 'eleve'] },
]
