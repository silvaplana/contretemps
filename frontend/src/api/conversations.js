// Domaine "conversations" (Admin > Conversations, voir spec/SPEC.md §5.1.5
// et §6.9) — voir README.md pour le principe général. Ne couvre ici que
// l'écran Admin (composition des conversations : nom, membres, groupe
// WhatsApp miroir) ; l'écran Messagerie (fil de messages) reste sur les
// données maquette pour l'instant (voir api/README.md, messagerie pas
// encore entièrement migrée — DOMAINES_MIGRES.messagerie).
//
// Groupe WhatsApp miroir (§6.9) : le "tuyau" pour un futur envoi réel
// (Baileys, plus tard) — pas encore branché, voir backend/src/messagerie/
// conversations.py: creer_groupe_whatsapp (stub). Ici, `whatsappStatut`
// vaut 'aucun' ou 'cree' ; `creerGroupeWhatsapp` déclenche la création
// (toujours avec confirmation utilisateur côté écran, voir AdminGroupes.jsx).

import { groupes as groupesInitiaux } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : copie mutable en mémoire, jamais le tableau original de
// mockData.js (même logique que eleves.js). ---
let magasin = null
function lireMagasin() {
  if (magasin === null) {
    magasin = groupesInitiaux.map((g) => ({
      ...g,
      membres: g.membres.map((m) => ({ ...m })),
      whatsappStatut: 'aucun',
      whatsappGroupeId: null,
    }))
  }
  return magasin
}
function trouverOuLever(id) {
  const g = lireMagasin().find((x) => x.id === id)
  if (!g) throw new Error('Conversation introuvable')
  return g
}

async function listerMaquette() {
  return lireMagasin()
}

async function creerMaquette(nom) {
  const nouvelle = { id: crypto.randomUUID(), nom, membres: [], whatsappStatut: 'aucun', whatsappGroupeId: null }
  lireMagasin().push(nouvelle)
  return nouvelle
}

async function renommerMaquette(id, nom) {
  const g = trouverOuLever(id)
  g.nom = nom
  return g
}

async function supprimerMaquette(id) {
  const liste = lireMagasin()
  const index = liste.findIndex((x) => x.id === id)
  if (index !== -1) liste.splice(index, 1)
}

async function ajouterMembreMaquette(id, membre) {
  trouverOuLever(id).membres.push(membre)
}

async function retirerMembreMaquette(id, index) {
  trouverOuLever(id).membres.splice(index, 1)
}

async function creerGroupeWhatsappMaquette(id) {
  const g = trouverOuLever(id)
  g.whatsappStatut = 'cree'
  g.whatsappGroupeId = `demo-${id}`
  return g
}

// --- Réel : voir backend/src/messagerie/receiver.py. ---

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

async function listerReel(ecoleId) {
  const liste = await requete(`/conversations?ecole_id=${ecoleId}`)
  return liste.filter((c) => c.type === 'groupe').map(versEcranAdmin)
}

async function creerReel(ecoleId, nom) {
  const conv = await requete(`/conversations?ecole_id=${ecoleId}`, {
    method: 'POST',
    body: JSON.stringify({ nom, membres: [] }),
  })
  return versEcranAdmin(conv)
}

async function renommerReel(id, nom) {
  const conv = await requete(`/conversations/${id}`, { method: 'PUT', body: JSON.stringify({ nom }) })
  return versEcranAdmin(conv)
}

async function supprimerReel(id) {
  await requete(`/conversations/${id}`, { method: 'DELETE' })
}

async function ajouterMembreReel(id, membre) {
  await requete(`/conversations/${id}/membres`, {
    method: 'POST',
    body: JSON.stringify(versBlocBackend(membre)),
  })
}

async function retirerMembreReel(id, membre) {
  const { membre_type, membre_id } = versBlocBackend(membre)
  await requete(`/conversations/${id}/membres/${membre_type}/${membre_id}`, { method: 'DELETE' })
}

async function creerGroupeWhatsappReel(id) {
  return versEcranAdmin(await requete(`/conversations/${id}/whatsapp`, { method: 'POST' }))
}

// --- Point d'entrée unique, appelé par AdminGroupes.jsx ---

export async function listerEcole(ecoleId) {
  return estModeDemo() ? listerMaquette() : listerReel(ecoleId)
}

export async function creerGroupe(ecoleId, nom) {
  return estModeDemo() ? creerMaquette(nom) : creerReel(ecoleId, nom)
}

export async function renommer(id, nom) {
  return estModeDemo() ? renommerMaquette(id, nom) : renommerReel(id, nom)
}

export async function supprimer(id) {
  return estModeDemo() ? supprimerMaquette(id) : supprimerReel(id)
}

// `index` uniquement utile en maquette (retrait positionnel, voir
// AdminGroupes.jsx) — le mode réel retire par (membre_type, membre_id).
export async function ajouterMembre(id, membre) {
  return estModeDemo() ? ajouterMembreMaquette(id, membre) : ajouterMembreReel(id, membre)
}

export async function retirerMembre(id, membre, index) {
  return estModeDemo() ? retirerMembreMaquette(id, index) : retirerMembreReel(id, membre)
}

export async function creerGroupeWhatsapp(id) {
  return estModeDemo() ? creerGroupeWhatsappMaquette(id) : creerGroupeWhatsappReel(id)
}
