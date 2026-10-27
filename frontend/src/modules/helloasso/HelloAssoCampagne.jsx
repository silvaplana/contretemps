import { useEffect, useRef, useState } from 'react'
import * as api from './api.js'

// En tête de « La fiche d'un membre » (`memberFields` du module.js,
// spec/core.md §11.1 ; maquette « Champs des membres ») : « Nos champs » ou
// « Imposés par HelloAsso » et la campagne de la saison
// (spec/modules/helloasso.md §3). Rien sans connexion ou module éteint.
// `onChange(info)` : la fiche se relit ; `info` dit comment montrer les
// champs de la campagne (null sans campagne).

const ANNULER_MS = 10000
// Le dernier état lu par école : rien ne clignote au retour d'un champ.
const dejaLu = {}

function infoDe(form) {
  return form
    ? {
        ligne: 'Calculé par HelloAsso',
        note: `Champ de la campagne HelloAsso « ${form.name} » : rempli par HelloAsso, ne se modifie pas ici.`,
      }
    : null
}

export default function HelloAssoCampagne({ ecoleId, onChange }) {
  const [etat, setEtat] = useState(dejaLu[ecoleId] ?? null)
  const [source, setSource] = useState(dejaLu[ecoleId]?.form ? 'ha' : 'ours')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)

  async function relire() {
    const lu = await api.campagne(ecoleId)
    dejaLu[ecoleId] = lu
    setEtat(lu)
    setSource(lu.form ? 'ha' : 'ours')
    onChange(infoDe(lu.form))
  }

  useEffect(() => {
    // Module éteint (404) ou pas le droit : rien à montrer.
    relire().catch(() => {
      delete dejaLu[ecoleId]
      setEtat(null)
    })
    return () => clearTimeout(minuteur.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecoleId])

  async function choisir(form) {
    setEnCours(true)
    setErreur('')
    try {
      await api.choisirCampagne(ecoleId, { form_type: form.form_type, form_slug: form.form_slug })
      await relire()
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  async function nosChamps() {
    const avant = etat.form
    setSource('ours')
    if (!avant) return
    setEnCours(true)
    setErreur('')
    try {
      await api.nosChamps(ecoleId)
      await relire()
      clearTimeout(minuteur.current)
      setToast({ texte: `Champs de « ${avant.name} » retirés, leurs réponses sont gardées`, avant })
      minuteur.current = setTimeout(() => setToast(null), ANNULER_MS)
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(false)
    }
  }

  if (!etat?.connected || (!etat.can_change && !etat.form)) return null
  const bloque = !etat.can_change || enCours
  const formulaires = etat.forms.length > 0 || !etat.form ? etat.forms : [{ ...etat.form, state: '' }]
  const choisi = etat.form ? `${etat.form.form_type}/${etat.form.form_slug}` : ''

  return (
    <>
      <div className="champs__seg" role="group" aria-label="Source des champs">
        {[
          ['ours', 'Nos champs'],
          ['ha', 'Imposés par HelloAsso'],
        ].map(([valeur, libelle]) => (
          <button
            key={valeur}
            type="button"
            aria-pressed={source === valeur}
            disabled={bloque}
            onClick={() => (valeur === 'ours' ? nosChamps() : setSource('ha'))}
          >
            {libelle}
          </button>
        ))}
      </div>
      {source === 'ha' ? (
        <div className="form-fields">
          <label htmlFor="helloasso-campagne">Campagne HelloAsso</label>
          <select
            id="helloasso-campagne"
            className="field-input"
            value={choisi}
            disabled={bloque}
            onChange={(e) => {
              const form = formulaires.find((f) => `${f.form_type}/${f.form_slug}` === e.target.value)
              if (form) choisir(form)
            }}
          >
            {!etat.form && <option value="">Choisir la campagne…</option>}
            {formulaires.map((f) => (
              <option key={`${f.form_type}/${f.form_slug}`} value={`${f.form_type}/${f.form_slug}`}>
                {f.name}
              </option>
            ))}
          </select>
          <p className="champs__note">
            Les champs de la campagne sont verrouillés et remplis par HelloAsso. Vous pouvez en ajouter d’autres à côté.
          </p>
        </div>
      ) : (
        <p className="champs__note">Les champs du socle, plus les vôtres.</p>
      )}
      {(erreur || etat.error) && <p className="login-screen__erreur">{erreur || etat.error}</p>}
      {toast && (
        <div className="admin-groupes__toast" role="status">
          <span>{toast.texte}</span>
          <button
            type="button"
            onClick={() => {
              const { avant } = toast
              setToast(null)
              clearTimeout(minuteur.current)
              choisir(avant)
            }}
          >
            Annuler
          </button>
        </div>
      )}
    </>
  )
}
