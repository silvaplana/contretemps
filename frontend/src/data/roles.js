// Libellé affichable d'un rôle (voir spec/SPEC.md §2, §4) — partagé entre
// Header (sélecteur famille) et ProfilScreen (liste des profils du foyer).
export const ROLE_LABEL = { admin: 'Admin', professeur: 'Professeur', eleve: 'Élève', superuser: 'Propriétaire' }

// Rang de rôle, du plus faible au plus fort (voir spec §2.2 "règle de
// sécurité du switch de profil famille") : sert à savoir si passer d'un
// profil à l'autre est une montée en privilège (code redemandé) ou non.
export const ROLE_RANK = { eleve: 0, professeur: 1, admin: 2, superuser: 3 }

// Passer de `depuisType` à `versType` est une montée en privilège (voir
// §2.2, règle Élève < Professeur < Admin) : le code d'accès du rôle visé
// doit alors être redemandé. Vers un rôle égal ou inférieur : bascule libre.
export function estMonteeEnPrivilege(depuisType, versType) {
  return ROLE_RANK[versType] > ROLE_RANK[depuisType]
}

// Ordre d'affichage du sélecteur de profil famille (Header) et de "Ma
// famille" (ProfilScreen) : Admin, puis Professeur, puis Élève — pas
// l'ordre arbitraire du tableau en mémoire.
export function trierParRole(profils) {
  return [...profils].sort((a, b) => ROLE_RANK[b.type] - ROLE_RANK[a.type])
}

// Rôles cumulables (voir spec/SPEC.md §2.1 et §6.3bis) : un profil peut en
// avoir plusieurs (ex. professeur ET admin), dans `profil.roles`.
// ⚠️ Pour savoir ce qu'un profil a le DROIT de faire, toujours passer par
// ces fonctions, jamais par `profil.type` : `type` n'est que le rôle
// principal (le plus élevé), bon pour un libellé ou un rang, mais un
// professeur-admin (type 'admin') y perdrait tout ce qui est propre aux
// profs (ex. "Mes heures" dans Profil). Même règle côté serveur
// (backend/src/comptes/roles.py).
function rolesDe(profil) {
  // Repli sur `type` pour un objet qui ne porte pas encore la liste (ex.
  // un membre de conversation) : il n'a alors qu'un seul rôle.
  const roles = profil?.roles ?? (profil?.type ? [profil.type] : [])
  // Le Superuser (§2.5) voit et fait tout ce que fait un Owner, dans
  // l'école qu'il a choisie : mêmes onglets, mêmes boutons. Le serveur
  // l'autorise de son côté (voir comptes/rbac.py).
  return roles.includes('superuser') ? [...roles, 'admin', 'owner'] : roles
}

export function aUnDesRoles(profil, roles) {
  return roles.some((role) => rolesDe(profil).includes(role))
}

export const isEleve = (profil) => aUnDesRoles(profil, ['eleve'])
export const isProf = (profil) => aUnDesRoles(profil, ['professeur'])
export const isAdmin = (profil) => aUnDesRoles(profil, ['admin'])
export const isOwner = (profil) => aUnDesRoles(profil, ['owner'])
export const isSuperuser = (profil) => aUnDesRoles(profil, ['superuser'])
