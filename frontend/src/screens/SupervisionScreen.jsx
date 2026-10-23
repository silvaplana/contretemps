import { useState } from 'react'
import * as modulesApi from '../api/modules.js'

// Onglet "Supervision" (demande du 2026-09-21) : réservé au Super User,
// au-dessus de toutes les écoles (voir spec/SPEC.md §2.5). Une case par
// module pour l'école choisie (spec/core.md §9 bis.3) : éteindre cache
// l'onglet et les actions de l'assistant, sans rien effacer.
export default function SupervisionScreen({ ecole, modules, onModulesChange }) {
  const [erreur, setErreur] = useState(null)

  async function cocher(key, enabled) {
    setErreur(null)
    try {
      onModulesChange(await modulesApi.changer(ecole.id, key, enabled))
    } catch (e) {
      setErreur(e.message)
    }
  }

  return (
    <div className="screen">
      <p>Modules utilisés par {ecole.nom}</p>
      <div className="checkbox-list">
        {modules.map((m) => (
          <label key={m.key} className="checkbox-list__item supervision__module">
            <input type="checkbox" checked={m.enabled} onChange={(e) => cocher(m.key, e.target.checked)} />
            {m.label}
          </label>
        ))}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </div>
  )
}
