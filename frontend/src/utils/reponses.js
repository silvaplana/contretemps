// Une réponse à un champ de la fiche (spec/core.md §4.3), en clair : fiche
// de l'élève en lecture et colonnes du tableau des élèves.
export function texteReponse(champ, valeur, sousGroupes = []) {
  if (valeur == null || valeur === '') return ''
  if (champ.format === 'date') return valeur.split('-').reverse().join('/')
  if (champ.format === 'yes_no') return valeur ? 'Oui' : 'Non'
  if (champ.format === 'group') return sousGroupes.filter((g) => valeur.includes(g.id)).map((g) => g.name).join(', ')
  if (champ.format === 'file') return valeur.name
  if (Array.isArray(valeur)) return valeur.join(', ')
  return String(valeur)
}
