import { useEffect, useRef, useState } from 'react'
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
// WhatsApp : le canal 'whatsapp' (voir backend/src/messagerie/messages.py)
// n'est qu'un MARQUEUR d'intention — la case cochée reste visible après
// coup (badge sur la bulle), mais aucun message ne part réellement sur
// WhatsApp pour l'instant (Baileys pas branché, voir spec/SPEC.md §6.9/§8).
export default function ConversationThreadScreen({ conversation, onBack, setConversations, compteId }) {
  const [draft, setDraft] = useState('')
  const messagesRef = useRef(null)

  // Redescend en bas de la liste — à l'ouverture du fil (sinon on
  // atterrit en haut, sur les plus vieux messages) ET à chaque nouveau
  // message (envoyé par moi OU reçu en direct via SSE, voir App.jsx) —
  // sans ça, un message qui arrive pendant que le fil est déjà ouvert
  // peut s'afficher hors de l'écran, plus bas que ce qu'on voit
  // (signalé). Toujours instantané (pas de défilement animé) : sur un
  // gros fil, un scroll animé depuis le haut serait lent et brouillon.
  useEffect(() => {
    const el = messagesRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [conversation.id, conversation.messages.length])

  // Ouvrir ce fil = les avoir vus pour de vrai (façon WhatsApp, voir
  // api/messages.js: marquerLus) — distinct de "reçu" (marqué dès la
  // liste, voir api/messages.js: listerAvecMessages). Redéclenché aussi
  // quand `messages.length` grandit (pas seulement à l'ouverture du
  // fil) : un message qui arrive EN DIRECT (SSE, voir App.jsx) pendant
  // que ce fil est déjà affiché doit lui aussi passer "lu" tout de suite
  // — sans ça, il resterait affiché "reçu" jusqu'à la prochaine ouverture
  // du fil. marquerLus est idempotent (ré-appeler sur un message déjà
  // "lu" ne fait rien de mal), donc pas de souci à le refaire à chaque fois.
  // Ne met pas à jour l'affichage local des coches immédiatement (pas
  // grave : ce sont MES messages à moi qui les afficheraient, pas les
  // siens/leurs).
  useEffect(() => {
    messagesApi.marquerLus(conversation.messages, compteId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversation.id, conversation.messages.length])

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
    // 'mail' (nom local du bouton) -> 'email' (nom du canal côté backend).
    const canalBackend = canal === 'mail' ? 'email' : canal
    const message = await messagesApi.envoyer(conversation.id, compteId, conversation.membres, contenu, canalBackend)
    // Déjà là (le flux SSE de App.jsx a pu livrer ce même message avant
    // même que cette réponse de POST ne revienne — l'événement est
    // publié côté backend avant que la réponse HTTP ne soit renvoyée,
    // voir messagerie/receiver.py: envoyer_message) : pas de doublon.
    setConversations((list) =>
      list.map((c) => {
        if (c.id !== conversation.id) return c
        if (c.messages.some((m) => m.id === message.id)) return c
        return { ...c, messages: [...c.messages, message] }
      }),
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

      <div className="conversation-thread__messages" ref={messagesRef}>
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
