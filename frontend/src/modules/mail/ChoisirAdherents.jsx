import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'

// « Écrire aux adhérents » (spec/modules/mail.md §7 bis ; Seb, 19 novembre) :
// tous les adhérents de la saison, ou un ou plusieurs cours. Rend
// { courses: [ids] (vide : tous), label, people (null si plusieurs cours), without }.

export default function ChoisirAdherents({ ecoleId, onChoix, onFermer }) {
  const [choix, setChoix] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [cours, setCours] = useState(() => new Set()) // vide : tous

  useEffect(() => {
    api.adherents(ecoleId).then(setChoix, (e) => setErreur(e.message))
  }, [ecoleId])

  function basculer(id) {
    setCours((c) => {
      const n = new Set(c)
      if (n.has(id)) n.delete(id)
      else n.add(id)
      return n
    })
  }

  function choisir() {
    if (cours.size === 0) {
      onChoix({ courses: [], label: 'Tous les adhérents', people: choix.people, without: choix.without })
      return
    }
    const elus = choix.courses.filter((c) => cours.has(c.id))
    onChoix({
      courses: elus.map((c) => c.id),
      label: elus.map((c) => c.name).join(', '),
      people: elus.length === 1 ? elus[0].people : null,
      without: 0,
    })
  }

  const personnes = (n) => `${n} personne${n > 1 ? 's' : ''}`

  return createPortal(
    <div className="creer-saison" role="dialog" aria-label="Écrire aux adhérents">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onFermer} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">Écrire aux adhérents</h2>
      </div>
      <div className="creer-saison__corps mail">
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        {choix && (
          <div className="mail__pile">
            <button
              type="button"
              className="mail__option"
              role="radio"
              aria-checked={cours.size === 0}
              onClick={() => setCours(new Set())}
            >
              <span className="mail__option-rond" />
              <span>
                Tous les adhérents
                <small>
                  {choix.season ? `Saison ${choix.season} · ` : ''}
                  {personnes(choix.people)}
                </small>
              </span>
            </button>
            {choix.courses.length > 0 && <p className="mail__discret">Ou des cours</p>}
            {choix.courses.map((c) => (
              <button
                key={c.id}
                type="button"
                className="mail__option"
                role="checkbox"
                aria-checked={cours.has(c.id)}
                onClick={() => basculer(c.id)}
              >
                <span className="mail__option-rond" />
                <span>
                  {c.name}
                  <small>{personnes(c.people)}</small>
                </span>
              </button>
            ))}
            {choix.courses.length > 1 && (
              <p className="mail__discret">
                On peut cocher plusieurs cours ; une personne inscrite à deux cours ne reçoit qu’un mail.
              </p>
            )}
            <button type="button" className="btn btn--primary btn--block mail__principal" onClick={choisir}>
              Choisir
            </button>
          </div>
        )}
      </div>
    </div>,
    document.body,
  )
}
