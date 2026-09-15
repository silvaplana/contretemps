// Âge calculé à la volée depuis une date de naissance (voir spec/SPEC.md
// §6.4) — jamais stocké, recalculé à chaque affichage. Partagé entre
// AdminEleves.jsx et ProfilContactScreen.jsx (fiche élève de Messagerie).
export function calculerAge(dateNaissance) {
  if (!dateNaissance) return null
  const naissance = new Date(dateNaissance)
  const aujourdhui = new Date()
  let age = aujourdhui.getFullYear() - naissance.getFullYear()
  const pasEncoreAnniversaire =
    aujourdhui.getMonth() < naissance.getMonth() ||
    (aujourdhui.getMonth() === naissance.getMonth() && aujourdhui.getDate() < naissance.getDate())
  if (pasEncoreAnniversaire) age -= 1
  return age
}
