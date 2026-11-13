import { useState } from 'react'
import { createPortal } from 'react-dom'
import Modal from './Modal.jsx'
import './Sondage.css'

// Sondage, comme dans WhatsApp (Seb, 13 novembre ; maquette « Sondage »),
// dans une publication et dans une discussion : une question, de 2 à 10 réponses, une seule ou plusieurs. On touche une
// réponse pour voter, on la retouche pour changer d'avis ; les barres et les
// nombres se voient tout de suite, « Voir les votes » montre qui a voté quoi.

export const MAX_REPONSES = 10
export const sondageVide = () => ({ question: '', plusieurs: false, reponses: ['', ''] })

// Ce qui manque pour publier, ou ''.
export function manqueSondage(s) {
  if (!s) return ''
  if (!s.question.trim()) return 'Écrivez la question du sondage'
  if (s.reponses.filter((r) => r.trim()).length < 2) return 'Donnez au moins 2 réponses'
  return ''
}

// La carte. `onVoter(ids)` enregistre le vote et rend le sondage à jour ;
// absent là où l'on ne vote pas (aperçu de l'éditeur, brouillon).
// `desactive` : pendant une sélection de messages.
export function Sondage({ sondage, onVoter = null, desactive = false }) {
  // Après un vote, la réponse du serveur ; sinon ce que donne la carte.
  const [apresVote, setApresVote] = useState(null)
  const s = apresVote ?? sondage
  const [votes, setVotes] = useState(false)
  const [envoi, setEnvoi] = useState(false)
  const peutVoter = Boolean(onVoter) && !desactive
  const total = s.options.reduce((n, o) => n + o.votants.length, 0)
  const aVote = s.options.some((o) => o.moi)

  async function voter(option) {
    if (!peutVoter || envoi) return
    const miens = s.options.filter((o) => o.moi).map((o) => o.id)
    let choix
    if (option.moi) choix = miens.filter((id) => id !== option.id)
    else choix = s.plusieurs ? [...miens, option.id] : [option.id]
    setEnvoi(true)
    try {
      setApresVote(await onVoter(choix))
    } catch (e) {
      window.alert(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div className="sondage">
      <strong className="sondage__question">{s.question}</strong>
      <span className="sondage__consigne">
        {s.plusieurs ? 'Plusieurs réponses possibles' : 'Une seule réponse'}
        {peutVoter && !aVote ? ' · touchez pour voter' : ''}
      </span>
      {s.options.map((o) => (
        <button
          key={o.id ?? o.libelle}
          type="button"
          className={`sondage__option ${o.moi ? 'sondage__option--moi' : ''}`}
          aria-pressed={o.moi}
          disabled={!peutVoter}
          onClick={() => voter(o)}
        >
          <span className="sondage__ligne">
            <span className={`sondage__case ${s.plusieurs ? 'sondage__case--carree' : ''}`} aria-hidden="true" />
            <span className="sondage__libelle">{o.libelle}</span>
            <b>{o.votants.length}</b>
          </span>
          <span className="sondage__barre">
            <span style={{ width: `${total ? Math.round((o.votants.length / total) * 100) : 0}%` }} />
          </span>
        </button>
      ))}
      <div className="sondage__pied">
        <span>
          {s.votants} {s.votants > 1 ? 'votes' : 'vote'}
        </span>
        {s.votants > 0 && (
          <button type="button" className="sondage__voir" disabled={desactive} onClick={() => setVotes(true)}>
            Voir les votes
          </button>
        )}
      </div>
      {/* Hors de la bulle d'un message : ni sa couleur, ni son appui long. */}
      {votes &&
        createPortal(
          <div onClick={(e) => e.stopPropagation()} onPointerDown={(e) => e.stopPropagation()}>
            <Modal title={s.question} onClose={() => setVotes(false)}>
              <ul className="sondage__votes">
                {s.options.map((o) => (
                  <li key={o.id}>
                    <b>
                      {o.libelle} · {o.votants.length}
                    </b>
                    <span>{o.votants.join(', ') || 'Personne'}</span>
                  </li>
                ))}
              </ul>
            </Modal>
          </div>,
          document.body,
        )}
    </div>
  )
}

// Dans l'éditeur : la question, les réponses (✕ pour en retirer une,
// « + Ajouter une réponse »), et « Plusieurs réponses possibles ».
export function EditeurSondage({ sondage, onChanger }) {
  const changer = (champs) => onChanger({ ...sondage, ...champs })
  const reponse = (i, texte) => changer({ reponses: sondage.reponses.map((r, j) => (j === i ? texte : r)) })
  return (
    <div className="sondage-editeur">
      <label className="sondage-editeur__champ">
        <span className="actus__periode">Question</span>
        <input value={sondage.question} maxLength={200} placeholder="Quel jour pour le stage ?" onChange={(e) => changer({ question: e.target.value })} />
      </label>
      <span className="actus__periode">Réponses</span>
      {sondage.reponses.map((r, i) => (
        <div key={i} className="sondage-editeur__reponse">
          <input aria-label={`Réponse ${i + 1}`} value={r} maxLength={100} placeholder={`Réponse ${i + 1}`} onChange={(e) => reponse(i, e.target.value)} />
          {sondage.reponses.length > 2 && (
            <button type="button" aria-label={`Retirer la réponse ${i + 1}`} onClick={() => changer({ reponses: sondage.reponses.filter((_, j) => j !== i) })}>
              ✕
            </button>
          )}
        </div>
      ))}
      {sondage.reponses.length < MAX_REPONSES && (
        <button type="button" className="sondage-editeur__ajouter" onClick={() => changer({ reponses: [...sondage.reponses, ''] })}>
          + Ajouter une réponse
        </button>
      )}
      <label className="sondage-editeur__plusieurs">
        <span>Plusieurs réponses possibles</span>
        <input type="checkbox" checked={sondage.plusieurs} onChange={(e) => changer({ plusieurs: e.target.checked })} />
      </label>
    </div>
  )
}

// L'aperçu de l'éditeur : le sondage tel qu'il sera, sans votes.
export const sondageEnApercu = (s) => ({
  question: s.question.trim() || 'Question',
  plusieurs: s.plusieurs,
  votants: 0,
  options: s.reponses.filter((r) => r.trim()).map((r, i) => ({ id: `a${i}`, libelle: r.trim(), votants: [], moi: false })),
})
