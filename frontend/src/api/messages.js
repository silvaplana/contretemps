// Domaine "messagerie" (écran Messagerie — fil de discussion, voir
// spec/SPEC.md §5.5/§6.9). Réel uniquement (comme api/comptes.js) : "Voir
// une maquette" est retiré, plus de session démo à couvrir ici.
//
// Portée : liste des conversations et leurs messages réels (en base,
// filtrés par appartenance — c'était le bug signalé : Nora Pesenti voyait
// "Equipe pédagogique"), envoi persisté, ET désormais le marquage
// reçu/lu (voir marquerRecu/marquerLu ci-dessous, et ConversationThreadScreen.jsx).
// La relance automatique par mail après délai tourne côté backend (voir
// app/relance_worker.py, processus séparé) — pas appelée depuis ici.
//
// Toujours pas fait : le vrai envoi WhatsApp (canal='whatsapp' reste un
// marqueur d'intention, voir backend/src/messagerie/messages.py) — et,
// comme lui, la relance mail ne fait QUE changer le canal en base, aucune
// vraie infrastructure d'envoi de mail n'existe dans ce projet.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// Le nom affiché : pour un DM, pas de `nom` propre côté backend (voir
// §6.9) — c'est l'autre personne. Pour un groupe, son nom, ou celui du
// cours s'il n'en a pas (conversation automatique de cours — même repli
// que AdminGroupes.jsx : nomAffiche).
function nomAffiche(conv, compteId, cours) {
  if (conv.type === 'individuelle') {
    const autre = conv.membres.find((m) => m.id !== compteId)
    return autre ? `${autre.prenom} ${autre.nom}` : 'Conversation'
  }
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

function versMessageEcran(message, compteId, membres) {
  const auteur = membres.find((m) => m.id === message.expediteur_id)
  return {
    id: message.id,
    auteur: auteur ? `${auteur.prenom} ${auteur.nom}` : '?',
    estMoi: message.expediteur_id === compteId,
    contenu: message.contenu,
    heure: new Date(message.created_at).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
    statut: statutAgrege(message.deliveries),
    envoyeParMail: message.deliveries.some((d) => d.canal === 'email'),
    // Marqueur d'INTENTION seulement (voir backend/src/messagerie/
    // messages.py: envoyer) — aucun vrai envoi WhatsApp pour l'instant.
    envoyeParWhatsapp: message.deliveries.some((d) => d.canal === 'whatsapp'),
  }
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

// Liste des conversations du compte + leurs messages, dans la forme
// attendue par MessagerieScreen.jsx/ConversationListScreen.jsx/
// ConversationThreadScreen.jsx (id/type/nom/membres/messages). Un
// aperçu du dernier message dans la liste (§5.5) suppose d'avoir déjà les
// messages, d'où l'aller chercher ici plutôt qu'à l'ouverture de chaque
// conversation — peu de conversations par compte en pratique, pas un
// souci de perf.
//
// Marque aussi "reçu" chaque message qui n'est pas de moi et encore
// 'envoye' pour MA livraison — mon client vient bien de le récupérer, en
// le listant ici (voir marquerRecu ci-dessus). Fait avant l'adaptation
// (versMessageEcran) : le statut affiché tout de suite reste celui d'AVANT
// ce marquage (il ne se mettra à jour qu'au prochain chargement) — pas un
// souci, juste pas de faux sentiment de "déjà lu" instantané.
export async function listerAvecMessages(ecoleId, compteId, cours) {
  const conversations = await requete(`/conversations?ecole_id=${ecoleId}&compte_id=${compteId}`)
  return Promise.all(
    conversations.map(async (conv) => {
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
    }),
  )
}

// canal : 'app' (défaut) | 'email' | 'whatsapp' — voir backend/src/
// messagerie/messages.py: envoyer() pour la nuance sur 'whatsapp'
// (marqueur d'intention, pas un vrai envoi pour l'instant).
export async function envoyer(conversationId, compteId, membres, contenu, canal = 'app') {
  const cree = await requete(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ expediteur_id: compteId, contenu, canal }),
  })
  return versMessageEcran(cree, compteId, membres)
}
