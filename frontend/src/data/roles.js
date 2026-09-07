import { ROLE_RANK } from './mockData.js'

// Libellé affichable d'un rôle (voir spec/SPEC.md §2, §4) — partagé entre
// Header (sélecteur famille) et ProfilScreen (liste des profils du foyer).
export const ROLE_LABEL = { admin: 'Admin', professeur: 'Professeur', eleve: 'Élève' }

// Passer de `depuisType` à `versType` est une montée en privilège (voir
// §2.2, règle Élève < Professeur < Admin) : le code d'accès du rôle visé
// doit alors être redemandé. Vers un rôle égal ou inférieur : bascule libre.
export function estMonteeEnPrivilege(depuisType, versType) {
  return ROLE_RANK[versType] > ROLE_RANK[depuisType]
}
