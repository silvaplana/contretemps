// Domaine "messagerie" (écran Messagerie — fil de discussion, voir
// spec/SPEC.md §5.5/§6.9). Réel uniquement (comme api/comptes.js) : "Voir
// une maquette" est retiré, plus de session démo à couvrir ici.
//
// Portée : liste des conversations et leurs messages réels (en base,
// filtrés par appartenance — c'était le bug signalé : Nora Pesenti voyait
// "Equipe pédagogique"), envoi persisté, le marquage reçu/lu (voir
// marquerRecu/marquerLu ci-dessous, et ConversationThreadScreen.jsx) ET
// désormais la réception EN DIRECT via SSE (voir ouvrirFluxEvenements,
// appelé depuis App.jsx) — un nouveau message apparaît sans recharger
// l'écran.
// La relance automatique par mail après délai tourne côté backend (voir
// app/relance_worker.py, processus séparé) — pas appelée depuis ici.
//
// Toujours pas fait : le vrai envoi WhatsApp (canal='whatsapp' reste un
// marqueur d'intention, voir backend/src/messagerie/messages.py) — et,
// comme lui, la relance mail ne fait QUE changer le canal en base, aucune
// vraie infrastructure d'envoi de mail n'existe dans ce projet.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Délai avant abandon (voir utils/messageOutbox.js) — sans ça, sur un
// réseau mobile qui "pend" au lieu de couper franchement, une requête
// peut rester en attente indéfiniment et une bulle d'envoi restait
// bloquée "en cours" pour toujours (bug signalé : "des fois les messages
// n'arrivaient pas").
const DELAI_TIMEOUT_MS = 20000

async function requete(chemin, options) {
  const controleur = new AbortController()
  const minuteur = setTimeout(() => controleur.abort(), DELAI_TIMEOUT_MS)
  try {
    const reponse = await fetch(`${BASE_URL}${chemin}`, {
      headers: { 'Content-Type': 'application/json' },
      signal: controleur.signal,
      ...options,
    })
    if (!reponse.ok) {
      const erreur = new Error(`Requête échouée (${reponse.status})`)
      erreur.status = reponse.status
      throw erreur
    }
    return reponse.status === 204 ? null : reponse.json()
  } finally {
    clearTimeout(minuteur)
  }
}

// Le nom affiché : pour un DM, pas de `nom` propre côté backend (voir
// §6.9) — c'est l'autre personne, ça dépend du viewer, résolu ici.
// Pour un groupe, `nom_affiche` (voir backend/src/messagerie/
// conversations.py: nom_groupe_affiche) est déjà le bon nom à afficher,
// résolu côté SERVEUR — PAS en cherchant le cours dans la liste locale
// (bug signalé, demande utilisateur du 2026-09-19 : un cours tout juste
// créé par un autre compte n'était pas encore dans MA liste de cours,
// donc introuvable, d'où "Conversation" affiché à la place de son vrai
// nom). Le repli local ci-dessous ne reste que pour une éventuelle
// réponse plus ancienne sans ce champ (défensif, ne devrait plus arriver).
function nomAffiche(conv, compteId, cours) {
  if (conv.type === 'individuelle') {
    const autre = conv.membres.find((m) => m.id !== compteId)
    return autre ? `${autre.prenom} ${autre.nom}` : 'Conversation'
  }
  if (conv.nom_affiche) return conv.nom_affiche
  if (conv.nom) return conv.nom
  const blocCours = conv.blocs.length === 1 ? conv.blocs.find((b) => b.membre_type === 'cours') : null
  const coursTrouve = blocCours && cours.find((c) => c.id === blocCours.membre_id)
  return coursTrouve ? coursTrouve.nom : 'Conversation'
}

// Voir §5.5 : "icône agrégée" — un seul statut par message même en
// groupe (le détail par personne, accessible au tap, reste à faire).
function statutAgrege(deliveries) {
  if (deliveries.length === 0) return 'envoye'
  if (deliveries.every((d) => d.statut === 'lu')) return 'vu'
  if (deliveries.some((d) => d.statut === 'lu' || d.statut === 'recu')) return 'recu'
  return 'envoye'
}

// Exportée : réutilisée par ouvrirFluxEvenements ci-dessous pour adapter
// un message reçu en direct par SSE, exactement comme un message chargé
// via listerAvecMessages/envoyer.
export function versMessageEcran(message, compteId, membres) {
  const auteur = membres.find((m) => m.id === message.expediteur_id)
  const maDelivery = message.deliveries.find((d) => d.destinataire_id === compteId)
  return {
    id: message.id,
    // Présent seulement pour un message envoyé via envoyerBrut (voir
    // utils/messageOutbox.js) — sert à ne jamais afficher 2 fois le même
    // message si la bulle d'attente locale et l'arrivée SSE se
    // chevauchent (voir ConversationThreadScreen.jsx).
    clientId: message.client_id ?? null,
    auteur: auteur ? `${auteur.prenom} ${auteur.nom}` : '?',
    estMoi: message.expediteur_id === compteId,
    contenu: message.contenu,
    heure: new Date(message.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    statut: statutAgrege(message.deliveries),
    envoyeParMail: message.deliveries.some((d) => d.canal === 'email'),
    // Marqueur d'INTENTION seulement (voir backend/src/messagerie/
    // messages.py: envoyer) — aucun vrai envoi WhatsApp pour l'instant.
    envoyeParWhatsapp: message.deliveries.some((d) => d.canal === 'whatsapp'),
    // Sens inverse de `statut` ci-dessus : celui-là agrège le statut de
    // TOUS les destinataires pour MES messages (coches) ; celui-ci ne
    // regarde QUE ma propre delivery, pour un message qui n'est PAS de
    // moi — sert à compter les non-lus (voir ConversationListScreen.jsx,
    // BottomNav.jsx). Toujours `true` pour un message de moi (aucune
    // delivery à moi-même, voir messages.py: envoyer) : jamais compté
    // comme non lu de toute façon (filtré par `!estMoi` côté appelant).
    luParMoi: maDelivery ? maDelivery.statut === 'lu' : true,
  }
}

// Nombre de messages pas de moi et pas encore "lu" dans cette conversation
// (voir `luParMoi` ci-dessus) — utilisé pour le badge par conversation
// (ConversationListScreen.jsx) et, agrégé sur toutes les conversations,
// pour le point rouge global (App.jsx -> BottomNav.jsx).
export function compterNonLus(conversation) {
  return conversation.messages.filter((m) => !m.estMoi && !m.luParMoi).length
}

async function modifierStatutDelivery(messageId, destinataireId, statut) {
  await requete(`/messages/${messageId}/deliveries/${destinataireId}`, {
    method: 'PUT',
    body: JSON.stringify({ statut }),
  })
}

// "Reçu" = mon client a récupéré le message (voir listerAvecMessages,
// appelé dès l'ouverture de l'onglet Messagerie) ; "lu" = j'ai ouvert
// CETTE conversation pour de vrai (voir ConversationThreadScreen.jsx) —
// même distinction que WhatsApp (reçu sur l'appareil vs vu à l'écran).
export async function marquerRecu(messageId, compteId) {
  return modifierStatutDelivery(messageId, compteId, 'recu')
}

export async function marquerLu(messageId, compteId) {
  return modifierStatutDelivery(messageId, compteId, 'lu')
}

// Marque "lu" tous les messages d'un fil qui ne sont pas de moi — appelé
// à l'ouverture du fil (voir ConversationThreadScreen.jsx). Prend les
// messages déjà adaptés (voir versMessageEcran : `estMoi`), pas les
// bruts du backend.
export async function marquerLus(messages, compteId) {
  await Promise.all(messages.filter((m) => !m.estMoi).map((m) => marquerLu(m.id, compteId)))
}

// Partagé par listerAvecMessages et obtenirConversation ci-dessous — voir
// leurs commentaires respectifs pour le contexte de chacun.
//
// Marque aussi "reçu" chaque message qui n'est pas de moi et encore
// 'envoye' pour MA livraison — mon client vient bien de le récupérer, en
// le listant ici (voir marquerRecu ci-dessus). Fait avant l'adaptation
// (versMessageEcran) : le statut affiché tout de suite reste celui d'AVANT
// ce marquage (il ne se mettra à jour qu'au prochain chargement) — pas un
// souci, juste pas de faux sentiment de "déjà lu" instantané.
async function construireConversation(conv, compteId, cours) {
  const messages = await requete(`/conversations/${conv.id}/messages`)
  await Promise.all(
    messages
      .filter((m) => m.expediteur_id !== compteId)
      .filter((m) => m.deliveries.some((d) => d.destinataire_id === compteId && d.statut === 'envoye'))
      .map((m) => marquerRecu(m.id, compteId)),
  )
  return {
    id: conv.id,
    type: conv.type,
    nom: nomAffiche(conv, compteId, cours),
    membres: conv.membres,
    messages: messages.map((m) => versMessageEcran(m, compteId, conv.membres)),
  }
}

// Liste des conversations du compte + leurs messages, dans la forme
// attendue par MessagerieScreen.jsx/ConversationListScreen.jsx/
// ConversationThreadScreen.jsx (id/type/nom/membres/messages). Un
// aperçu du dernier message dans la liste (§5.5) suppose d'avoir déjà les
// messages, d'où l'aller chercher ici plutôt qu'à l'ouverture de chaque
// conversation — peu de conversations par compte en pratique, pas un
// souci de perf.
export async function listerAvecMessages(ecoleId, compteId, cours) {
  const conversations = await requete(`/conversations?ecole_id=${ecoleId}&compte_id=${compteId}`)
  return Promise.all(conversations.map((conv) => construireConversation(conv, compteId, cours)))
}

// Une conversation dont on connaît déjà l'id mais pas encore le contenu
// (voir App.jsx : arrivée d'un événement SSE `message` pour une
// conversation absente de l'état local — typiquement un DM tout juste
// créé par l'AUTRE partie, jamais vu par listerAvecMessages ci-dessus).
// Bug signalé : sans ça, ce premier message (et la conversation avec)
// n'apparaissait jamais tant que l'appli n'était pas rechargée en entier.
export async function obtenirConversation(conversationId, compteId, cours) {
  const conv = await requete(`/conversations/${conversationId}`)
  return construireConversation(conv, compteId, cours)
}

// canal : 'app' (défaut) | 'email' | 'whatsapp' — voir backend/src/
// messagerie/messages.py: envoyer() pour la nuance sur 'whatsapp'
// (marqueur d'intention, pas un vrai envoi pour l'instant).
//
// "Brut" : renvoie la forme backend telle quelle (pas adaptée via
// versMessageEcran) — utilisée par utils/messageOutbox.js, qui n'a pas
// toujours les `membres` sous la main (ex. reprise après rechargement de
// page) ; l'adaptation se fait dans App.jsx au moment d'insérer le
// résultat dans la conversation concernée. `client_id` : voir
// messageOutbox.js, permet un renvoi sûr sans jamais créer de doublon
// (voir backend/src/messagerie/messages.py: envoyer).
export async function envoyerBrut(conversationId, compteId, contenu, canal, clientId) {
  return requete(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ expediteur_id: compteId, contenu, canal, client_id: clientId }),
  })
}

// "Nouvelle discussion" depuis la recherche (voir ConversationListScreen.jsx,
// mode recherche façon WhatsApp) — récupère-ou-crée l'unique conversation
// individuelle entre les 2 comptes (voir backend/src/messagerie/
// conversations.py: create_ou_obtenir_dm, POST /dm) : jamais 2 fois la
// même paire, peu importe qui a initié le contact. Toujours sans message
// pour l'instant si elle vient d'être créée à l'instant (`lister_messages`
// renvoie alors une liste vide).
export async function creerOuObtenirDm(ecoleId, compteId, autreCompteId) {
  const conv = await requete(
    `/dm?ecole_id=${ecoleId}&compte_a_id=${compteId}&compte_b_id=${autreCompteId}`,
    { method: 'POST' },
  )
  const messages = await requete(`/conversations/${conv.id}/messages`)
  return {
    id: conv.id,
    type: conv.type,
    // `cours` inutile ici : nomAffiche ne le regarde que pour une
    // conversation de groupe, jamais pour une individuelle (voir plus haut).
    nom: nomAffiche(conv, compteId, []),
    membres: conv.membres,
    messages: messages.map((m) => versMessageEcran(m, compteId, conv.membres)),
  }
}

// Réception en direct (§5.5) : UN SEUL flux par compte connecté (voir
// backend/src/messagerie/evenements.py pour le choix "par compte" plutôt
// que "par conversation ouverte" — sans ça, la LISTE des conversations
// elle-même ne se mettrait à jour que pour le fil actuellement ouvert).
// Retourne une fonction de fermeture, à appeler à la déconnexion (voir
// App.jsx).
//
// `onEtatConnexion`/`onEcrit` : présence "en ligne"/"dernière connexion"
// et indicateur "en train d'écrire" (voir backend/src/messagerie/
// connexions.py et frappe.py) — mêmes flux SSE que les messages, pas de
// connexion séparée à ouvrir.
//
// `onReconnect` : bug signalé ("des fois les messages n'arrivent pas",
// surtout sur téléphone) — `Evenements.publier` (backend) ne fait rien
// si ce compte n'a AUCUN flux ouvert au moment où le message part (voir
// evenements.py) : un message envoyé PENDANT que le flux d'un téléphone
// est coupé (mise en arrière-plan, écran verrouillé, coupure réseau...)
// est donc perdu pour de bon côté push temps réel, pas juste retardé.
// `EventSource` reconnecte bien tout seul, mais seulement pour les
// événements FUTURS — d'où ce callback, appelé à CHAQUE reconnexion
// (automatique du navigateur, ou forcée ci-dessous), pour resynchroniser
// tout depuis le serveur et rattraper ce qui a pu être manqué entre
// temps (voir App.jsx : refait le même chargement qu'au login).
// `onConversationMaj`/`onConversationSupprimee` : composition/nom d'une
// conversation changé, ou disparue de chez ce compte (voir backend/src/
// messagerie/receiver.py : _publier_conversation_maj/
// _publier_conversation_supprimee) — création d'un groupe, renommage,
// ajout/retrait de membre, suppression. Demande utilisateur du
// 2026-09-18 : un groupe tout juste créé depuis Messagerie doit
// apparaître EN DIRECT chez les autres membres, pas seulement chez son
// créateur.
// `onMessageStatut` : une livraison de MON message a changé (reçu/lu par
// le destinataire — voir backend/src/messagerie/receiver.py :
// _publier_statut_message). Bug signalé : sans ça, la coche ne passait
// au bleu ("lu") que si je fermais et rouvrais le fil — jamais en direct
// pendant que l'autre lisait le message.
export function ouvrirFluxEvenements(
  compteId,
  {
    onMessage,
    onEtatConnexion,
    onEcrit,
    onReconnect,
    onConversationMaj,
    onConversationSupprimee,
    onMessageStatut,
  },
) {
  let dejaOuvertUneFois = false
  let source

  function creer() {
    const s = new EventSource(`${BASE_URL}/comptes/${compteId}/messagerie/evenements`)
    s.onopen = () => {
      if (dejaOuvertUneFois) onReconnect?.()
      dejaOuvertUneFois = true
    }
    s.onmessage = (e) => {
      const evenement = JSON.parse(e.data)
      if (evenement.type === 'message') onMessage(evenement)
      else if (evenement.type === 'etat_connexion') onEtatConnexion?.(evenement)
      else if (evenement.type === 'ecrit') onEcrit?.(evenement)
      else if (evenement.type === 'conversation_maj') onConversationMaj?.(evenement)
      else if (evenement.type === 'conversation_supprimee') onConversationSupprimee?.(evenement)
      else if (evenement.type === 'message_statut') onMessageStatut?.(evenement)
    }
    return s
  }

  source = creer()

  // Certains navigateurs mobiles (iOS Safari en tête) tardent à relancer
  // la reconnexion EventSource après une longue mise en arrière-plan —
  // on la force explicitement dans les 2 moments où une coupure a le
  // plus de chances de s'être produite, plutôt que de compter uniquement
  // sur le comportement natif (qui, lui, reste basé sur un simple délai
  // fixe, pas sur ces événements).
  function forcerReconnexion() {
    source.close()
    source = creer()
  }
  function surVisibilite() {
    if (document.visibilityState === 'visible') forcerReconnexion()
  }
  window.addEventListener('online', forcerReconnexion)
  document.addEventListener('visibilitychange', surVisibilite)

  return () => {
    source.close()
    window.removeEventListener('online', forcerReconnexion)
    document.removeEventListener('visibilitychange', surVisibilite)
  }
}

// "En train d'écrire" (voir utils/frappeIndicateur.js) — appelé au plus
// 1 fois toutes les ~3s pendant la frappe (throttle client), le backend
// throttle aussi de son côté (voir messagerie/frappe.py). Erreur ignorée
// par l'appelant (voir frappeIndicateur.js) : un ping raté n'a aucune
// conséquence grave, pas la peine de le faire échouer bruyamment.
export async function signalerFrappe(conversationId, compteId) {
  return requete(`/conversations/${conversationId}/ecrit`, {
    method: 'POST',
    body: JSON.stringify({ compte_id: compteId }),
  })
}
