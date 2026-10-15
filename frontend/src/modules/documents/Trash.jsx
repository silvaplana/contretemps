import { useEffect, useState } from 'react'
import { FileIcon, FolderIcon } from './icons.jsx'
import { formatDate } from './format.js'

// Corbeille (spec documents.md §6.0 bis) : 30 jours, puis effacé pour de
// bon. On y voit ce qu'on a supprimé soi-même (les admins voient tout).

export default function Trash({ api, space, spaceLabel, onClose, onRestored, onEmptied }) {
  const [liste, setListe] = useState(null)
  const [erreur, setErreur] = useState('')
  // Vider efface pour de bon, sans retour possible : une seule question
  // de confirmation (pas d'Annuler pendant 10 s ici).
  const [confirmer, setConfirmer] = useState(false)

  useEffect(() => {
    api.trash(space).then(setListe, (e) => setErreur(e.message))
  }, [api, space])

  async function restaurer(x) {
    try {
      await api.restore(x.id)
      setListe((l) => l.filter((y) => y.id !== x.id))
      onRestored(x)
    } catch (e) {
      setErreur(e.message)
    }
  }

  async function vider() {
    try {
      const { erased } = await api.emptyTrash(space)
      setListe([])
      setConfirmer(false)
      onEmptied(erased)
    } catch (e) {
      setErreur(e.message)
    }
  }

  return (
    <div className="dx-panel" role="dialog" aria-label="Corbeille">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Retour">←</button>
        <h2>Corbeille · {spaceLabel}</h2>
      </div>
      <div className="dx-list">
        <p className="dx-note dx-note--pad">Ce qui est ici est effacé pour de bon au bout de 30 jours.</p>
        {erreur && <p className="dx-error">{erreur}</p>}
        {liste?.length === 0 && <p className="dx-empty">La corbeille est vide.</p>}
        {liste?.length > 0 &&
          (confirmer ? (
            <div className="dx-trash-empty">
              <p>
                Effacer pour de bon {liste.length === 1 ? 'cet élément' : `ces ${liste.length} éléments`} ? On ne
                pourra plus {liste.length === 1 ? 'le' : 'les'} restaurer.
              </p>
              <button type="button" className="dx-btn dx-btn--danger" onClick={vider}>
                Oui, vider la corbeille
              </button>
              <button type="button" className="dx-btn dx-btn--ghost" onClick={() => setConfirmer(false)}>
                Non, garder
              </button>
            </div>
          ) : (
            <button type="button" className="dx-btn dx-btn--ghost dx-trash-empty" onClick={() => setConfirmer(true)}>
              Vider la corbeille
            </button>
          ))}
        {liste?.map((x) => (
          <div key={x.id} className="dx-row dx-row--static">
            {x.kind === 'folder' ? <FolderIcon /> : <FileIcon name={x.name} />}
            <div className="dx-meta">
              <div className="dx-n">{x.name}</div>
              <div className="dx-s">
                supprimé {formatDate(x.deleted_at)}
                {x.deleted_by && ` par ${x.deleted_by}`}
              </div>
            </div>
            <button type="button" className="dx-btn dx-btn--small" onClick={() => restaurer(x)}>
              Restaurer
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}
