import { useState } from 'react'
import './app/app.css'

// « Convoquer l’AG » (spec procurations.md §1.3) : deux questions
// seulement, ordinaire ou extraordinaire puis la date et l'heure. L'appli
// écrit la convocation (ordre du jour de l'an dernier, sinon de base) et la
// range dans Réunions ; si elle hésite entre deux dossiers, elle demande.
// Ensuite le fichier s'ouvre en Brouillon : c'est l'aperçu modifiable.

const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

export default function ConvoquerAG({ api, onClose, onCreated }) {
  const [kind, setKind] = useState('ordinary')
  const [jour, setJour] = useState('')
  const [heure, setHeure] = useState('14:00')
  const [dossiers, setDossiers] = useState(null) // { folders, new_name }
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState('')

  async function preparer(folderId, nouveau) {
    setEnvoi(true)
    setErreur('')
    try {
      const r = await api.convene(kind, `${jour}T${heure}`, folderId, nouveau)
      if (r.folders) setDossiers(r)
      else onCreated(r)
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  const d = jour ? new Date(`${jour}T12:00`) : null
  const titre = d ? `${kind === 'ordinary' ? 'AGO' : 'AGE'} du ${d.getDate()} ${MOIS[d.getMonth()]} ${d.getFullYear()}` : ''

  return (
    <div className="dx-panel dx-panel--up" role="dialog" aria-label="Convoquer l’AG">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={dossiers ? () => setDossiers(null) : onClose} aria-label="Retour">←</button>
        <h2>Convoquer l’AG</h2>
      </div>
      {dossiers ? (
        <div className="dx-body">
          <p className="dx-q">Où ranger la convocation ?</p>
          {dossiers.folders.map((f) => (
            <button key={f.id} type="button" className="dx-act" disabled={envoi} onClick={() => preparer(f.id, false)}>
              <i>📁</i>
              <span>Réunions › {f.name}</span>
            </button>
          ))}
          <button type="button" className="dx-act" disabled={envoi} onClick={() => preparer(null, true)}>
            <i>＋</i>
            <span>Nouveau dossier « {dossiers.new_name} »</span>
          </button>
          {erreur && <p className="dx-error" role="alert">{erreur}</p>}
        </div>
      ) : (
        <form
          className="dx-body"
          onSubmit={(e) => {
            e.preventDefault()
            if (jour && heure && !envoi) preparer(null, false)
          }}
        >
          <p className="dx-q">Quelle assemblée ?</p>
          <div className="dx-seg cag-seg" role="radiogroup" aria-label="Quelle assemblée ?">
            {[
              ['ordinary', 'Ordinaire'],
              ['extraordinary', 'Extraordinaire'],
            ].map(([cle, texte]) => (
              <button key={cle} type="button" role="radio" aria-checked={kind === cle} className={kind === cle ? 'on' : ''} onClick={() => setKind(cle)}>
                {texte}
              </button>
            ))}
          </div>
          <p className="dx-q">Quand ?</p>
          <div className="cag-quand">
            <input type="date" aria-label="Date" className="ap-input" value={jour} onChange={(e) => setJour(e.target.value)} required />
            <input type="time" aria-label="Heure" className="ap-input" value={heure} onChange={(e) => setHeure(e.target.value)} required />
          </div>
          {titre && (
            <p className="dx-note">
              La convocation « {titre} » sera rangée dans Réunions, avec l’ordre du jour de la dernière assemblée, que vous pourrez modifier.
            </p>
          )}
          {erreur && <p className="dx-error" role="alert">{erreur}</p>}
          <button type="submit" className="dx-btn" disabled={!jour || !heure || envoi}>
            {envoi ? 'Préparation…' : 'Préparer la convocation'}
          </button>
        </form>
      )}
    </div>
  )
}
