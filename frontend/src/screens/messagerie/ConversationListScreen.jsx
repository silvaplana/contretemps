import Icon from '../../components/Icon.jsx'

// Écran 1/2 de la Messagerie (voir spec/SPEC.md 5.5) : liste des
// conversations. Cliquer une conversation ouvre ConversationThreadScreen
// (voir MessagerieScreen.jsx) — comme la liste de discussions de WhatsApp.
export default function ConversationListScreen({ conversations, onSelect }) {
  return (
    <div className="conversation-list-screen">
      {conversations.map((c) => {
        const last = c.messages[c.messages.length - 1]
        return (
          <button
            key={c.id}
            type="button"
            className="conversation-list__item"
            onClick={() => onSelect(c.id)}
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
      {conversations.length === 0 && <p className="muted">Aucune conversation.</p>}
    </div>
  )
}
