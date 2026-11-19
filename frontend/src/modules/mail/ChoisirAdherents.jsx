import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'

// « Écrire à un groupe » (spec/modules/mail.md §7 bis ; Seb, 19 novembre) :
// tout le monde (adhérents, administrateurs, profs), ou des cours et des groupes
// d'Admin (Bureau, Profs, faits à la main). Rend { courses, groups (vides :
// tout le monde), label, people (null si plusieurs), without }.

export default function ChoisirAdherents({ ecoleId, onChoix, onFermer }) {
  const [choix, setChoix] = useState(null)
  const [erreur, setErreur] = useState(null)
  // Cochés : 'c<id>' pour un cours, 'g<id>' pour un groupe ; vide : tout le monde.
  const [cours, setCours] = useState(() => new Set())

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
      onChoix({ courses: [], groups: [], label: 'Tout le monde', people: choix.people, without: choix.without })
      return
    }
    const lesCours = choix.courses.filter((c) => cours.has(`c${c.id}`))
    const lesGroupes = choix.groups.filter((g) => cours.has(`g${g.id}`))
    const elus = [...lesCours, ...lesGroupes]
    onChoix({
      courses: lesCours.map((c) => c.id),
      groups: lesGroupes.map((g) => g.id),
      label: elus.map((c) => c.name).join(', '),
      people: elus.length === 1 ? elus[0].people : null,
      without: 0,
    })
  }

  const personnes = (n) => `${n} personne${n > 1 ? 's' : ''}`

  return createPortal(
    <div className="creer-saison" role="dialog" aria-label="Écrire à un groupe">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onFermer} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">Écrire à un groupe</h2>
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
                Tout le monde
                <small>
                  Adhérents, administrateurs et professeurs · {choix.season ? `${choix.season} · ` : ''}
                  {personnes(choix.people)}
                </small>
              </span>
            </button>
            {choix.courses.length > 0 && <p className="mail__discret">Ou des cours</p>}
            {choix.courses.map((c) => (
              <button
                key={`c${c.id}`}
                type="button"
                className="mail__option"
                role="checkbox"
                aria-checked={cours.has(`c${c.id}`)}
                onClick={() => basculer(`c${c.id}`)}
              >
                <span className="mail__option-rond" />
                <span>
                  {c.name}
                  <small>{personnes(c.people)}</small>
                </span>
              </button>
            ))}
            {choix.groups.length > 0 && <p className="mail__discret">Ou des groupes</p>}
            {choix.groups.map((g) => (
              <button
                key={`g${g.id}`}
                type="button"
                className="mail__option"
                role="checkbox"
                aria-checked={cours.has(`g${g.id}`)}
                onClick={() => basculer(`g${g.id}`)}
              >
                <span className="mail__option-rond" />
                <span>
                  {g.name}
                  <small>{personnes(g.people)}</small>
                </span>
              </button>
            ))}
            {choix.courses.length + choix.groups.length > 1 && (
              <p className="mail__discret">
                On peut en cocher plusieurs ; une personne qui est dans deux d’entre eux ne reçoit qu’un mail.
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
