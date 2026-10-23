import { useEffect, useRef, useState } from 'react'
import { chargerScript, configurationEditeur } from '../../api/bureautique.js'

// Éditeur OnlyOffice en plein écran (essai, Seb 16 octobre) : Word, Excel,
// PowerPoint modifiés dans l'appli. L'enregistrement est automatique ; à la
// fermeture, OnlyOffice renvoie le fichier au serveur, qui en fait une
// nouvelle version (historique et retour arrière habituels).
const FERMETURE_EN_ARRIERE_PLAN = 2 * 60 * 1000

export default function Editeur({ orgId, item, onClose }) {
  const [erreur, setErreur] = useState('')
  const [lecture, setLecture] = useState(false)
  const editeur = useRef(null)
  const id = `oo-editeur-${item.id}`

  useEffect(() => {
    let annule = false
    configurationEditeur(orgId, item.id)
      .then(async ({ config, api_js: script, modifiable }) => {
        await chargerScript(script)
        if (annule) return
        setLecture(!modifiable)
        editeur.current = new window.DocsAPI.DocEditor(id, config)
      })
      .catch((e) => !annule && setErreur(e.message))
    return () => {
      annule = true
      editeur.current?.destroyEditor?.()
      editeur.current = null
    }
  }, [orgId, item.id, id])

  // Appli quittée (autre appli, écran éteint) : l'éditeur se ferme au bout
  // de 2 minutes, ce qui enregistre et libère la place chez OnlyOffice (20
  // éditeurs ouverts en même temps au plus ; Seb, 23 octobre).
  useEffect(() => {
    let minuteur = null
    const suivre = () => {
      clearTimeout(minuteur)
      if (document.visibilityState === 'hidden') minuteur = setTimeout(onClose, FERMETURE_EN_ARRIERE_PLAN)
    }
    document.addEventListener('visibilitychange', suivre)
    return () => {
      clearTimeout(minuteur)
      document.removeEventListener('visibilitychange', suivre)
    }
  }, [onClose])

  return (
    <div className="dx-panel dx-editeur" role="dialog" aria-label={`Modifier ${item.name}`}>
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Fermer l’éditeur">
          ←
        </button>
        <h2 className="dx-viewer__title">
          {item.name}
          {lecture && <span className="dx-editeur__lecture"> · lecture seule</span>}
        </h2>
      </div>
      {erreur ? <p className="dx-error">{erreur}</p> : <div className="dx-editeur__zone"><div id={id} /></div>}
    </div>
  )
}
