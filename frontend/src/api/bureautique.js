// Édition Word / Excel / PowerPoint avec OnlyOffice (essai, voir
// backend/src/bureautique/). La session est ajoutée par api/identite.js.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// { config, api_js, modifiable } : configuration signée de l'éditeur.
export async function configurationEditeur(orgId, nodeId) {
  const reponse = await fetch(`${BASE_URL}/bureautique/orgs/${orgId}/nodes/${nodeId}/configuration`)
  if (!reponse.ok) {
    let message = `L'éditeur ne s'ouvre pas (${reponse.status})`
    try {
      const { detail } = await reponse.json()
      if (typeof detail === 'string') message = detail
    } catch {
      // pas de JSON : message par défaut
    }
    throw new Error(message)
  }
  return reponse.json()
}

// Le script d'OnlyOffice, chargé une seule fois.
const scripts = new Map()
export function chargerScript(url) {
  if (!scripts.has(url)) {
    scripts.set(
      url,
      new Promise((resolve, reject) => {
        const balise = document.createElement('script')
        balise.src = url
        balise.onload = resolve
        balise.onerror = () => {
          scripts.delete(url)
          reject(new Error('Le serveur d’édition ne répond pas.'))
        }
        document.head.appendChild(balise)
      }),
    )
  }
  return scripts.get(url)
}
