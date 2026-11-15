import { useEffect, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'
import { signe } from './Labo.jsx'

// Noter les signes dans la frise d'une séance (Seb, 15/11) : toucher un geste
// ou un cri le montre dans la vidéo, puis Bon | Mauvais | Inventé ; la frise
// garde la marque (✓, ✗, barré). Les cris vont dans les notes de l'écoute
// (comme « Noter les cris »), les gestes dans les notes des gestes. Sous la
// frise, « Il manque un geste ici » et « Proposer un réglage », qui ne change
// rien sans « Appliquer ».

const GESTES = ['fists_touch', 'arms_up', 'handshake', 'x']
const CRIS = ['combattez', 'time']
const mmss = (s) => `${Math.floor(s / 60)}:${String(Math.floor(s) % 60).padStart(2, '0')}`
const virgule = (x) => String(x).replace('.', ',')
const pres = (a, b) => Math.abs(a - b) < 0.3

export const notable = (kind) => GESTES.includes(kind) || CRIS.includes(kind)

// Les notes des gestes et des cris d'une séance, rechargées à chaque `version`.
export function useNotes(seanceId, version) {
  const [notes, setNotes] = useState({ gestes: [], cris: [] })
  useEffect(() => {
    Promise.all([api.notesGestes(seanceId), api.notesSeance(seanceId)]).then(
      ([gestes, cris]) => setNotes({ gestes, cris }),
      () => {},
    )
  }, [seanceId, version])
  // La marque d'un signe de la frise : 'good', 'wrong', 'invented' ou null.
  const marque = (s) => {
    if (GESTES.includes(s.kind)) {
      const n = notes.gestes.find((x) => x.kind === s.kind && pres(x.t, s.start))
      return n && n.answer !== 'missing' ? n.answer : null
    }
    if (CRIS.includes(s.kind)) {
      const n = notes.cris.find((x) => pres(x.t, s.start))
      if (!n) return null
      return n.word == null ? 'invented' : n.word === s.kind ? 'good' : 'wrong'
    }
    return null
  }
  return { notes, marque }
}

const DIT = { good: 'Bon', wrong: 'Mauvais', invented: 'Inventé' }

export default function NoterSignes({ seanceId, notes, marque, choisi, fermer, maintenant, changer, club, setClub, montrer }) {
  const [quoiPour, setQuoiPour] = useState(null) // Mauvais : on choisit ce que c'était (ce signe-là)
  const [manque, setManque] = useState(null) // moment de la vidéo pour « Il manque un geste ici »
  const [proposition, setProposition] = useState(null)
  const [cherche, setCherche] = useState(false)
  const quoi = choisi != null && quoiPour === choisi.start

  async function faire(action) {
    try {
      await action()
      setQuoiPour(null)
      setManque(null)
      setProposition(null)
      changer()
    } catch (e) {
      montrer(e.message)
    }
  }
  const geste = choisi && GESTES.includes(choisi.kind)
  function noter(answer, autre) {
    const t = choisi.start
    if (geste) return faire(() => api.noterGeste(seanceId, { t, kind: choisi.kind, answer, real: autre ?? null }))
    return faire(() => api.noterCri(seanceId, { t, answer, word: answer === 'good' ? choisi.kind : autre }))
  }
  function retirer(t) {
    if (!choisi || geste) return faire(() => api.retirerGeste(seanceId, t))
    return faire(() => api.retirerNote(seanceId, t))
  }
  const autres = geste
    ? GESTES.filter((k) => k !== choisi.kind).map((k) => [k, signe(k).court])
    : [...CRIS.filter((k) => k !== choisi?.kind).map((k) => [k, signe(k).court]), ['other', 'Autre mot']]

  async function proposer() {
    setCherche(true)
    try {
      setProposition(await api.proposerReglage())
    } catch (e) {
      montrer(e.message)
    } finally {
      setCherche(false)
    }
  }
  async function appliquer() {
    try {
      setClub(await api.reglerClub({ ...club, min_hold: proposition.best.min_hold }))
      setProposition(null)
      montrer('Réglage appliqué : il sert aux prochaines découpes.')
    } catch (e) {
      montrer(e.message)
    }
  }

  const ajoutes = notes.gestes.filter((n) => n.answer === 'missing')
  const p = proposition
  return (
    <div className="sc-noter">
      {/* En bas de l'écran, pendant que la vidéo montre le signe touché. */}
      {choisi && notable(choisi.kind) && (
        <div className="sc-ecoute__choix sc-noter__barre">
          <span className="sc-meta">
            {signe(choisi.kind).court} à {mmss(choisi.start)} :
          </span>
          {marque(choisi) ? (
            <>
              <span className="sc-meta">{DIT[marque(choisi)]}</span>
              <button type="button" className="btn" onClick={() => retirer(choisi.start)}>
                Retirer
              </button>
            </>
          ) : quoi ? (
            autres.map(([id, l]) => (
              <button key={id} type="button" className="btn" onClick={() => noter('wrong', id)}>
                {l}
              </button>
            ))
          ) : (
            <>
              <button type="button" className="btn" onClick={() => noter('good')}>
                Bon
              </button>
              <button type="button" className="btn" onClick={() => setQuoiPour(choisi.start)}>
                Mauvais
              </button>
              <button type="button" className="btn" onClick={() => noter('invented')}>
                Inventé
              </button>
            </>
          )}
          <button type="button" className="icon-btn" onClick={fermer} aria-label="Fermer">
            <Icon name="x" size={22} />
          </button>
        </div>
      )}
      {ajoutes.map((n) => (
        <div key={n.t} className="sc-ecoute__choix">
          <span className="sc-meta">
            Ajouté : {signe(n.kind).court} à {mmss(n.t)}
          </span>
          <button type="button" className="btn" onClick={() => faire(() => api.retirerGeste(seanceId, n.t))}>
            Retirer
          </button>
        </div>
      ))}
      {manque == null ? (
        <button type="button" className="btn" onClick={() => setManque(maintenant())}>
          Il manque un geste ici
        </button>
      ) : (
        <div className="sc-ecoute__choix">
          <span className="sc-meta">À {mmss(manque)} :</span>
          {GESTES.map((k) => (
            <button
              key={k}
              type="button"
              className="btn"
              onClick={() => faire(() => api.noterGeste(seanceId, { t: manque, kind: k, answer: 'missing' }))}
            >
              {signe(k).court}
            </button>
          ))}
        </div>
      )}
      {p == null ? (
        <button type="button" className="btn" disabled={cherche} onClick={proposer}>
          {cherche ? 'Recherche du réglage…' : 'Proposer un réglage'}
        </button>
      ) : p.total === 0 ? (
        <p className="sc-meta">Notez d’abord quelques gestes : Bon, Mauvais ou Inventé.</p>
      ) : p.best.min_hold === p.current.min_hold ? (
        <p className="sc-meta">
          Le réglage du jour est déjà le meilleur : durée minimale d’un geste {virgule(p.current.min_hold)} s,{' '}
          {p.current.right} notes respectées sur {p.total}.
        </p>
      ) : (
        <div>
          <p className="sc-meta">
            Durée minimale d’un geste {virgule(p.best.min_hold)} s : {p.best.right} notes respectées sur {p.total}{' '}
            (aujourd’hui {virgule(p.current.min_hold)} s : {p.current.right} sur {p.total}).
          </p>
          <div className="sc-ecoute__choix">
            <button type="button" className="btn btn--primary" onClick={appliquer}>
              Appliquer
            </button>
            <button type="button" className="btn" onClick={() => setProposition(null)}>
              Annuler
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
