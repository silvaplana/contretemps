// « Voir » un document du bilan (Excel, Word, FEC) dans OnlyOffice, en
// lecture seule, sans le ranger dans Docs (Seb 13/11) : le serveur fabrique
// le fichier, le garde une heure hors de Docs et rend la configuration.
import { useEffect, useRef, useState } from 'react'
import { chargerScript } from '../../../api/bureautique.js'
import './compta.css'

export default function Apercu({ titre, charger, onClose }) {
  const [erreur, setErreur] = useState('')
  const editeur = useRef(null)
  const id = 'fin-apercu-editeur'

  useEffect(() => {
    let annule = false
    charger()
      .then(async ({ config, api_js: script }) => {
        await chargerScript(script)
        if (!annule) editeur.current = new window.DocsAPI.DocEditor(id, config)
      })
      .catch((e) => !annule && setErreur(e.message))
    return () => {
      annule = true
      editeur.current?.destroyEditor?.()
      editeur.current = null
    }
  }, [charger])

  return (
    <div className="fin-apercu" role="dialog" aria-label={`Voir ${titre}`}>
      <div className="fin-apercu__haut">
        <button type="button" className="fin-apercu__retour" onClick={onClose} aria-label="Revenir aux documents">
          ←
        </button>
        <h2 className="fin-apercu__titre">{titre}</h2>
      </div>
      {erreur ? <p className="login-screen__erreur">{erreur}</p> : <div className="fin-apercu__zone"><div id={id} /></div>}
    </div>
  )
}
