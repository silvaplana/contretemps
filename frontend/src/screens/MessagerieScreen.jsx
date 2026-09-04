import { useState } from 'react'
import ConversationListScreen from './messagerie/ConversationListScreen.jsx'
import ConversationThreadScreen from './messagerie/ConversationThreadScreen.jsx'

// Écran Messagerie (Admin, Professeur, Parent — voir spec/SPEC.md 5.5).
// Deux écrans distincts, comme WhatsApp : la liste des conversations, puis
// (au clic) le fil d'une conversation en plein écran avec une flèche de
// retour — jamais les deux affichés en même temps.
export default function MessagerieScreen({ conversations, setConversations }) {
  const [selectedId, setSelectedId] = useState(null)

  const selected = conversations.find((c) => c.id === selectedId)

  if (selected) {
    return (
      <ConversationThreadScreen
        conversation={selected}
        onBack={() => setSelectedId(null)}
        setConversations={setConversations}
      />
    )
  }

  return <ConversationListScreen conversations={conversations} onSelect={setSelectedId} />
}
