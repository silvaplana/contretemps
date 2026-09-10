// Domaine "notifications push" (Web Push, voir spec/SPEC.md §8 et
// backend/src/notifications/) — active/désactive une vraie notification
// système, même appli/onglet fermé (contrairement au SSE, voir
// api/messages.js : ouvrirFluxEvenements, qui a besoin d'une page ouverte).
//
// Le bouton "Notifications" (ProfilScreen.jsx) pilote directement
// s'abonner()/se désabonner() — pas de bascule automatique au login : la
// permission navigateur doit être demandée sur un vrai geste utilisateur
// (un clic), jamais au chargement de la page (la plupart des navigateurs
// l'ignorent ou l'affichent au pire moment sinon).

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// 'granted' | 'denied' | 'default' (jamais encore demandé) — ni l'un ni
// l'autre ne dit si un ABONNEMENT existe déjà pour CET appareil, voir
// estAbonneSurCetAppareil ci-dessous.
export function permissionActuelle() {
  return 'Notification' in window ? Notification.permission : 'denied'
}

// Web Push n'existe pas partout (vieux Safari, navigateur sans Push API) —
// à vérifier avant de proposer le bouton, plutôt que de le laisser planter
// au clic.
export function pushSupporte() {
  return 'serviceWorker' in navigator && 'PushManager' in window
}

// 'https://B64Url...' -> Uint8Array, format attendu par
// PushManager.subscribe (applicationServerKey) — la clé VAPID publique
// arrive du backend en base64url standard (voir .env.example), jamais en
// ArrayBuffer directement.
function versUint8Array(base64Url) {
  const base64 = (base64Url + '='.repeat((4 - (base64Url.length % 4)) % 4))
    .replace(/-/g, '+')
    .replace(/_/g, '/')
  const brut = window.atob(base64)
  return Uint8Array.from(brut, (c) => c.charCodeAt(0))
}

// Abonnement DÉJÀ actif sur CET appareil/navigateur (indépendant de
// `permissionActuelle` : la permission peut être "granted" sans qu'un
// abonnement existe, ex. jamais cliqué sur le bouton, ou révoqué côté
// backend) — sert à l'affichage initial du bouton dans ProfilScreen.jsx.
export async function estAbonneSurCetAppareil() {
  if (!pushSupporte()) return false
  const registration = await navigator.serviceWorker.ready
  return (await registration.pushManager.getSubscription()) !== null
}

// S'abonne : demande la permission (geste utilisateur requis), récupère
// la clé publique VAPID côté backend, crée l'abonnement navigateur, puis
// l'enregistre côté backend (voir POST /comptes/{id}/push/abonnement).
// Lève une erreur explicite à chaque étape qui peut échouer (permission
// refusée, pas de clé VAPID configurée côté backend — voir .env.example).
export async function abonner(compteId) {
  if (!pushSupporte()) throw new Error('Notifications non supportées par ce navigateur')

  const permission = await Notification.requestPermission()
  if (permission !== 'granted') throw new Error('Permission refusée')

  const { cle_publique } = await requete('/push/cle-publique')
  if (!cle_publique) throw new Error('Notifications non configurées côté serveur')

  const registration = await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: versUint8Array(cle_publique),
  })
  const { endpoint, keys } = subscription.toJSON()

  await requete(`/comptes/${compteId}/push/abonnement`, {
    method: 'POST',
    body: JSON.stringify({ endpoint, keys }),
  })
}

// Ferme toutes les notifications système encore affichées pour cette
// origine (voir public/sw.js : showNotification) — appelé dès qu'on
// rouvre l'appli (voir App.jsx). Sans ça, le badge numéroté sur l'icône
// Android (qui compte les notifs PAS ENCORE balayées dans le tiroir, pas
// un vrai total géré par nous) reste bloqué au dernier chiffre : lire un
// message DANS l'appli ne ferme jamais, en soi, la notification système
// déjà affichée (signalé). On ferme tout plutôt qu'au cas par cas — le
// contenu du push (title/body, voir notifications.py: envoyer_a_compte)
// ne porte pas de conversation_id, pas de quoi cibler plus finement, et
// rouvrir l'appli les rend de toute façon redondantes (déjà visibles
// dans l'écran Messagerie).
export async function viderNotifications() {
  if (!pushSupporte()) return
  const registration = await navigator.serviceWorker.ready
  const notifications = await registration.getNotifications()
  notifications.forEach((n) => n.close())
}

// Se désabonne : côté navigateur ET côté backend (sans le 2e, l'endpoint
// resterait en base et le backend continuerait à essayer de lui envoyer
// des notifications — échec silencieux, voir notifications.py, mais
// autant nettoyer proprement).
export async function desabonner() {
  if (!pushSupporte()) return
  const registration = await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.getSubscription()
  if (!subscription) return
  const { endpoint } = subscription.toJSON()
  await subscription.unsubscribe()
  await requete(`/push/abonnement?endpoint=${encodeURIComponent(endpoint)}`, { method: 'DELETE' })
}
