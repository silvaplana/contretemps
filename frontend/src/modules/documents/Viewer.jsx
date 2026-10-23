import { useEffect, useState } from 'react'
import { FileIcon, StatusBadge } from './icons.jsx'
import { isImage, isOffice, isPdf, isTexte } from './kinds.js'
import { subtitle } from './format.js'

// Ouvrir un fichier (spec documents.md §7.2) : photo en grand ; PDF dans la
// page ; Word, Excel, PowerPoint montrés par leur aperçu PDF (fait par le
// serveur avec LibreOffice) ; texte (.txt, .md, .csv) affiché, et
// modifiable par qui peut modifier (« Enregistrer » crée une nouvelle
// version, l'ancienne reste dans l'historique). Sinon une grande tuile avec
// Télécharger. Le contenu est lu avec la session puis montré par une URL blob:.

export default function Viewer({ api, item, onClose, onMore, onDownload, onSaved, onEditer }) {
  const [url, setUrl] = useState(null)
  const [texte, setTexte] = useState(null)
  const [brouillon, setBrouillon] = useState(null) // non null : en modification
  const [enregistrement, setEnregistrement] = useState(false)
  const [erreur, setErreur] = useState('')
  const office = isOffice(item)
  const enPdf = isPdf(item) || office
  // Téléphone : pas d'aperçu PDF dans la page, la fiche du fichier à la
  // place. Partout : Voir l'aperçu, Modifier, Télécharger côte à côte en bas
  // (Seb, 23 octobre).
  const sansVisionneuse = enPdf && !navigator.pdfViewerEnabled
  const apercu = isImage(item) || enPdf
  const estTexte = isTexte(item)
  const modifiable = estTexte && item.level !== 'view' && !item.closed_period && !item.frozen

  useEffect(() => {
    if (!apercu) return undefined
    let lien = null
    let annule = false
    api.blobUrl(item.id, { preview: office, modifie: item.updated_at }).then(
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
  }, [api, item.id, apercu, office, item.updated_at])

  useEffect(() => {
    if (!estTexte) return undefined
    let annule = false
    api.texte(item.id, item.updated_at).then(
      (t) => !annule && setTexte(t),
      (e) => !annule && setErreur(e.message),
    )
    return () => {
      annule = true
    }
  }, [api, item.id, estTexte, item.updated_at])

  async function enregistrer() {
    setEnregistrement(true)
    setErreur('')
    try {
      await api.newVersion(item.id, new File([brouillon], item.name, { type: 'text/plain' }))
      setTexte(brouillon)
      setBrouillon(null)
      onSaved?.(item)
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnregistrement(false)
    }
  }

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
        {enPdf && url && !sansVisionneuse && (
          <object className="dx-viewer__pdf" data={url} type="application/pdf" aria-label={item.name}>
            <Tuile item={item} onDownload={onDownload} apercuUrl={url} />
          </object>
        )}
        {sansVisionneuse && !erreur && <Tuile item={item} />}
        {office && erreur && <Tuile item={item} onDownload={onDownload} />}
        {estTexte &&
          (brouillon != null ? (
            <textarea
              className="dx-viewer__texte dx-viewer__texte--edition"
              value={brouillon}
              onChange={(e) => setBrouillon(e.target.value)}
              autoFocus
              spellCheck
            />
          ) : (
            texte != null && <pre className="dx-viewer__texte">{texte || '(fichier vide)'}</pre>
          ))}
        {!apercu && !estTexte && <Tuile item={item} onDownload={onDownload} />}
        {((apercu && !url) || (estTexte && texte == null)) && !erreur && (
          <p className="dx-muted">{office ? 'Préparation de l’aperçu…' : 'Chargement…'}</p>
        )}
      </div>
      {((apercu && !(office && erreur && !onEditer)) || estTexte) && (
        <div className="dx-footer dx-footer--rang">
          {brouillon != null ? (
            <>
              <button type="button" className="dx-btn dx-btn--ghost" disabled={enregistrement} onClick={() => setBrouillon(null)}>
                Annuler
              </button>
              <button type="button" className="dx-btn" disabled={enregistrement || brouillon === texte} onClick={enregistrer}>
                {enregistrement ? 'Enregistrement…' : 'Enregistrer'}
              </button>
            </>
          ) : (
            <>
              {enPdf && url && (
                <a className={`dx-btn${office && onEditer ? ' dx-btn--ghost' : ''}`} href={url} target="_blank" rel="noreferrer">
                  Voir l’aperçu
                </a>
              )}
              {modifiable && texte != null && (
                <button type="button" className="dx-btn" onClick={() => setBrouillon(texte)}>
                  Modifier
                </button>
              )}
              {office && onEditer && (
                <button type="button" className="dx-btn" onClick={() => onEditer(item)}>
                  Modifier
                </button>
              )}
              <button type="button" className="dx-btn dx-btn--ghost" onClick={() => onDownload(item)}>
                Télécharger
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

// Quand l'aperçu ne s'affiche pas dans la page (PDF sur certains
// téléphones) : l'ouvrir dans un nouvel onglet, ou télécharger le fichier.
function Tuile({ item, onDownload, apercuUrl }) {
  return (
    <div className="dx-tuile">
      <FileIcon name={item.name} family={item.family} />
      <div className="dx-n">{item.name}</div>
      <div className="dx-s">
        {item.status && <StatusBadge status={item.status} />} {subtitle(item)}
      </div>
      {apercuUrl && (
        <a className="dx-btn" href={apercuUrl} target="_blank" rel="noreferrer">
          Voir l’aperçu
        </a>
      )}
      {onDownload && (
        <>
          <button type="button" className={`dx-btn${apercuUrl ? ' dx-btn--ghost' : ''}`} onClick={() => onDownload(item)}>
            Télécharger
          </button>
          <p className="dx-muted dx-small">Il s’ouvrira avec l’application de votre téléphone ou de votre ordinateur (Word, Excel…).</p>
        </>
      )}
    </div>
  )
}
