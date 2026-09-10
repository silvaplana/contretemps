import { useEffect, useRef, useState } from 'react'
import * as messagesApi from '../../api/messages.js'
import Icon from '../../components/Icon.jsx'
import WhatsappBadge from '../../components/WhatsappBadge.jsx'
import { useFermerAuClicExterieur } from '../../hooks/useFermerAuClicExterieur.js'

const STATUT_ICON = { envoye: 'check', recu: 'checkCheck', vu: 'checkCheck' }

// Sélection volontairement courte plutôt qu'un clavier emoji complet
// (pas de dépendance externe à charger pour ça) — quelques essentiels
// façon WhatsApp, plus une poignée liée à la danse (🩰💃🕺), cohérente
// avec le thème de l'appli.
const EMOJIS = [
  '😀', '😂', '🥰', '😍', '😉', '😎', '🙂', '😢',
  '😭', '😡', '😱', '🤔', '👍', '👎', '👏', '🙏',
  '💪', '🙌', '🤝', '👋', '❤️', '💔', '🎉', '✨',
  '🔥', '💯', '💃', '🕺', '🎶', '🎵', '🩰', '☀️',
  '🌙', '⭐', '🎂', '🎈',
]

// Entrée envoie SEULEMENT sur un appareil à pointeur "fin" (souris/pavé
// tactile, typiquement un ordinateur) — sur un écran tactile (Android,
// iOS...), le clavier virtuel n'a pas de vraie touche Maj à combiner
// avec Entrée pour un retour à la ligne : `shiftKey` y reste toujours
// faux, donc Entrée y envoyait le message à chaque fois (signalé). Sur
// ces appareils, Entrée insère juste une ligne (comportement natif de la
// textarea, rien à faire) — l'envoi se fait via le bouton.
const ENTREE_ENVOIE = window.matchMedia('(pointer: fine)').matches

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
  const textareaRef = useRef(null)
  const [emojiOpen, setEmojiOpen] = useState(false)
  const emojiSelectorRef = useRef(null)
  useFermerAuClicExterieur(emojiSelectorRef, emojiOpen, () => setEmojiOpen(false))

  // Hauteur qui suit le contenu, façon WhatsApp (une ligne par défaut,
  // grandit jusqu'à un plafond CSS, voir .conversation-thread__input
  // textarea : au-delà, ça défile plutôt que de continuer à grandir).
  function ajusterHauteur(el) {
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }

  // Insère au niveau du curseur (pas juste à la fin) — sinon cliquer un
  // emoji après avoir replacé le curseur au milieu du texte l'enverrait
  // toujours à la fin, contre-intuitif.
  function insererEmoji(emoji) {
    const el = textareaRef.current
    const debut = el?.selectionStart ?? draft.length
    const fin = el?.selectionEnd ?? draft.length
    const nouveauDraft = draft.slice(0, debut) + emoji + draft.slice(fin)
    setDraft(nouveauDraft)
    setEmojiOpen(false)
    // Après le prochain rendu (la textarea doit d'abord recevoir la
    // nouvelle valeur) : redonne le focus et replace le curseur juste
    // après l'emoji, plutôt que de le laisser sauter à la fin.
    requestAnimationFrame(() => {
      if (!el) return
      el.focus()
      const position = debut + emoji.length
      el.setSelectionRange(position, position)
      ajusterHauteur(el)
    })
  }

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
  // du fil.
  //
  // Contrairement à avant : met AUSSI à jour `luParMoi` en local, tout de
  // suite (pas seulement côté serveur) — sert au badge de non-lus (voir
  // ConversationListScreen.jsx/BottomNav.jsx) : sans ça, le badge ne
  // retomberait à zéro qu'au prochain rechargement complet, pas à
  // l'ouverture du fil (signalé). Se limite aux messages VRAIMENT non lus
  // (`nonLus`) : évite de re-PUT en boucle des messages déjà "lu" à
  // chaque fois que ce fil se réaffiche (ex. un nouveau message dans une
  // AUTRE conversation ne fait pas grandir `messages.length` ici, mais un
  // nouveau rendu de ce composant sans changement de dépendance ne
  // redéclenche pas l'effet non plus — la garde reste utile si jamais).
  useEffect(() => {
    const nonLus = conversation.messages.filter((m) => !m.estMoi && !m.luParMoi)
    if (nonLus.length === 0) return
    messagesApi.marquerLus(nonLus, compteId)
    setConversations((liste) =>
      liste.map((c) =>
        c.id !== conversation.id
          ? c
          : { ...c, messages: c.messages.map((m) => (nonLus.includes(m) ? { ...m, luParMoi: true } : m)) },
      ),
    )
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
    // Revient à 1 ligne après l'envoi — sinon la textarea, agrandie
    // manuellement (voir ajusterHauteur), garde sa hauteur même une fois
    // vide.
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
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
              {/* white-space: pre-wrap (voir App.css) : un message écrit
                  sur plusieurs lignes (voir la textarea ci-dessous) doit
                  aussi s'afficher sur plusieurs lignes, pas être aplati
                  en un seul paragraphe comme le ferait un <p> normal. */}
              <p className="message-bubble__contenu">{m.contenu}</p>
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
        {emojiOpen && (
          <div className="emoji-picker" ref={emojiSelectorRef}>
            {EMOJIS.map((emoji) => (
              <button type="button" key={emoji} onClick={() => insererEmoji(emoji)}>
                {emoji}
              </button>
            ))}
          </div>
        )}
        <button
          type="button"
          className="icon-btn"
          onClick={() => setEmojiOpen((o) => !o)}
          aria-label="Insérer un emoji"
        >
          🙂
        </button>
        <textarea
          ref={textareaRef}
          value={draft}
          placeholder="Message"
          rows={1}
          onChange={(e) => {
            setDraft(e.target.value)
            ajusterHauteur(e.target)
          }}
          // Entrée seule -> envoie ; Maj+Entrée -> retour à la ligne —
          // mais SEULEMENT sur un appareil à pointeur fin (voir
          // ENTREE_ENVOIE) : sur écran tactile, Entrée reste toujours un
          // retour à la ligne (comportement natif), l'envoi se fait par
          // le bouton. `isComposing` : une touche Entrée qui valide une
          // saisie assistée (japonais/chinois...) ne doit pas envoyer le
          // message par accident.
          onKeyDown={(e) => {
            if (ENTREE_ENVOIE && e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
              e.preventDefault()
              send('app')
            }
          }}
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
