import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import { taille } from './format.js'

// Écrire (spec/modules/mail.md §7) : écran plein, « De : » l'adresse du club,
// À, Cc / Cci, Objet, message, pièces jointes (18 Mo au plus), Envoyer. Le
// mail part au bout des 10 s d'Annuler (§8, Boite.jsx).

const MAX = 18 * 1024 * 1024
const TITRES = { new: 'Nouveau message', reply: 'Répondre', replyAll: 'Répondre à tous', forward: 'Transférer' }

export default function Ecrire({ brouillon, fichiersInitiaux = [], de, onFermer, onEnvoyer }) {
  const [to, setTo] = useState(brouillon.to)
  const [cc, setCc] = useState(brouillon.cc)
  const [bcc, setBcc] = useState(brouillon.bcc ?? '')
  const [copies, setCopies] = useState(Boolean(brouillon.cc || brouillon.bcc))
  const [subject, setSubject] = useState(brouillon.subject)
  const [body, setBody] = useState(brouillon.body)
  const [fichiers, setFichiers] = useState(fichiersInitiaux)
  const [erreur, setErreur] = useState(null)
  const texte = useRef(null)
  const total = fichiers.reduce((s, f) => s + f.size, 0)

  // Réponse : curseur tout en haut, au-dessus du mail cité.
  useEffect(() => {
    if (brouillon.mode === 'reply' || brouillon.mode === 'replyAll') {
      texte.current?.focus()
      texte.current?.setSelectionRange(0, 0)
    }
  }, [brouillon.mode])

  function envoyer(e) {
    e.preventDefault()
    if (!to.trim() && !cc.trim() && !bcc.trim()) {
      setErreur('Indiquez à qui envoyer le mail')
      return
    }
    onEnvoyer({ ...brouillon, to, cc, bcc, subject, body }, fichiers)
  }

  return createPortal(
    <div className="creer-saison" role="dialog" aria-label={TITRES[brouillon.mode]}>
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onFermer} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">{TITRES[brouillon.mode]}</h2>
      </div>
      <form className="creer-saison__corps mail mail__ecrire" onSubmit={envoyer}>
        <div className="mail__champ-ligne">
          <span>De</span>
          <span className="mail__discret">{de}</span>
        </div>
        <label className="mail__champ-ligne">
          <span>À</span>
          <input
            value={to}
            onChange={(e) => setTo(e.target.value)}
            inputMode="email"
            autoCapitalize="none"
            autoFocus={brouillon.mode === 'new' || brouillon.mode === 'forward'}
          />
          {!copies && (
            <button type="button" className="mail__lien" onClick={() => setCopies(true)}>
              Cc / Cci
            </button>
          )}
        </label>
        {copies && (
          <>
            <label className="mail__champ-ligne">
              <span>Cc</span>
              <input value={cc} onChange={(e) => setCc(e.target.value)} inputMode="email" autoCapitalize="none" />
            </label>
            <label className="mail__champ-ligne">
              <span>Cci</span>
              <input value={bcc} onChange={(e) => setBcc(e.target.value)} inputMode="email" autoCapitalize="none" />
            </label>
          </>
        )}
        <label className="mail__champ-ligne">
          <span>Objet</span>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} />
        </label>
        <textarea
          ref={texte}
          className="mail__corps"
          aria-label="Message"
          value={body}
          onChange={(e) => setBody(e.target.value)}
          rows={12}
        />

        {(brouillon.forwardAttachments?.length > 0 || fichiers.length > 0) && (
          <div className="mail__pieces">
            {brouillon.forwardAttachments?.map((p) => (
              <span key={`t${p.index}`} className="mail__piece">
                <Icon name="paperclip" />
                <span>
                  {p.filename}
                  <small>{taille(p.size)}</small>
                </span>
              </span>
            ))}
            {fichiers.map((f, i) => (
              <span key={`${f.name}-${i}`} className="mail__piece">
                <Icon name="paperclip" />
                <span>
                  {f.name}
                  <small>{taille(f.size)}</small>
                </span>
                <button
                  type="button"
                  className="icon-btn"
                  aria-label={`Retirer ${f.name}`}
                  onClick={() => setFichiers((liste) => liste.filter((_, j) => j !== i))}
                >
                  <Icon name="x" />
                </button>
              </span>
            ))}
          </div>
        )}
        {total > MAX && <p className="login-screen__erreur">Pièces jointes trop lourdes : 18 Mo au total au maximum.</p>}
        {erreur && <p className="login-screen__erreur">{erreur}</p>}

        <label className="btn btn--secondary mail__joindre">
          <Icon name="paperclip" /> Joindre un fichier
          <input
            type="file"
            multiple
            hidden
            onChange={(e) => {
              const choisis = [...e.target.files]
              setFichiers((liste) => [...liste, ...choisis])
              e.target.value = ''
            }}
          />
        </label>
        <button type="submit" className="btn btn--primary btn--block mail__principal" disabled={total > MAX}>
          Envoyer
        </button>
      </form>
    </div>,
    document.body,
  )
}
