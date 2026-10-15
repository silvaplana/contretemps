import { useEffect, useState } from 'react'
import { FileIcon, StatusBadge } from './icons.jsx'
import { isImage, isPdf } from './kinds.js'
import { subtitle } from './format.js'

// Ouvrir un fichier importé (spec documents.md §7.2) : photo en grand, PDF
// dans la page (sur ordinateur), sinon une grande tuile avec Télécharger.
// Le contenu est lu avec la session puis montré par une URL blob:.

export default function Viewer({ api, item, onClose, onMore, onDownload }) {
  const [url, setUrl] = useState(null)
  const [erreur, setErreur] = useState('')
  const apercu = isImage(item) || isPdf(item)

  useEffect(() => {
    if (!apercu) return undefined
    let lien = null
    let annule = false
    api.blobUrl(item.id).then(
      (u) => {
        if (annule) URL.revokeObjectURL(u)
        else setUrl((lien = u))
      },
      (e) => !annule && setErreur(e.message),
    )
    return () => {
      annule = true
      if (lien) URL.revokeObjectURL(lien)
    }
  }, [api, item.id, apercu])

  return (
    <div className="dx-panel dx-viewer" role="dialog" aria-label={item.name}>
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
        <h2 className="dx-viewer__title">{item.name}</h2>
        <button type="button" className="dx-ico" onClick={() => onMore(item)} aria-label="Actions">⋯</button>
      </div>
      <div className="dx-viewer__body">
        {erreur && <p className="dx-error">{erreur}</p>}
        {isImage(item) && url && <img className="dx-viewer__img" src={url} alt={item.name} />}
        {isPdf(item) && url && (
          <object className="dx-viewer__pdf" data={url} type="application/pdf" aria-label={item.name}>
            <Tuile item={item} onDownload={onDownload} />
          </object>
        )}
        {!apercu && <Tuile item={item} onDownload={onDownload} />}
        {apercu && !url && !erreur && <p className="dx-muted">Chargement…</p>}
      </div>
      {apercu && (
        <div className="dx-footer">
          <button type="button" className="dx-btn dx-btn--ghost" onClick={() => onDownload(item)}>Télécharger</button>
        </div>
      )}
    </div>
  )
}

function Tuile({ item, onDownload }) {
  return (
    <div className="dx-tuile">
      <FileIcon name={item.name} family={item.family} />
      <div className="dx-n">{item.name}</div>
      <div className="dx-s">
        {item.status && <StatusBadge status={item.status} />} {subtitle(item)}
      </div>
      <button type="button" className="dx-btn" onClick={() => onDownload(item)}>Télécharger</button>
      <p className="dx-muted dx-small">Il s’ouvrira avec l’application de votre téléphone ou de votre ordinateur (Word, Excel…).</p>
    </div>
  )
}
