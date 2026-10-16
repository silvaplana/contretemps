// Adresse d'une page en ligne : <page>.<école>.contretemps.silvaplana.cloud
// (documents.md §5.5), ou <page>.<école>.localhost en développement.
const DOMAINES = ['contretemps.silvaplana.cloud', 'localhost']

export function pageDuHost(hostname) {
  const hote = (hostname ?? '').toLowerCase().replace(/\.$/, '')
  for (const domaine of DOMAINES) {
    if (hote.endsWith(`.${domaine}`)) {
      const morceaux = hote.slice(0, -domaine.length - 1).split('.')
      if (morceaux.length === 2 && morceaux.every(Boolean)) return { page: morceaux[0], ecole: morceaux[1] }
    }
  }
  return null
}

// « https://le-beausset.contretemps.silvaplana.cloud » + « fete » ->
// « https://fete.le-beausset.contretemps.silvaplana.cloud ».
export function adresseDeLaPage(adresseEcole, slug) {
  if (!adresseEcole) return null
  return adresseEcole.replace('://', `://${slug}.`)
}
