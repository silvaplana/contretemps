import { useCallback, useEffect, useState } from 'react'
import * as api from './api.js'

// Admin > À encaisser (spec/modules/helloasso.md §7.4, maquette validée par
// Seb le 18 novembre 2026) : l'argent qui doit encore arriver sur le compte.
// 1. Ce que les adhérents doivent encore payer à HelloAsso, échéance par
//    échéance ; dépassée sans paiement = en rouge, en tête.
// 2. Ce que HelloAsso doit verser au compte (statistiques de la saison :
//    virements en route et argent gardé par HelloAsso).
// Lu dans la copie de la synchronisation ; « Rafraîchir » synchronise d'abord.

const euros = (centimes) =>
  (centimes / 100).toLocaleString('fr-FR', { style: 'currency', currency: 'EUR' })

const jour = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'short' }) : '')

const mois = (iso) => {
  const texte = new Date(iso).toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
  return texte.charAt(0).toUpperCase() + texte.slice(1)
}

// HelloAsso verse vers le 10 du mois suivant.
const prochainVersement = () => {
  const d = new Date()
  const versement = new Date(d.getFullYear(), d.getMonth() + (d.getDate() < 10 ? 0 : 1), 10)
  return versement.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
}

const somme = (echeances) => echeances.reduce((s, e) => s + e.amount, 0)

function Echeance({ e }) {
  return (
    <div className={`encaisser__ligne${e.overdue ? ' encaisser__ligne--retard' : ''}`}>
      <span>{jour(e.date)}</span>
      <span>
        <b>{e.last_name}</b> {e.first_name}
        {(e.installment || e.overdue) && (
          <small>
            {[e.installment && `Paiement ${e.installment}`, e.overdue && 'dépassée, pas de paiement']
              .filter(Boolean)
              .join(' · ')}
          </small>
        )}
      </span>
      <span className="encaisser__somme">{euros(e.amount)}</span>
    </div>
  )
}

export default function Impayes({ ecoleId }) {
  const [lu, setLu] = useState(null)
  const [caisse, setCaisse] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const relire = useCallback(() => {
    api
      .impayes(ecoleId)
      .then((r) => {
        setLu(r)
        setErreur('')
      })
      .catch((e) => setErreur(e.message))
    api
      .statistiques(ecoleId)
      .then((s) => setCaisse(s.cash))
      .catch(() => setCaisse(null))
  }, [ecoleId])

  useEffect(() => {
    relire()
  }, [relire])

  async function rafraichir() {
    setEnCours(true)
    try {
      await api.synchroniser(ecoleId)
    } catch (e) {
      setErreur(e.message)
    }
    setEnCours(false)
    relire()
  }

  const echeances = lu?.upcoming ?? []
  const enRetard = echeances.filter((e) => e.overdue)
  const parMois = []
  for (const e of echeances.filter((x) => !x.overdue)) {
    const cle = (e.date || '').slice(0, 7)
    if (parMois.at(-1)?.cle !== cle) parMois.push({ cle, echeances: [] })
    parMois.at(-1).echeances.push(e)
  }
  const aPayer = somme(echeances)
  const enRoute = caisse ? Math.round(caisse.in_transit * 100) : 0
  const garde = caisse ? Math.round(caisse.held * 100) : 0

  return (
    <div className="admin-panel">
      <div className="adherents__entete">
        <h2>À encaisser</h2>
        {lu?.campaign && (
          <button type="button" className="btn btn--secondary" onClick={rafraichir} disabled={enCours}>
            {enCours ? 'Rafraîchissement…' : 'Rafraîchir'}
          </button>
        )}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {lu && !lu.campaign && <p className="muted">Pas de campagne HelloAsso pour cette saison.</p>}
      {lu?.campaign && (
        <>
          <div className="encaisser__total">
            <span>Doit encore arriver sur le compte</span>
            <b>{euros(aPayer + enRoute + garde)}</b>
            {caisse && (
              <span>
                {euros(aPayer)} à payer par les adhérents + {euros(enRoute + garde)} chez HelloAsso
              </span>
            )}
          </div>

          <div className="encaisser__partie">
            <h3>1. À payer à HelloAsso</h3>
            <b>{euros(aPayer)}</b>
          </div>
          <p className="muted">Les échéances que les adhérents doivent encore payer.</p>
          {enRetard.length > 0 && (
            <p className="encaisser__alerte">
              {enRetard.length === 1 ? '1 échéance dépassée' : `${enRetard.length} échéances dépassées`} sans
              paiement : {euros(somme(enRetard))}
            </p>
          )}
          {echeances.length === 0 && <p className="muted">Aucune échéance à payer.</p>}
          {enRetard.map((e, i) => (
            <Echeance key={`r${i}`} e={e} />
          ))}
          {parMois.map((m) => (
            <div key={m.cle}>
              <p className="encaisser__mois">
                {m.cle ? mois(m.echeances[0].date) : 'Sans date'} · {euros(somme(m.echeances))}
              </p>
              {m.echeances.map((e, i) => (
                <Echeance key={i} e={e} />
              ))}
            </div>
          ))}

          {caisse && (
            <>
              <div className="encaisser__partie">
                <h3>2. HelloAsso doit verser au compte</h3>
                <b>{euros(enRoute + garde)}</b>
              </div>
              <p className="muted">L'argent déjà payé, que HelloAsso garde pour l'école.</p>
              {enRoute > 0 && (
                <div className="encaisser__ligne encaisser__ligne--large">
                  <span>
                    <b>Virement en route</b>
                  </span>
                  <span className="encaisser__somme">{euros(enRoute)}</span>
                </div>
              )}
              <div className="encaisser__ligne encaisser__ligne--large">
                <span>
                  <b>Gardé par HelloAsso</b>
                  <small>Versé vers le {prochainVersement()}</small>
                </span>
                <span className="encaisser__somme">{euros(garde)}</span>
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
