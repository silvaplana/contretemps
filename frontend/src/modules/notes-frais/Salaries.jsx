import { useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'

// Réglage « L'association a des salariés » sur la ligne Financier de
// Fonctionnalités (financier.md §8.11), non par défaut. Oui : les comptes de
// la paie (641, 645, 431) entrent au plan, et Pièces propose le bulletin de
// salaire. La ligne est l'étiquette de la case : un clic ici ne la coche pas.
export default function Salaries() {
  const [active, setActive] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api
      .paie()
      .then((p) => setActive(p.active))
      .catch(() => setActive(null))
  }, [])

  // Réservé aux trésoriers : sinon, rien sur la ligne.
  if (active === null) return null

  async function changer(e) {
    e.preventDefault()
    setErreur('')
    try {
      setActive((await api.reglerPaie(!active)).active)
    } catch (err) {
      setErreur(err.message)
    }
  }

  return (
    <span className="nf-qui-paie">
      L’association a des salariés : {active ? 'oui' : 'non'}{' '}
      <button type="button" className="btn btn--link" onClick={changer}>
        {active ? 'Non' : 'Oui'}
      </button>
      {erreur && <span className="login-screen__erreur"> {erreur}</span>}
    </span>
  )
}
