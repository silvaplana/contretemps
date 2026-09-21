import { useState } from 'react'
import * as conversationsApi from '../../api/conversations.js'
import { estVide } from './ConversationEditModal.jsx'

// Logique d'édition d'une conversation de groupe, partagée par Admin >
// Messagerie et Admin > Cours (voir ConversationEditModal.jsx) — opère
// sur le `groupes`/`setGroupes` possédé par AdminScreen.jsx et redescendu
// aux deux écrans, pour qu'une conversation créée depuis Admin > Cours
// apparaisse tout de suite dans la liste d'Admin > Messagerie sans
// rechargement.
export function useConversationEditor(groupes, setGroupes) {
  const [editId, setEditIdRaw] = useState(null)
  // Accompagne `editId` d'un flag "nouvelle" décidé par l'appelant (voir
  // ConversationEditModal.jsx pour pourquoi ça ne peut pas se déduire de
  // `estVide` seul) : `setEditId(id)` pour ouvrir une conversation
  // existante (titre "Modifier — ..."), `setEditId(id, { nouvelle: true
  // })` juste après une création (titre "Nouvelle conversation").
  const [nouvelle, setNouvelle] = useState(false)
  const enEdition = groupes.find((g) => g.id === editId)

  function setEditId(id, { nouvelle: estNouvelle = false } = {}) {
    setNouvelle(estNouvelle)
    setEditIdRaw(id)
  }

  function remplacer(id, patch) {
    setGroupes((list) => list.map((g) => (g.id === id ? { ...g, ...patch } : g)))
  }

  async function renameGroupe(id, nom) {
    remplacer(id, { nom }) // optimiste : l'input ne doit pas attendre le réseau
    await conversationsApi.renommer(id, nom)
  }

  async function addMembre(groupeId, membre) {
    const nouvelle = await conversationsApi.ajouterMembre(groupeId, membre)
    remplacer(groupeId, { membres: [...groupes.find((g) => g.id === groupeId).membres, nouvelle ?? membre] })
  }

  async function removeMembre(groupeId, membre, index) {
    remplacer(groupeId, {
      membres: groupes.find((g) => g.id === groupeId).membres.filter((_, i) => i !== index),
    })
    await conversationsApi.retirerMembre(groupeId, membre, index)
  }

  async function creerGroupeWhatsapp(id) {
    if (
      !window.confirm(
        'Créer un groupe WhatsApp lié à cette conversation ? Cette action ne peut pas être annulée depuis cet écran.',
      )
    ) {
      return
    }
    const miroir = await conversationsApi.creerGroupeWhatsapp(id)
    remplacer(id, { whatsappStatut: miroir.whatsappStatut, whatsappGroupeId: miroir.whatsappGroupeId })
  }

  // Referme la modale — supprime la conversation si elle est ressortie
  // vide (voir estVide), pour ne jamais laisser une conversation fantôme
  // créée par erreur (clic sur "+" puis "Fermer" sans rien remplir).
  async function fermerEdition() {
    if (enEdition && estVide(enEdition)) {
      await conversationsApi.supprimer(enEdition.id)
      setGroupes((list) => list.filter((g) => g.id !== enEdition.id))
    }
    setEditId(null)
  }

  return {
    editId,
    setEditId,
    enEdition,
    nouvelle,
    renameGroupe,
    addMembre,
    removeMembre,
    creerGroupeWhatsapp,
    fermerEdition,
  }
}
