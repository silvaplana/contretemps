import { useEffect, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'
import { Deroulant } from './Labo.jsx'

// Noter les cris d'une séance filmée (étude du 14/11) : comme sous un test
// d'Entraîner l'écoute, Bon | Mauvais | Inventé sous chaque cri, et « Il
// manque un mot » au moment de la vidéo. Le cri est rangé comme exemple, et
// « Rejouer tous les essais » compte la séance avec le vrai bruit de la salle.

const MOTS = [
  ['combattez', 'Combattez'],
  ['time', 'Time'],
]
const nom = (id) => MOTS.find(([x]) => x === id)?.[1]
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s) % 60).padStart(2, '0')}`

export default function NoterCris({ seanceId, version, changer, signes, maintenant, aller, montrer }) {
  const [notes, setNotes] = useState([])
  const [quelMot, setQuelMot] = useState(null) // moment dont on choisit le mot (Mauvais)
  const [manque, setManque] = useState(null) // moment de la vidéo pour « Il manque un mot »
  useEffect(() => {
    api.notesSeance(seanceId).then(setNotes, () => {})
  }, [seanceId, version])
  const cris = signes.filter((x) => nom(x.kind))
  const note = (t) => notes.find((n) => Math.abs(n.t - t) < 0.3)

  async function noter(t, answer, word) {
    try {
      setNotes(await api.noterCri(seanceId, { t, answer, word }))
      setQuelMot(null)
      setManque(null)
      changer?.() // la frise montre la marque (Seb, 15/11)
    } catch (e) {
      montrer(e.message)
    }
  }

  // Une note mise par erreur se retire, avec l'exemple rangé (Seb, 15/11).
  async function retirer(t) {
    try {
      setNotes(await api.retirerNote(seanceId, t))
      changer?.()
    } catch (e) {
      montrer(e.message)
    }
  }

  const dit = (n) => (n.word == null ? 'Rangé : inventé' : nom(n.word) ? `Rangé : « ${nom(n.word)} »` : 'Rangé : autre mot')
  return (
    <Deroulant titre="Noter les cris">
      <p className="sc-meta">
        Pour que l’écoute apprenne le son de la salle : sous chaque cri, dites s’il est juste. « Rejouer tous les essais »
        (⋮ › Entraîner l’écoute) compte cette séance. Un cri oublié : arrêtez la vidéo dessus, puis « Il manque un mot
        ici ».
      </p>
      {cris.length === 0 && <p className="sc-meta">Aucun cri repéré.</p>}
      <ul className="sc-ecoute__liste">
        {cris.map((x) => (
          <li key={`${x.kind}-${x.start}`} className="sc-ecoute__trouve">
            <span>
              <button type="button" className="icon-btn" onClick={() => aller(x.start)} aria-label="Voir dans la vidéo">
                <Icon name="play" size={22} />
              </button>
              « {nom(x.kind)} ! » à {mmss(x.start)}
              {x.weak ? ' (pas sûr)' : ''}
            </span>
            {note(x.start) ? (
              <span className="sc-ecoute__choix">
                <span className="sc-meta">{dit(note(x.start))}</span>
                <button type="button" className="btn" onClick={() => retirer(note(x.start).t)}>
                  Retirer
                </button>
              </span>
            ) : quelMot === x.start ? (
              <span className="sc-ecoute__choix">
                {[...MOTS.filter(([id]) => id !== x.kind), ['other', 'Autre mot']].map(([id, l]) => (
                  <button key={id} type="button" className="btn" onClick={() => noter(x.start, 'wrong', id)}>
                    {l}
                  </button>
                ))}
              </span>
            ) : (
              <span className="sc-ecoute__choix">
                <button type="button" className="btn" onClick={() => noter(x.start, 'good', x.kind)}>
                  Bon
                </button>
                <button type="button" className="btn" onClick={() => setQuelMot(x.start)}>
                  Mauvais
                </button>
                <button type="button" className="btn" onClick={() => noter(x.start, 'invented')}>
                  Inventé
                </button>
              </span>
            )}
          </li>
        ))}
      </ul>
      {notes
        .filter((n) => !cris.some((x) => Math.abs(n.t - x.start) < 0.3))
        .map((n) => (
          <div key={n.t} className="sc-ecoute__choix">
            <span className="sc-meta">
              Ajouté : « {nom(n.word) ?? n.word} » à {mmss(n.t)}
            </span>
            <button type="button" className="btn" onClick={() => retirer(n.t)}>
              Retirer
            </button>
          </div>
        ))}
      {manque == null ? (
        <button type="button" className="btn" onClick={() => setManque(maintenant())}>
          Il manque un mot ici
        </button>
      ) : (
        <div className="sc-ecoute__choix">
          <span className="sc-meta">À {mmss(manque)} :</span>
          {MOTS.map(([id, l]) => (
            <button key={id} type="button" className="btn" onClick={() => noter(manque, 'missing', id)}>
              {l}
            </button>
          ))}
        </div>
      )}
    </Deroulant>
  )
}
