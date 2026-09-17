// "En train d'écrire" (voir backend/src/messagerie/frappe.py) — demande
// utilisateur du 2026-09-17. Aucun signal explicite "j'ai arrêté
// d'écrire" n'existe côté serveur (voir frappe.py) : c'est CE module qui
// fait expirer l'indicateur ~6s après le dernier event reçu.
import { useEffect, useRef, useSyncExternalStore } from 'react'
import * as messagesApi from '../api/messages.js'

const DELAI_EXPIRATION_MS = 6000
// Throttle d'ENVOI, séparé du throttle serveur (voir frappe.py) — celui
// côté serveur protège contre un client bogué, celui-ci évite de spammer
// une requête HTTP à chaque frappe de touche pour un client sain.
const DELAI_THROTTLE_ENVOI_MS = 3000

const frappeurs = new Map() // conversationId -> { compteId, expireLe }
const abonnes = new Set()

function notifier() {
  for (const f of abonnes) f()
}

function sabonner(f) {
  abonnes.add(f)
  return () => abonnes.delete(f)
}

// App.jsx : appelé à la réception d'un événement SSE `ecrit`.
export function signalerFrappeRecue(conversationId, compteId) {
  const expireLe = Date.now() + DELAI_EXPIRATION_MS
  frappeurs.set(conversationId, { compteId, expireLe })
  notifier()
  setTimeout(() => {
    const actuel = frappeurs.get(conversationId)
    // Un event plus récent a pu repousser `expireLe` entre-temps (encore
    // en train d'écrire) : ne l'efface que si c'est TOUJOURS celui-ci qui
    // doit expirer maintenant.
    if (actuel && actuel.expireLe <= Date.now()) {
      frappeurs.delete(conversationId)
      notifier()
    }
  }, DELAI_EXPIRATION_MS + 50)
}

// ConversationThreadScreen.jsx : qui est en train d'écrire dans CETTE
// conversation, ou `null`.
export function useFrappeEnCours(conversationId) {
  return useSyncExternalStore(sabonner, () => frappeurs.get(conversationId) ?? null)
}

// ConversationThreadScreen.jsx : à appeler à chaque frappe de touche
// dans le champ de saisie — throttlé en interne, sûr à appeler souvent.
export function useSignalerFrappe(conversationId, compteId) {
  const dernierEnvoiRef = useRef(0)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => {
    dernierEnvoiRef.current = 0
  }, [conversationId])
  return () => {
    const maintenant = Date.now()
    if (maintenant - dernierEnvoiRef.current < DELAI_THROTTLE_ENVOI_MS) return
    dernierEnvoiRef.current = maintenant
    messagesApi.signalerFrappe(conversationId, compteId).catch(() => {})
  }
}
