// Présence "en ligne" / "dernière connexion" (voir backend/src/
// messagerie/connexions.py) — demande utilisateur : "j'aimerais qu'on
// implemente la presence, c'est a dire savoir si un correspondant est
// en ligne, quand est la derniere fois qu'il a ete en ligne".
//
// État EN DEHORS du cycle de vie React (module-level, comme
// utils/messageOutbox.js) : partagé par tous les écrans qui affichent un
// même compte (fil de conversation, éventuellement liste plus tard) sans
// prop-drilling.
//
// 2 sources, jamais en conflit grâce à la garde `etats.has(...)` dans
// `initialiserPresence` : le chargement des conversations (voir
// App.jsx: listerAvecMessages) SÈME l'état une seule fois par compte,
// puis seul le flux SSE (voir appliquerEtatConnexion, événement
// `etat_connexion`) le met à jour en direct ensuite — un simple refetch
// périodique de la liste des conversations n'écrase donc jamais une info
// plus fraîche déjà connue en direct.
import { useSyncExternalStore } from 'react'

const etats = new Map() // compteId -> { enLigne: bool, derniereActiviteLe: string|null }
const abonnes = new Set()
// Incrémenté à chaque mutation de `etats` — sert de "snapshot" pour
// useSyncExternalStore dans usePresenceListe ci-dessous : `etats` lui-même
// (une Map mutée en place) garde TOUJOURS la même référence, donc la
// comparer directement ne détecterait jamais un changement.
let version = 0

function notifier() {
  version += 1
  for (const f of abonnes) f()
}

function sabonner(f) {
  abonnes.add(f)
  return () => abonnes.delete(f)
}

export function initialiserPresence(membres) {
  let change = false
  for (const m of membres) {
    if (m.en_ligne === undefined || etats.has(m.id)) continue
    etats.set(m.id, { enLigne: m.en_ligne, derniereActiviteLe: m.derniere_activite_le ?? null })
    change = true
  }
  if (change) notifier()
}

export function appliquerEtatConnexion({ compte_id, en_ligne, derniere_activite_le }) {
  etats.set(compte_id, { enLigne: en_ligne, derniereActiviteLe: derniere_activite_le })
  notifier()
}

export function usePresence(compteId) {
  return useSyncExternalStore(sabonner, () => (compteId != null ? (etats.get(compteId) ?? null) : null))
}

// Pour un GROUPE (voir ConversationThreadScreen.jsx) — pas de "l'autre"
// unique, potentiellement plusieurs membres à suivre à la fois. Un hook
// par compte (comme usePresence ci-dessus) est impossible ici (nombre de
// membres variable, violerait les règles des Hooks) : on se réabonne
// juste aux changements de présence en général (`version`), et on relit
// la Map à chaque rendu — chaque tableau retourné est neuf à chaque appel,
// mais ce n'est PAS le "snapshot" comparé par React ici (seul `version`
// l'est), donc aucun risque de boucle infinie.
export function usePresenceListe(compteIds) {
  useSyncExternalStore(sabonner, () => version)
  return compteIds.map((id) => etats.get(id) ?? null)
}

// Texte affiché sous le nom, façon WhatsApp (voir
// ConversationThreadScreen.jsx) — `null` quand on n'a encore aucune
// info (ni SSE, ni chargement initial : ex. tout premier rendu).
export function libellePresence(etat) {
  if (!etat) return null
  if (etat.enLigne) return 'En ligne'
  if (!etat.derniereActiviteLe) return null
  const date = new Date(etat.derniereActiviteLe)
  const maintenant = new Date()
  const heure = date.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })
  if (date.toDateString() === maintenant.toDateString()) return `Vu aujourd'hui à ${heure}`
  const hier = new Date(maintenant)
  hier.setDate(hier.getDate() - 1)
  if (date.toDateString() === hier.toDateString()) return `Vu hier à ${heure}`
  return `Vu le ${date.toLocaleDateString('fr-FR')}`
}
