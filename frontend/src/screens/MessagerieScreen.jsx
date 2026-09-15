import { useState } from 'react'
import * as messagesApi from '../api/messages.js'
import ConversationListScreen from './messagerie/ConversationListScreen.jsx'
import ConversationThreadScreen from './messagerie/ConversationThreadScreen.jsx'
import ProfilContactScreen from './messagerie/ProfilContactScreen.jsx'

// Écran Messagerie (Admin, Professeur, Élève — voir spec/SPEC.md 5.5).
// 3 écrans distincts, comme WhatsApp, jamais 2 affichés en même temps :
// - la liste des conversations (état par défaut) ;
// - (clic sur le TEXTE d'une ligne) le fil d'une conversation en plein
//   écran, avec une flèche de retour ;
// - (clic sur l'AVATAR d'une ligne) la "carte" du profil correspondant
//   (voir ProfilContactScreen.jsx), avec ses 2 actions Message/Infos.
export default function MessagerieScreen({
  conversations,
  setConversations,
  compteId,
  ecoleId,
  admins,
  professeurs,
  eleves,
}) {
  const [selectedId, setSelectedId] = useState(null)
  // Profil affiché en carte (voir ConversationListScreen.jsx :
  // onAvatarClick) — { type: 'conversation', conversation } ou
  // { type: 'contact', compte }, ou null hors de ce mode.
  const [profilCible, setProfilCible] = useState(null)
  // Garde-fou contre un double-clic sur "Message" (carte de profil) ou
  // sur une ligne "Nouvelle discussion" pendant que la création du DM est
  // en cours (même principe qu'ailleurs, voir AdminCours.jsx/AdminEleves.jsx).
  const [creationEnCours, setCreationEnCours] = useState(false)

  const selected = conversations.find((c) => c.id === selectedId)

  // Crée (ou récupère si elle existe déjà) le DM avec ce compte puis
  // l'ouvre — partagé entre le clic sur une ligne "Nouvelle discussion"
  // ET le bouton "Message" de la carte de profil pour un `type: 'contact'`
  // (voir ProfilContactScreen.jsx), pour ne jamais dupliquer cette logique.
  async function ouvrirAvecContact(compte) {
    if (creationEnCours) return
    setCreationEnCours(true)
    try {
      const conv = await messagesApi.creerOuObtenirDm(ecoleId, compteId, compte.id)
      setConversations((liste) => (liste.some((c) => c.id === conv.id) ? liste : [...liste, conv]))
      setProfilCible(null)
      setSelectedId(conv.id)
    } finally {
      setCreationEnCours(false)
    }
  }

  if (selected) {
    return (
      <ConversationThreadScreen
        conversation={selected}
        onBack={() => setSelectedId(null)}
        setConversations={setConversations}
        compteId={compteId}
      />
    )
  }

  if (profilCible) {
    return (
      <ProfilContactScreen
        cible={profilCible}
        compteId={compteId}
        onBack={() => setProfilCible(null)}
        contacterEnCours={creationEnCours}
        onMessage={() => {
          if (profilCible.type === 'conversation') {
            setSelectedId(profilCible.conversation.id)
            setProfilCible(null)
          } else {
            ouvrirAvecContact(profilCible.compte)
          }
        }}
      />
    )
  }

  return (
    <ConversationListScreen
      conversations={conversations}
      onOpenConversation={setSelectedId}
      onOpenContact={ouvrirAvecContact}
      onAvatarClick={setProfilCible}
      compteId={compteId}
      admins={admins}
      professeurs={professeurs}
      eleves={eleves}
      contactActionEnCours={creationEnCours}
    />
  )
}
