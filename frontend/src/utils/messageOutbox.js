// File d'attente des messages en échec d'envoi — corrige le bug signalé
// ("des fois les messages n'arrivaient pas") : avant, le champ de saisie
// était vidé AVANT même de savoir si l'envoi avait réussi, sans aucun
// retry ni feedback — une coupure réseau au mauvais moment faisait
// disparaître le message tapé, sans trace.
//
// État EN DEHORS du cycle de vie React (module-level, comme
// utils/videoUploads.js) : un renvoi continue même si on quitte l'écran
// de conversation, et SURVIT à un rechargement de page (persisté en
// localStorage) — sans ça, fermer l'onglet pendant une coupure réseau
// perdrait quand même le message.
//
// Chaque message sortant passe par `client_id` (généré ici, voir
// backend/src/messagerie/messages.py: envoyer) : un renvoi après une
// réponse HTTP perdue ne crée donc jamais de doublon, même si le serveur
// avait déjà enregistré le message la 1re fois — c'est ce qui rend le
// retry automatique sûr.
import { useEffect, useMemo, useSyncExternalStore } from 'react'
import * as messagesApi from '../api/messages.js'

const CLE_STOCKAGE = 'contretemps-messages-en-attente'
// Backoff avec un peu de jitter — voir tenter() ci-dessous.
const DELAIS_RETRY_MS = [1000, 4000, 10000]

// clientId -> { conversationId, compteId, contenu, canal, etat: 'en_cours'|'echec', tentative, creeLe }
const enAttente = new Map()
const abonnesProgression = new Set()
const abonnesEnvoyes = new Set() // (messageBrut) => void

// `useSyncExternalStore` compare le résultat de getSnapshot par référence
// — lui renvoyer un `.filter().map()` frais à chaque appel le fait
// paraître "changé" à chaque rendu, donc une boucle de rendu infinie
// (vécu, corrigé). Un seul tableau, recalculé et RÉASSIGNÉ (nouvelle
// référence) uniquement quand `enAttente` change vraiment (voir
// `notifierProgression`), jamais à l'intérieur de getSnapshot lui-même.
let instantanne = []

function notifierProgression() {
  instantanne = Array.from(enAttente.entries()).map(([clientId, m]) => ({ clientId, ...m }))
  for (const f of abonnesProgression) f()
}

function sauvegarder() {
  try {
    localStorage.setItem(CLE_STOCKAGE, JSON.stringify(Array.from(enAttente.entries())))
  } catch {
    // Stockage indisponible (navigation privée...) — pas grave, juste
    // pas de reprise après un rechargement de page dans ce cas précis
    // (le retry en mémoire, lui, continue de fonctionner normalement).
  }
}

function restaurer() {
  try {
    const donnees = JSON.parse(localStorage.getItem(CLE_STOCKAGE) || '[]')
    for (const [clientId, m] of donnees) enAttente.set(clientId, { ...m, etat: 'en_cours', tentative: 0 })
  } catch {
    // idem
  }
  // Synchronise `instantanne` tout de suite (voir plus haut) — sans ça,
  // les bulles restaurées de localStorage resteraient invisibles tant
  // qu'aucune vraie mutation n'a eu lieu.
  instantanne = Array.from(enAttente.entries()).map(([clientId, m]) => ({ clientId, ...m }))
}
restaurer()

function sabonnerProgression(f) {
  abonnesProgression.add(f)
  return () => abonnesProgression.delete(f)
}

// Suivi des messages en attente D'UNE conversation — pour l'afficher
// comme bulles "en cours"/"échec" dans ConversationThreadScreen.jsx.
// `useMemo` (pas un filtre direct dans getSnapshot, voir plus haut) :
// ne recalcule que quand `instantanne` change vraiment, jamais à chaque
// rendu.
export function useMessagesEnAttente(conversationId) {
  const tout = useSyncExternalStore(sabonnerProgression, () => instantanne)
  return useMemo(() => tout.filter((m) => m.conversationId === conversationId), [tout, conversationId])
}

// App.jsx : insère le message dans la conversation concernée une fois
// l'envoi (ou le renvoi) réussi — quel que soit l'écran affiché à ce
// moment-là (voir utils/videoUploads.js pour le même principe).
export function useMessagesEnvoyes(onEnvoye) {
  useEffect(() => {
    abonnesEnvoyes.add(onEnvoye)
    return () => abonnesEnvoyes.delete(onEnvoye)
  }, [onEnvoye])
}

export function envoyerAvecReprise(conversationId, compteId, contenu, canal) {
  const clientId = crypto.randomUUID()
  enAttente.set(clientId, {
    conversationId,
    compteId,
    contenu,
    canal,
    etat: 'en_cours',
    tentative: 0,
    creeLe: Date.now(),
  })
  sauvegarder()
  notifierProgression()
  tenter(clientId)
}

async function tenter(clientId) {
  const m = enAttente.get(clientId)
  if (!m) return
  try {
    const messageBrut = await messagesApi.envoyerBrut(m.conversationId, m.compteId, m.contenu, m.canal, clientId)
    enAttente.delete(clientId)
    sauvegarder()
    notifierProgression()
    for (const f of abonnesEnvoyes) f(messageBrut)
  } catch (err) {
    if (!enAttente.has(clientId)) return // annulé/déjà réussi entre-temps
    // 4xx : un renvoi échouera identiquement (ex. conversation
    // supprimée) — pas la peine d'insister automatiquement.
    const definitif = err.status >= 400 && err.status < 500
    const tentative = m.tentative + 1
    if (!definitif && tentative <= DELAIS_RETRY_MS.length && navigator.onLine) {
      enAttente.set(clientId, { ...m, tentative })
      notifierProgression()
      setTimeout(() => tenter(clientId), DELAIS_RETRY_MS[tentative - 1] + Math.random() * 500)
    } else {
      enAttente.set(clientId, { ...m, etat: 'echec' })
      sauvegarder()
      notifierProgression()
    }
  }
}

// Tap sur une bulle en échec (voir ConversationThreadScreen.jsx).
export function reessayer(clientId) {
  const m = enAttente.get(clientId)
  if (!m) return
  enAttente.set(clientId, { ...m, etat: 'en_cours', tentative: 0 })
  notifierProgression()
  tenter(clientId)
}

function reprendreTout() {
  for (const clientId of enAttente.keys()) tenter(clientId)
}

if (typeof window !== 'undefined') {
  // Reconnexion réseau / retour au premier plan : les 2 moments où une
  // bulle bloquée a une vraie chance d'aboutir — voir aussi App.jsx pour
  // le même principe appliqué au flux SSE.
  window.addEventListener('online', reprendreTout)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') reprendreTout()
  })
  // Ce qui a été restauré de localStorage au chargement de la page
  // (fermeture de l'onglet pendant que des messages étaient en attente).
  if (enAttente.size > 0) reprendreTout()
}
