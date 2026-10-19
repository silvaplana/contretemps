import { useEffect, useState } from 'react'
import { blobPiece } from '../../api/messages.js'
import Icon from '../../components/Icon.jsx'
import { tailleLisible } from './piecesOutils.js'

// Photos et fichiers d'un message (spec/modules/messagerie-instantanee.md
// §4.3, §4.6) : la bulle ne charge que la vignette d'une photo ; la photo
// elle-même et les fichiers ne se chargent qu'en les touchant.

function useBlob(pieceId, options) {
  const [url, setUrl] = useState(null)
  useEffect(() => {
    let actif = true
    blobPiece(pieceId, options).then((u) => actif && setUrl(u), () => {})
    return () => {
      actif = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pieceId])
  return url
}

// Vignette d'une photo, à la bonne proportion dès avant son chargement
// (le fil ne saute pas).
function Vignette({ piece, onOuvrir, desactivee }) {
  const url = useBlob(piece.id, { vignette: true })
  const ratio = piece.width && piece.height ? `${piece.width} / ${piece.height}` : '4 / 3'
  return (
    <button
      type="button"
      className="piece-photo"
      style={{ aspectRatio: ratio }}
      onClick={(e) => {
        if (desactivee) return
        e.stopPropagation()
        onOuvrir(piece)
      }}
      aria-label={`Ouvrir la photo ${piece.filename}`}
    >
      {url && <img src={url} alt="" />}
    </button>
  )
}

async function telecharger(piece) {
  const url = await blobPiece(piece.id)
  const lien = document.createElement('a')
  lien.href = url
  lien.download = piece.filename
  lien.click()
}

function CarteFichier({ piece, desactivee }) {
  const [enCours, setEnCours] = useState(false)
  return (
    <button
      type="button"
      className="piece-fichier"
      disabled={enCours}
      onClick={async (e) => {
        if (desactivee) return
        e.stopPropagation()
        setEnCours(true)
        try {
          await telecharger(piece)
        } finally {
          setEnCours(false)
        }
      }}
    >
      <Icon name="docs" size={28} />
      <span className="piece-fichier__texte">
        <strong>{piece.filename}</strong>
        <span>{enCours ? 'Téléchargement…' : tailleLisible(piece.size)}</span>
      </span>
    </button>
  )
}

export function PiecesDuMessage({ pieces, onOuvrirPhoto, desactivees }) {
  if (pieces.length === 0) return null
  return (
    <div className="message-bubble__pieces">
      {pieces.map((p) =>
        p.kind === 'photo' ? (
          <Vignette key={p.id} piece={p} onOuvrir={onOuvrirPhoto} desactivee={desactivees} />
        ) : (
          <CarteFichier key={p.id} piece={p} desactivee={desactivees} />
        ),
      )}
    </div>
  )
}

// Photo en plein écran, chargée seulement maintenant (§4.6).
export function PhotoPleinEcran({ piece, onFermer }) {
  const url = useBlob(piece.id)
  return (
    <div className="photo-plein-ecran" role="dialog" aria-label={piece.filename}>
      <div className="photo-plein-ecran__barre">
        <button type="button" className="icon-btn" onClick={onFermer} aria-label="Fermer">
          <Icon name="x" size={24} />
        </button>
        {url && (
          <a className="btn btn--primary" href={url} download={piece.filename}>
            <Icon name="download" size={18} /> Télécharger
          </a>
        )}
      </div>
      {url ? <img src={url} alt={piece.filename} /> : <p>Chargement…</p>}
    </div>
  )
}
