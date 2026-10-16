// Assistant de l'onglet Documents (prototype, voir backend/src/assistant/).
// La réponse arrive en flux (Server-Sent Events sur une requête POST) : on
// lit le corps au fil de l'eau et on transmet chaque événement à `surEvenement`
// ({ type: 'conversation' | 'texte' | 'outil' | 'action' | 'fin' | 'erreur', ... }).
// La session est ajoutée par api/identite.js, comme pour toute requête.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// L'assistant est-il ouvert à cette personne ? (essai : le Super User)
// Avec le cumul « Chat documents » de la saison : { autorise, cout_saison_usd }.
export async function accesAssistant(orgId) {
  const reponse = await fetch(`${BASE_URL}/assistant/acces?org_id=${orgId}`)
  return reponse.ok ? reponse.json() : { autorise: false, cout_saison_usd: null }
}

// « Faire » sur un fichier fabriqué par l'ordinateur de l'assistant : il
// entre dans Documents, dans l'espace et le dossier indiqués.
// « Tout faire » sur une carte de modifications : seulement les lignes
// cochées. Renvoie une ligne par changement : { index, libelle, ok, erreur? }.
export async function faireModifications(orgId, jeton, indices) {
  const reponse = await fetch(`${BASE_URL}/assistant/orgs/${orgId}/modifications/${jeton}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ indices }),
  })
  if (!reponse.ok) {
    let message = `Modification impossible (${reponse.status})`
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

export async function ajouterProduit(orgId, jeton, espace, dossierParentId) {
  const reponse = await fetch(`${BASE_URL}/assistant/orgs/${orgId}/produits/${jeton}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ espace, dossier_parent_id: dossierParentId }),
  })
  if (!reponse.ok) {
    let message = `Ajout impossible (${reponse.status})`
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

// Fichier glissé dans l'assistant : déposé tout de suite, joint à la
// question suivante par son identifiant. { id, nom, taille }.
export async function deposerPiece(orgId, fichier) {
  const donnees = new FormData()
  donnees.append('fichier', fichier, fichier.name)
  const reponse = await fetch(`${BASE_URL}/assistant/orgs/${orgId}/pieces`, { method: 'POST', body: donnees })
  if (!reponse.ok) {
    let message = `« ${fichier.name} » n'a pas pu être joint (${reponse.status})`
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

export async function poserQuestion(orgId, { conversationId, texte, contexte, modele, pieces = [] }, surEvenement) {
  const reponse = await fetch(`${BASE_URL}/assistant/orgs/${orgId}/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, texte, contexte, modele, pieces }),
  })
  if (!reponse.ok) {
    let message = `L'assistant ne répond pas (${reponse.status})`
    try {
      const { detail } = await reponse.json()
      if (typeof detail === 'string') message = detail
    } catch {
      // pas de JSON : message par défaut
    }
    throw new Error(message)
  }
  const lecteur = reponse.body.getReader()
  const decodeur = new TextDecoder()
  let tampon = ''
  for (;;) {
    const { done, value } = await lecteur.read()
    if (done) break
    tampon += decodeur.decode(value, { stream: true })
    let fin
    while ((fin = tampon.indexOf('\n\n')) >= 0) {
      const bloc = tampon.slice(0, fin)
      tampon = tampon.slice(fin + 2)
      for (const ligne of bloc.split('\n')) {
        if (ligne.startsWith('data: ')) surEvenement(JSON.parse(ligne.slice(6)))
      }
    }
  }
}
