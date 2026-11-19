import { useEffect, useRef, useState } from 'react'
import { TAILLES, analyser, remplir, versBalises } from './texteRiche.js'

// Le texte d'une publication, mis en forme (§12.15).
export function TexteRiche({ texte, className }) {
  return (
    <p className={className}>
      {analyser(texte).map((m, i) => {
        let contenu = m.texte
        if (m.taille) contenu = <span className={`texte--${m.taille}`}>{contenu}</span>
        if (m.s) contenu = <u>{contenu}</u>
        if (m.g) contenu = <strong>{contenu}</strong>
        return <span key={i}>{contenu}</span>
      })}
    </p>
  )
}

// Les émojis du bouton ☺ (maquette « Texte mis en forme »).
const EMOJIS = [
  '🎄', '💃', '🎉', '❤️', '👏', '📅', '⚠️',
  '😊', '😍', '🤩', '😎', '😂', '😮', '😢',
  '👍', '🙏', '💪', '🔥', '🌟', '✨', '🏆',
  '🎶', '🩰', '🕺', '🥋', '📣', '📍', '⏰',
  '✅', '❌', '☀️', '❄️', '🎁', '🍾', '📸',
]

const ETAT_VIDE = { g: false, s: false, taille: 'normal' }

// L'éditeur : une barre B, U, Taille, ☺ au-dessus du texte. On sélectionne
// des mots puis on touche un bouton ; le retoucher enlève. `simple` : une
// Brève, du texte sans mise en forme (les émojis restent).
export function EditeurTexte({ valeur, onChange, simple = false }) {
  const bloc = useRef(null)
  const dernier = useRef(null) // le dernier texte écrit par le bloc lui-même
  const selection = useRef(null)
  const [etat, setEtat] = useState(ETAT_VIDE)
  const [menuTaille, setMenuTaille] = useState(false)
  const [emojis, setEmojis] = useState(false)

  // Remplir le bloc quand le texte change d'ailleurs (ouverture, partage…).
  useEffect(() => {
    if (valeur === dernier.current) return
    remplir(bloc.current, valeur)
    dernier.current = valeur
  }, [valeur])

  // Les boutons allumés suivent le curseur.
  useEffect(() => {
    const suivre = () => {
      const s = document.getSelection()
      if (!s?.rangeCount || !bloc.current?.contains(s.anchorNode)) return
      selection.current = s.getRangeAt(0).cloneRange()
      const taille = Number(document.queryCommandValue('fontSize'))
      setEtat({
        g: document.queryCommandState('bold'),
        s: document.queryCommandState('underline'),
        taille: taille <= 2 && taille > 0 ? 'petit' : taille >= 5 ? 'grand' : 'normal',
      })
    }
    document.addEventListener('selectionchange', suivre)
    return () => document.removeEventListener('selectionchange', suivre)
  }, [])

  const lire = () => {
    const texte = versBalises(bloc.current)
    if (!texte) bloc.current.replaceChildren() // l'invite « Écrivez… » revient
    dernier.current = texte
    onChange(texte)
  }
  // Le bouton touché ne doit pas faire perdre la sélection.
  const garder = (e) => e.preventDefault()
  const commande = (nom, valeur) => {
    bloc.current.focus()
    const s = document.getSelection()
    if (selection.current && !bloc.current.contains(s.anchorNode)) {
      s.removeAllRanges()
      s.addRange(selection.current)
    }
    document.execCommand('styleWithCSS', false, false)
    document.execCommand(nom, false, valeur)
    lire()
  }
  const coller = (e) => {
    // Seulement le texte : pas les couleurs ni les polices d'ailleurs.
    e.preventDefault()
    document.execCommand('insertText', false, e.clipboardData.getData('text/plain'))
  }

  return (
    <div className="texte-riche">
      <div className="texte-riche__barre" role="toolbar" aria-label="Mise en forme">
        {!simple && (
          <>
            <button type="button" className="texte-riche__gras" aria-label="Gras" aria-pressed={etat.g} onMouseDown={garder} onClick={() => commande('bold')}>
              B
            </button>
            <button type="button" className="texte-riche__souligne" aria-label="Souligné" aria-pressed={etat.s} onMouseDown={garder} onClick={() => commande('underline')}>
              U
            </button>
            <button type="button" className="texte-riche__taille" aria-expanded={menuTaille} onMouseDown={garder} onClick={() => setMenuTaille((x) => !x)}>
              Taille
              <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M6 9l6 6 6-6" />
              </svg>
            </button>
          </>
        )}
        <button type="button" className="texte-riche__emoji" aria-label="Émojis" aria-expanded={emojis} onMouseDown={garder} onClick={() => setEmojis((x) => !x)}>
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <circle cx="12" cy="12" r="9" />
            <path d="M8.5 14.5c1 1.3 2.2 2 3.5 2s2.5-.7 3.5-2" />
            <path d="M9 9.5h.01M15 9.5h.01" />
          </svg>
        </button>
      </div>
      {menuTaille && !simple && (
        <div className="texte-riche__tailles">
          {[['petit', 'Petit'], ['normal', 'Normal'], ['grand', 'Grand']].map(([cle, nom]) => (
            <button
              key={cle}
              type="button"
              className={`texte-riche__choix texte--${cle}`}
              aria-pressed={etat.taille === cle}
              onMouseDown={garder}
              onClick={() => {
                commande('fontSize', TAILLES[cle])
                setMenuTaille(false)
              }}
            >
              {nom}
            </button>
          ))}
        </div>
      )}
      {emojis && (
        <div className="texte-riche__emojis">
          <div className="texte-riche__emojis-entete">
            <strong>Émojis</strong>
            <button type="button" onMouseDown={garder} onClick={() => setEmojis(false)}>
              Fermer
            </button>
          </div>
          <div className="texte-riche__emojis-grille">
            {EMOJIS.map((e) => (
              <button key={e} type="button" onMouseDown={garder} onClick={() => commande('insertText', e)}>
                {e}
              </button>
            ))}
          </div>
        </div>
      )}
      <div
        ref={bloc}
        id="actu-texte"
        className="editeur__texte texte-riche__bloc"
        role="textbox"
        aria-multiline="true"
        aria-label="Texte"
        data-placeholder="Écrivez…"
        contentEditable
        suppressContentEditableWarning
        onInput={lire}
        onPaste={coller}
      />
    </div>
  )
}
