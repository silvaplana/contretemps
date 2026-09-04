import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { currentUser } from '../../data/mockData.js'

const STATUT_ICON = { envoye: 'check', recu: 'checkCheck', vu: 'checkCheck' }

// Écran 2/2 de la Messagerie : le fil d'UNE conversation, plein écran, avec
// une flèche de retour vers ConversationListScreen (voir MessagerieScreen.jsx)
// — comme l'écran de discussion de WhatsApp. Coches de statut façon WhatsApp ;
// le choix messagerie/mail se fait à l'envoi (voir send ci-dessous), et
// l'icône mail dans la bulle n'est qu'un indicatif de ce choix a posteriori
// (voir spec/SPEC.md 5.5).
export default function ConversationThreadScreen({ conversation, onBack, setConversations }) {
  const [draft, setDraft] = useState('')

  // Choix à l'envoi : par la messagerie (par défaut) ou par mail — l'envoi
  // par mail demande confirmation car il sort de l'appli.
  function send(parMail) {
    if (!draft.trim()) return
    if (parMail && !window.confirm('Envoyer aussi ce message par mail ?')) return
    const message = {
      id: crypto.randomUUID(),
      auteur: `${currentUser.prenom} ${currentUser.nom}`,
      estMoi: true,
      contenu: draft.trim(),
      heure: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
      statut: 'envoye',
      envoyeParMail: parMail,
    }
    setConversations((list) =>
      list.map((c) => (c.id === conversation.id ? { ...c, messages: [...c.messages, message] } : c)),
    )
    setDraft('')
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
          onKeyDown={(e) => e.key === 'Enter' && send(false)}
        />
        <button
          type="button"
          className="icon-btn icon-btn--mail"
          onClick={() => send(true)}
          aria-label="Envoyer par mail"
        >
          <Icon name="mail" size={18} />
        </button>
        <button
          type="button"
          className="icon-btn icon-btn--accent"
          onClick={() => send(false)}
          aria-label="Envoyer par la messagerie"
        >
          <Icon name="send" size={18} />
        </button>
      </div>
    </div>
  )
}
