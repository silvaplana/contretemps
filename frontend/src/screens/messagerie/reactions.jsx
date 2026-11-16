import { useState } from 'react'
import Modal from '../../components/Modal.jsx'

// Réactions par emoji, comme WhatsApp (Seb, 16 novembre ; spec §4.12) : une
// par personne, une autre la remplace, toucher la sienne la retire. Mêmes
// emojis que les publications.
const EMOJIS = ['😊', '😍', '🤩', '😎', '👍', '❤️', '👏', '🙏', '😂', '😮', '😢', '🔥', '💪', '💃', '🌟', '🎉']
const RAPIDES = ['👍', '❤️', '😊', '😂', '😮', '🙏']

// Au-dessus du message choisi (appui long) : les plus courantes, + pour les autres.
export function ReactionsRapides({ mienne, onReagir, aDroite }) {
  const [toutes, setToutes] = useState(false)
  return (
    <div
      className={`reactions-rapides ${aDroite ? 'reactions-rapides--droite' : ''}`}
      onClick={(e) => e.stopPropagation()}
    >
      {(toutes ? EMOJIS : RAPIDES).map((e) => (
        <button
          key={e}
          type="button"
          className={e === mienne ? 'reactions-rapides--mienne' : ''}
          onClick={() => onReagir(e === mienne ? null : e)}
        >
          {e}
        </button>
      ))}
      {!toutes && (
        <button type="button" className="reactions-rapides__plus" aria-label="Autres emojis" onClick={() => setToutes(true)}>
          +
        </button>
      )}
    </div>
  )
}

// Sous la bulle : les emojis donnés et leur nombre ; toucher montre qui a réagi.
export function ReactionsDuMessage({ reactions, compteId, onRetirer, desactive }) {
  const [qui, setQui] = useState(false)
  if (reactions.length === 0) return null
  const emojis = [...new Set(reactions.map((r) => r.emoji))]
  return (
    <>
      <button
        type="button"
        className="message-bubble__reactions"
        disabled={desactive}
        onClick={(e) => {
          e.stopPropagation()
          setQui(true)
        }}
        aria-label="Qui a réagi"
      >
        {emojis.join('')}
        {reactions.length > 1 && <span>{reactions.length}</span>}
      </button>
      {qui && (
        <Modal title="Qui a réagi" onClose={() => setQui(false)}>
          <ul className="reactions-qui">
            {reactions.map((r) => (
              <li key={r.member_id}>
                <span className="reactions-qui__emoji">{r.emoji}</span>
                {r.member_id === compteId ? (
                  <button
                    type="button"
                    onClick={() => {
                      setQui(false)
                      onRetirer()
                    }}
                  >
                    Vous <span className="muted">· toucher pour retirer</span>
                  </button>
                ) : (
                  r.name
                )}
              </li>
            ))}
          </ul>
        </Modal>
      )}
    </>
  )
}
