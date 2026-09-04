import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import { currentUser } from '../data/mockData.js'

const STATUT_ICON = { envoye: 'check', recu: 'checkCheck', vu: 'checkCheck' }

// Écran Messagerie (Admin, Professeur, Parent — voir spec/SPEC.md 5.5 et
// images/messagerie.png + messagerie2.png). Liste de conversations en haut,
// fil de la conversation sélectionnée en bas, avec coches de statut façon
// WhatsApp et un bouton "envoyer par mail" par message.
export default function MessagerieScreen({ conversations, setConversations }) {
  const [selectedId, setSelectedId] = useState(conversations[0]?.id ?? null)
  const [draft, setDraft] = useState('')

  const selected = conversations.find((c) => c.id === selectedId)

  function sendMessage() {
    if (!draft.trim() || !selected) return
    const message = {
      id: crypto.randomUUID(),
      auteur: `${currentUser.prenom} ${currentUser.nom}`,
      estMoi: true,
      contenu: draft.trim(),
      heure: new Date().toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }),
      statut: 'envoye',
      envoyeParMail: false,
    }
    setConversations((list) =>
      list.map((c) => (c.id === selectedId ? { ...c, messages: [...c.messages, message] } : c)),
    )
    setDraft('')
  }

  function toggleMail(messageId) {
    setConversations((list) =>
      list.map((c) =>
        c.id !== selectedId
          ? c
          : {
              ...c,
              messages: c.messages.map((m) =>
                m.id === messageId ? { ...m, envoyeParMail: !m.envoyeParMail } : m,
              ),
            },
      ),
    )
  }

  return (
    <div className="screen messagerie-screen">
      <div className="conversation-list">
        <p className="conversation-list__title">Conversations</p>
        {conversations.map((c) => {
          const last = c.messages[c.messages.length - 1]
          return (
            <button
              key={c.id}
              type="button"
              className={`conversation-list__item ${c.id === selectedId ? 'is-active' : ''}`}
              onClick={() => setSelectedId(c.id)}
            >
              <span className={`avatar avatar--sm ${c.type === 'groupe' ? 'avatar--groupe' : ''}`}>
                {c.type === 'groupe' ? <Icon name="users" size={16} /> : c.nom.slice(0, 2).toUpperCase()}
              </span>
              <span className="conversation-list__text">
                <strong>{c.nom}</strong>
                <span className="muted">{last?.contenu}</span>
              </span>
              {last?.envoyeParMail && <Icon name="mail" size={16} className="muted" />}
            </button>
          )
        })}
      </div>

      {selected && (
        <div className="conversation-thread">
          <p className="conversation-thread__header">
            <strong>{selected.nom}</strong>
            <span className="muted">{selected.type === 'groupe' ? 'Groupe' : 'Conversation'}</span>
          </p>

          <div className="conversation-thread__messages">
            {selected.messages.map((m) => (
              <div key={m.id} className={`message-row ${m.estMoi ? 'message-row--moi' : ''}`}>
                <div className="message-bubble">
                  {!m.estMoi && selected.type === 'groupe' && (
                    <span className="message-bubble__auteur">{m.auteur}</span>
                  )}
                  <p>{m.contenu}</p>
                  <span className="message-bubble__meta">
                    {m.heure}
                    {m.estMoi && <Icon name={STATUT_ICON[m.statut]} size={14} />}
                    {m.envoyeParMail && <Icon name="mail" size={14} />}
                  </span>
                </div>
                <button
                  type="button"
                  className={`message-mail-btn ${m.envoyeParMail ? 'is-on' : ''}`}
                  onClick={() => toggleMail(m.id)}
                  aria-label="Envoyer par mail"
                >
                  <Icon name="mail" size={14} />
                </button>
              </div>
            ))}
          </div>

          <div className="conversation-thread__input">
            <input
              value={draft}
              placeholder="Écrire un message..."
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && sendMessage()}
            />
            <button type="button" className="icon-btn icon-btn--accent" onClick={sendMessage} aria-label="Envoyer">
              <Icon name="send" size={18} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
