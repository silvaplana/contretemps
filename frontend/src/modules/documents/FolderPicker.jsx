import { useEffect, useState } from 'react'
import { FolderIcon } from './icons.jsx'

// « Déplacer… » et « Copier vers… » : on descend dans les dossiers, puis
// « Déplacer ici ». Seuls les dossiers où l'on peut ajouter sont choisis.

export default function FolderPicker({ api, spaces, items, mode, startSpace, startFolder, onClose, onPick }) {
  const ids = items.map((x) => x.id)
  const titre = items.length > 1 ? `${items.length} éléments` : `« ${items[0].name} »`
  const [space, setSpace] = useState(startSpace)
  const [folder, setFolder] = useState(startFolder)
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let annule = false
    api.browse(space, folder).then(
      (x) => !annule && (setData(x), setErreur('')),
      (e) => !annule && setErreur(e.message),
    )
    return () => {
      annule = true
    }
  }, [api, space, folder])

  const dossiers = (data?.items ?? []).filter((x) => x.kind === 'folder' && !ids.includes(x.id))
  const ici = data && data.can_add && !ids.includes(data.folder?.id)
  const verbe = mode === 'copy' ? 'Copier' : 'Déplacer'
  const remonter = () => {
    const fil = data?.breadcrumb ?? []
    setFolder(fil.length > 1 ? fil[fil.length - 2].id : null)
  }

  return (
    <div className="dx-panel" role="dialog" aria-label={`${verbe} ${titre}`}>
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Fermer">✕</button>
        <h2>{verbe} vers…</h2>
      </div>
      <div className="dx-seg">
        {spaces.map((s) => (
          <button key={s.key} type="button" className={s.key === space ? 'on' : ''} onClick={() => (setSpace(s.key), setFolder(null))}>
            {s.label}
          </button>
        ))}
      </div>
      <div className="dx-crumb">
        {folder ? (
          <button type="button" className="dx-link" onClick={remonter}>‹ Remonter</button>
        ) : (
          <span>{spaces.find((s) => s.key === space)?.label}</span>
        )}
        {data?.folder && <b> {data.folder.name}</b>}
      </div>
      <div className="dx-list dx-list--picker">
        {erreur && <p className="dx-error">{erreur}</p>}
        {dossiers.length === 0 && data && <p className="dx-empty">Pas de sous-dossier ici.</p>}
        {dossiers.length > 0 && (
          <div className="dx-dirs">
            {dossiers.map((x) => (
              <button key={x.id} type="button" className="dx-row dx-row--dir" onClick={() => setFolder(x.id)}>
                <FolderIcon restricted={x.restricted} />
                <span className="dx-meta">
                  <span className="dx-n">{x.name}</span>
                  {x.closed_period && <span className="dx-s">saison terminée</span>}
                </span>
                <span className="dx-chev">›</span>
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="dx-footer">
        <button type="button" className="dx-btn" disabled={!ici} onClick={() => onPick(space, folder)}>
          {verbe} ici
        </button>
        {data && !data.can_add && <p className="dx-muted dx-small">Vous ne pouvez pas ajouter dans ce dossier.</p>}
      </div>
    </div>
  )
}
