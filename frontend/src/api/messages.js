// Domaine "messagerie" (écran Messagerie — fil de discussion, voir
// spec/SPEC.md §5.5/§6.9). Réel uniquement (comme api/comptes.js) : "Voir
// une maquette" est retiré, plus de session démo à couvrir ici.
//
// Portée volontairement réduite (demande) : la liste des conversations et
// leurs messages sont bien réels (en base, filtrés par appartenance —
// c'était le bug signalé : Nora Pesenti voyait "Equipe pédagogique") et
// l'envoi persiste vraiment le message — mais PAS le routage/la
// réception : pas de marquage reçu/lu, pas de relance mail automatique,
// pas de vrai envoi WhatsApp. `statut` reste 'envoye' pour mes propres
// messages tant que rien ne les fait avancer côté serveur (à faire plus
// tard, voir backend/src/messagerie/messages.py: marquer_recu/marquer_lu/
// relancer_messages_non_lus, déjà prêts côté backend mais jamais appelés
// depuis cet écran).

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
  }
}

// Liste des conversations du compte + leurs messages, dans la forme
// attendue par MessagerieScreen.jsx (même forme que l'ancienne maquette,
// voir data/mockData.js : conversations, gardée pour ne pas devoir
// réécrire ConversationListScreen.jsx/ConversationThreadScreen.jsx). Un
// aperçu du dernier message dans la liste (§5.5) suppose d'avoir déjà les
// messages, d'où l'aller chercher ici plutôt qu'à l'ouverture de chaque
// conversation — peu de conversations par compte en pratique, pas un
// souci de perf.
export async function listerAvecMessages(ecoleId, compteId, cours) {
  const conversations = await requete(`/conversations?ecole_id=${ecoleId}&compte_id=${compteId}`)
  return Promise.all(
    conversations.map(async (conv) => {
      const messages = await requete(`/conversations/${conv.id}/messages`)
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

export async function envoyer(conversationId, compteId, membres, contenu, envoiVolontaireEmail = false) {
  const cree = await requete(`/conversations/${conversationId}/messages`, {
    method: 'POST',
    body: JSON.stringify({
      expediteur_id: compteId,
      contenu,
      envoi_volontaire_email: envoiVolontaireEmail,
    }),
  })
  return versMessageEcran(cree, compteId, membres)
}
