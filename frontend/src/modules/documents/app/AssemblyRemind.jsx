import { useEffect, useRef, useState } from 'react'

// Résultats d'une convocation d'AG : « Relancer les N sans réponse »
// (procurations.md §1.4). Un email ne se reprend pas : il part après 10 s,
// Annuler d'ici là (« Annuler plutôt que confirmer »).

const ANNULER_S = 10

export default function AssemblyRemind({ file, api, count, onToast, onSent }) {
  const [compte, setCompte] = useState(null)
  const minuteur = useRef(null)
  useEffect(() => () => clearInterval(minuteur.current), [])

  async function envoyer() {
    try {
      const r = await api.remind(file.id)
      onToast(`Rappel envoyé à ${r.sent} membre${r.sent > 1 ? 's' : ''}`)
      onSent?.()
    } catch (e) {
      onToast(e.message)
    }
  }

  function lancer() {
    let reste = ANNULER_S
    setCompte(reste)
    minuteur.current = setInterval(() => {
      reste -= 1
      if (reste > 0) setCompte(reste)
      else {
        clearInterval(minuteur.current)
        setCompte(null)
        envoyer()
      }
    }, 1000)
  }

  if (compte != null) {
    return (
      <div className="ag-compte" role="status">
        <span>Rappel dans {compte} s…</span>
        <button
          type="button"
          className="dx-btn dx-btn--ghost"
          onClick={() => {
            clearInterval(minuteur.current)
            setCompte(null)
          }}
        >
          Annuler
        </button>
      </div>
    )
  }
  return (
    <button type="button" className="dx-btn dx-btn--ghost af-emargement" disabled={!file.can_edit} onClick={lancer}>
      Renvoyer un rappel {count > 1 ? `aux ${count} personnes qui n’ont` : 'à la personne qui n’a'} pas encore répondu
    </button>
  )
}
