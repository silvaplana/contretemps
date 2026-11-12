import { MODULES } from '../app/modules.js'
import { aUnDesRoles } from './roles.js'

// Onglets de la barre de navigation basse (voir spec/SPEC.md §3 et §4),
// avec les rôles qui y ont accès — partagé entre BottomNav.jsx (affichage)
// et App.jsx (retomber sur un onglet accessible après un switch de profil).
// Le core n'a que Admin, Supervision et Profil ; les onglets des modules
// viennent de leur déclaration (spec/core.md §9 bis), entre Admin et
// Supervision, dans l'ordre de app/modules.js.
//
// `charges` : ce que les modules aux onglets calculés ont lu pour l'école
// (spec/core.md §11.1), par clé de module, ex. { publications: blogs }.
export const ongletsAvec = (charges = {}) => [
  { key: 'admin', label: 'Admin', icon: 'admin', roles: ['admin'] },
  // `module` : pour cacher l'onglet quand l'école a éteint le module (§9 bis.3).
  ...MODULES.flatMap((module) =>
    (typeof module.tabs === 'function' ? module.tabs(charges[module.key]) : module.tabs).map((tab) => ({ ...tab, module: module.key })),
  ),
  // Super User seulement (§2.5) : `superuser` n'est jamais ajouté aux autres
  // comptes, contrairement à admin/owner qu'IL reçoit en plus (voir
  // data/roles.js : rolesDe) — les autres ne voient donc jamais cet onglet.
  { key: 'supervision', label: 'Supervision', icon: 'supervision', roles: ['superuser'] },
  // Profil reste le dernier onglet (demande du 2026-10-01).
  { key: 'profil', label: 'Profil', icon: 'profil', roles: ['admin', 'professeur', 'eleve'] },
]

// Les onglets fixes (sans ceux qui se calculent).
export const TABS = ongletsAvec()

// Un onglet calculé (ex. « blog-3 ») avant que son module ait lu l'école.
export const ongletCalcule = (key) => MODULES.some((m) => m.tabPrefix && key?.startsWith(m.tabPrefix))

// Largeur minimale d'un onglet lisible (icône + libellé à 10 px) : en
// dessous, les libellés se chevauchent. Donne le nombre de places de la barre.
export const LARGEUR_ONGLET = 64

// Les onglets que ce profil voit, dans SON ordre (Profil › Ma barre du bas,
// spec/core.md §10.4) : `profil.tabOrder` d'abord, puis, dans l'ordre de
// l'école, ceux qu'il n'a pas rangés (un module allumé depuis). Les clés
// inconnues (module retiré) sont ignorées. `tabs` : avec les onglets
// calculés pour l'école (ongletsAvec).
export function ongletsVisibles(profil, eteints = new Set(), tabs = TABS) {
  const visibles = tabs.filter((tab) => aUnDesRoles(profil, tab.roles) && !eteints.has(tab.module))
  const ordre = profil.tabOrder ?? []
  const rang = (tab) => (ordre.includes(tab.key) ? ordre.indexOf(tab.key) : ordre.length)
  // sort est stable : à rang égal, l'ordre de l'école reste.
  return [...visibles].sort((a, b) => rang(a) - rang(b))
}
