import { useState } from 'react'
import * as messagesApi from '../../api/messages.js'
import Icon from '../../components/Icon.jsx'
import WhatsappBadge from '../../components/WhatsappBadge.jsx'

const STATUT_ICON = { envoye: 'check', recu: 'checkCheck', vu: 'checkCheck' }

// Écran 2/2 de la Messagerie : le fil d'UNE conversation, plein écran, avec
// une flèche de retour vers ConversationListScreen (voir MessagerieScreen.jsx)
// — comme l'écran de discussion de WhatsApp. Coches de statut façon WhatsApp ;
// le choix messagerie/mail/whatsapp se fait à l'envoi (voir send ci-dessous),
// et l'icône dans la bulle n'est qu'un indicatif de ce choix a posteriori
// (voir spec/SPEC.md 5.5).
//
// WhatsApp : juste l'écran pour l'instant (voir spec/SPEC.md §6.9 et §8) —
// aucun vrai envoi (le backend n'a pas de canal 'whatsapp', seulement
// 'app'/'email'), seulement la confirmation avant d'envoyer normalement,
// comme "prévoir le tuyau" avant de brancher Baileys plus tard.
export default function ConversationThreadScreen({ conversation, onBack, setConversations, compteId }) {
  const [draft, setDraft] = useState('')

  // Choix à l'envoi : par la messagerie (par défaut), par mail, ou par
  // WhatsApp — mail et WhatsApp sortent de l'appli, donc demandent
  // confirmation. En groupe, WhatsApp n'a pas de vrai fil unique côté
  // WhatsApp (pas de groupe WhatsApp = plusieurs messages 1-à-1) : la
  // confirmation le dit explicitement.
  async function send(canal) {
    if (!draft.trim()) return
    if (canal === 'mail' && !window.confirm('Envoyer aussi ce message par mail ?')) return
    if (canal === 'whatsapp') {
      const question =
        conversation.type === 'groupe'
          ? 'Ce message sera envoyé par WhatsApp séparément à chaque membre de la conversation. Confirmer ?'
          : 'Envoyer ce message par WhatsApp ?'
      if (!window.confirm(question)) return
    }
    const contenu = draft.trim()
    setDraft('')
    const message = await messagesApi.envoyer(
      conversation.id,
      compteId,
      conversation.membres,
      contenu,
      canal === 'mail',
    )
    setConversations((list) =>
      list.map((c) => (c.id === conversation.id ? { ...c, messages: [...c.messages, message] } : c)),
    )
  }

  return (
    <div className="thread-screen">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour aux conversations">
          <Icon name="chevronLeft" size={22} />
        </button>
        <span className={`avatar avatar--sm ${conversation.type === 'groupe' ? 'avatar--groupe' : ''}`}>
          {conversation.type === 'groupe' ? (
            <Icon name="users" size={16} />
          ) : (
            conversation.nom.slice(0, 2).toUpperCase()
          )}
        </span>
        <span className="thread-screen__header-text">
          <strong>{conversation.nom}</strong>
          <span className="muted">{conversation.type === 'groupe' ? 'Groupe' : 'Conversation'}</span>
        </span>
      </div>

      <div className="conversation-thread__messages">
        {conversation.messages.map((m) => (
          <div key={m.id} className={`message-row ${m.estMoi ? 'message-row--moi' : ''}`}>
            <div className="message-bubble">
              {!m.estMoi && conversation.type === 'groupe' && (
                <span className="message-bubble__auteur">{m.auteur}</span>
              )}
              <p>{m.contenu}</p>
              <span className="message-bubble__meta">
                {m.heure}
                {m.estMoi && <Icon name={STATUT_ICON[m.statut]} size={14} />}
                {m.envoyeParMail && <Icon name="mail" size={14} />}
                {m.envoyeParWhatsapp && <WhatsappBadge size={14} />}
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="conversation-thread__input">
        <input
          value={draft}
          placeholder="Écrire un message..."
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send('app')}
        />
        <button
          type="button"
          className="icon-btn icon-btn--accent"
          onClick={() => send('app')}
          aria-label="Envoyer par la messagerie"
        >
          <Icon name="send" size={18} />
        </button>
        <button
          type="button"
          className="icon-btn icon-btn--mail"
          onClick={() => send('mail')}
          aria-label="Envoyer par mail"
        >
          <Icon name="mail" size={18} />
        </button>
        <button
          type="button"
          className="icon-btn icon-btn--mail"
          onClick={() => send('whatsapp')}
          aria-label="Envoyer par WhatsApp"
        >
          <WhatsappBadge size={18} />
        </button>
      </div>
    </div>
  )
}
