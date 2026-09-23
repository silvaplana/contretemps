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

// --- Notifications activées par défaut (demande du 2026-09-21) ---
//
// Aucun navigateur ne laisse un site activer les notifications tout seul :
// il faut l'accord de l'utilisateur, demandé PENDANT un geste de sa part.
// On profite donc du tout premier clic "Se connecter" sur cet appareil
// (voir LoginScreen.jsx) : la demande part pendant le clic, et si elle est
// acceptée, l'appareil est abonné dès que la connexion a réussi.
// Retenu sur l'appareil : jamais redemandé ensuite — et si l'utilisateur
// coupe les notifications dans Profil, on ne les réactive pas derrière
// son dos.
const CLE_PROPOSEES = 'contretemps:notificationsProposees'

function dejaProposees() {
  try {
    return localStorage.getItem(CLE_PROPOSEES) !== null
  } catch {
    return true // stockage indisponible : ne pas redemander à chaque fois
  }
}

// À appeler DANS le gestionnaire du clic (avant tout `await`) : renvoie une
// promesse de la permission, ou null s'il n'y a rien à faire (déjà
// proposé sur cet appareil, ou notifications non supportées).
export function proposerAuPremierLancement() {
  if (!pushSupporte() || dejaProposees()) return null
  try {
    localStorage.setItem(CLE_PROPOSEES, '1')
  } catch {
    // Tant pis : au pire, on reproposera une fois.
  }
  return permissionActuelle() === 'default' ? Notification.requestPermission() : Promise.resolve(permissionActuelle())
}

// --- Rattrapage : appli installée, réinstallée, déjà connectée ---
//
// La proposition ci-dessus n'a lieu qu'au premier "Se connecter" : une
// appli installée où l'on reste connecté ne la voit jamais, et après une
// réinstallation Android l'abonnement peut avoir disparu (signalé le
// 2026-09-21 : plus de notifications, donc plus de badge sur l'icône).
// Deux rattrapages, jamais contre un choix explicite de l'utilisateur :
// - permission déjà accordée mais aucun abonnement sur cet appareil :
//   réabonnement silencieux (aucune demande n'est affichée) ;
// - permission jamais demandée : bandeau "Activer" (components/
//   BandeauNotifications.jsx), le geste qu'exige le navigateur.
// "Coupées volontairement" = bouton Notifications éteint dans Profil
// (voir desabonner) : plus aucun rattrapage tant qu'il ne le rallume pas.
const CLE_COUPEES = 'contretemps:notificationsCoupees'
const CLE_BANDEAU_REPORTE = 'contretemps:notificationsBandeauReporte'
const SEPT_JOURS = 7 * 24 * 3600 * 1000

function lireLocal(cle) {
  try {
    return localStorage.getItem(cle)
  } catch {
    return null
  }
}

function ecrireLocal(cle, valeur) {
  try {
    if (valeur === null) localStorage.removeItem(cle)
    else localStorage.setItem(cle, valeur)
  } catch {
    // Stockage indisponible : le choix ne sera pas retenu, pas bloquant.
  }
}

function coupeesVolontairement() {
  return lireLocal(CLE_COUPEES) !== null
}

export async function reabonnerSiAutorise(compteId) {
  if (!pushSupporte() || coupeesVolontairement() || permissionActuelle() !== 'granted') return
  try {
    if (!(await estAbonneSurCetAppareil())) await abonner(compteId)
  } catch (err) {
    console.warn('Réabonnement aux notifications impossible :', err.message)
  }
}

// Saisons (spec §2.6) : après la bascule sur la nouvelle fiche de la même
// personne, l'abonnement de CET appareil (déjà actif, donc ignoré par
// reabonnerSiAutorise) pointe encore sur l'ancienne fiche côté serveur. On
// le rattache à la nouvelle — sans rien demander : la permission est déjà
// accordée, et le serveur met à jour l'abonnement existant (même endpoint).
export async function transfererAbonnement(compteId) {
  if (!pushSupporte() || coupeesVolontairement() || permissionActuelle() !== 'granted') return
  try {
    await abonner(compteId)
  } catch (err) {
    console.warn('Transfert des notifications impossible :', err.message)
  }
}

export function bandeauAProposer() {
  if (!pushSupporte() || coupeesVolontairement() || permissionActuelle() !== 'default') return false
  return Date.now() - Number(lireLocal(CLE_BANDEAU_REPORTE) || 0) >= SEPT_JOURS
}

export function reporterBandeau() {
  ecrireLocal(CLE_BANDEAU_REPORTE, String(Date.now()))
}

// Suite de proposerAuPremierLancement, une fois connecté : abonne cet
// appareil si la permission a été accordée. Jamais bloquant ni bruyant —
// la connexion a déjà réussi, un échec ici ne doit rien casser.
export async function abonnerSiAccepte(permissionPromise, compteId) {
  if (!permissionPromise) return
  try {
    if ((await permissionPromise) === 'granted') await abonner(compteId)
  } catch (err) {
    console.warn('Notifications non activées :', err.message)
  }
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
  ecrireLocal(CLE_COUPEES, null)
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
// ⚠️ Ne touche PAS au badge de l'icône (voir definirBadge ci-dessous) :
// rouvrir l'appli ne veut pas dire "tout est lu" (ex. on rouvre sur un
// autre onglet que Messagerie) — seul le VRAI total de non-lus doit
// piloter ce badge, recalculé à chaque changement (voir App.jsx).
export async function viderNotifications() {
  if (!pushSupporte()) return
  const registration = await navigator.serviceWorker.ready
  const notifications = await registration.getNotifications()
  notifications.forEach((n) => n.close())
}

// Badging API (voir MDN : Navigator.setAppBadge/clearAppBadge) — LE vrai
// moyen d'afficher un NOMBRE sur l'icône de l'appli (écran d'accueil),
// pas juste le point générique que certains lanceurs affichent par
// défaut quand il y a des notifications actives (demande : "un chiffre,
// pas un point"). Pas supporté partout (Firefox, Safari — voir
// caniuse.com "badging-api") : `'setAppBadge' in navigator` avant tout
// appel, sinon `TypeError`. Appelé à chaque fois que le total de
// non-lus change (voir App.jsx), même appli ouverte au premier plan —
// contrairement à viderNotifications ci-dessus, qui ne s'occupe que des
// notifications système, pas de ce badge-là.
export async function definirBadge(nombre) {
  if (!('setAppBadge' in navigator)) return
  try {
    if (nombre > 0) await navigator.setAppBadge(nombre)
    else await navigator.clearAppBadge()
  } catch {
    // Refusé par le navigateur (contexte non sécurisé, etc.) — pas
    // grave, l'icône garde alors son comportement par défaut.
  }
}

// Se désabonne : côté navigateur ET côté backend (sans le 2e, l'endpoint
// resterait en base et le backend continuerait à essayer de lui envoyer
// des notifications — échec silencieux, voir notifications.py, mais
// autant nettoyer proprement).
export async function desabonner() {
  if (!pushSupporte()) return
  // Seul appelant : le bouton de Profil — choix explicite, à respecter
  // (voir reabonnerSiAutorise / bandeauAProposer).
  ecrireLocal(CLE_COUPEES, '1')
  const registration = await navigator.serviceWorker.ready
  const subscription = await registration.pushManager.getSubscription()
  if (!subscription) return
  const { endpoint } = subscription.toJSON()
  await subscription.unsubscribe()
  await requete(`/push/abonnement?endpoint=${encodeURIComponent(endpoint)}`, { method: 'DELETE' })
}
