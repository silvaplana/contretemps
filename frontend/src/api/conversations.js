// Domaine "conversations" (Admin > Conversations, voir spec/SPEC.md §5.1.5
// et §6.9) — voir README.md pour le principe général. Ne couvre ici que
// l'écran Admin (composition des conversations : nom, membres, groupe
// WhatsApp miroir) ; l'écran Messagerie (fil de messages) est couvert par
// api/messages.js.
//
// Groupe WhatsApp miroir (§6.9) : le "tuyau" pour un futur envoi réel
// (Baileys, plus tard) — pas encore branché, voir backend/src/messagerie/
// conversations.py: creer_groupe_whatsapp (stub). Ici, `whatsappStatut`
// vaut 'aucun' ou 'cree' ; `creerGroupeWhatsapp` déclenche la création
// (toujours avec confirmation utilisateur côté écran, voir AdminGroupes.jsx).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// 'compte' se résout en admin/professeur/eleve via son `role` dans les
// membres déjà résolus par le backend (`membres`) — un même bloc brut
// (`blocs`) ne porte pas cette info, voir backend/src/messagerie/
// schemas.py (ConversationSortie.blocs vs .membres).
function versEcranAdmin(conv) {
  const parId = new Map(conv.membres.map((m) => [m.id, m]))
  return {
    id: conv.id,
    nom: conv.nom ?? '',
    type: conv.type,
    whatsappStatut: conv.whatsapp_statut,
    whatsappGroupeId: conv.whatsapp_groupe_id,
    membres: conv.blocs.map((b) => {
      if (b.membre_type === 'cours') return { type: 'cours', id: b.membre_id }
      const compte = parId.get(b.membre_id)
      return {
        type: compte?.role ?? 'admin',
        id: b.membre_id,
        label: compte ? `${compte.prenom} ${compte.nom}` : undefined,
      }
    }),
  }
}

function versBlocBackend({ type, id }) {
  return { membre_type: type === 'cours' ? 'cours' : 'compte', membre_id: id }
}

export async function listerEcole(ecoleId) {
  const liste = await requete(`/conversations?ecole_id=${ecoleId}`)
  return liste.filter((c) => c.type === 'groupe').map(versEcranAdmin)
}

export async function creerGroupe(ecoleId, nom) {
  const conv = await requete(`/conversations?ecole_id=${ecoleId}`, {
    method: 'POST',
    body: JSON.stringify({ nom, membres: [] }),
  })
  return versEcranAdmin(conv)
}

export async function renommer(id, nom) {
  const conv = await requete(`/conversations/${id}`, { method: 'PUT', body: JSON.stringify({ nom }) })
  return versEcranAdmin(conv)
}

export async function supprimer(id) {
  await requete(`/conversations/${id}`, { method: 'DELETE' })
}

export async function ajouterMembre(id, membre) {
  await requete(`/conversations/${id}/membres`, {
    method: 'POST',
    body: JSON.stringify(versBlocBackend(membre)),
  })
}

export async function retirerMembre(id, membre) {
  const { membre_type, membre_id } = versBlocBackend(membre)
  await requete(`/conversations/${id}/membres/${membre_type}/${membre_id}`, { method: 'DELETE' })
}

export async function creerGroupeWhatsapp(id) {
  return versEcranAdmin(await requete(`/conversations/${id}/whatsapp`, { method: 'POST' }))
}
