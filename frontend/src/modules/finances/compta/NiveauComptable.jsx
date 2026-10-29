import { useEffect, useState } from 'react'
import * as api from '../api.js'

// « Documents comptables : Simple / Complet » sur la ligne Financier de
// Fonctionnalités (spec/modules/financier.md §8.1), en plus de Comptes › ⋯ ›
// Plan comptable. Complet ne revient pas en Simple. La ligne est l'étiquette
// de la case : un clic sur le bouton ne doit pas la cocher.
export default function NiveauComptable() {
  const [niveau, setNiveau] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api
      .planComptable()
      .then((p) => setNiveau(p.level))
      .catch(() => setNiveau(null))
  }, [])

  // Réservé aux trésoriers : sinon, rien sur la ligne.
  if (!niveau) return null

  async function passerEnComplet(e) {
    e.preventDefault()
    if (!window.confirm('Passer en Complet (partie double) ? On ne revient pas en Simple.')) return
    try {
      setNiveau((await api.choisirNiveau('complet')).level)
    } catch (err) {
      setErreur(err.message)
    }
  }

  return (
    <span className="nf-qui-paie">
      Documents comptables : {niveau === 'complet' ? 'Complet' : 'Simple'}
      {niveau !== 'complet' && (
        <>
          {' '}
          <button type="button" className="btn btn--link" onClick={passerEnComplet}>
            Passer en Complet
          </button>
        </>
      )}
      {erreur && <span className="login-screen__erreur"> {erreur}</span>}
    </span>
  )
}
