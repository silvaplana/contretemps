import { useCallback, useEffect, useState } from 'react'
import * as api from './api.js'

// Admin > Impayés HelloAsso (spec/modules/helloasso.md §7.4), repris de
// Sambo Admin : les adhésions avec au moins une échéance refusée ou en
// échec. Lu dans la copie de la synchronisation ; « Rafraîchir »
// synchronise d'abord.

const euros = (centimes) =>
  (centimes / 100).toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })

const dateFr = (iso) => (iso ? new Date(iso).toLocaleDateString('fr-FR') : '')

export default function Impayes({ ecoleId }) {
  const [lu, setLu] = useState(null)
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

  return (
    <div className="admin-panel">
      <div className="adherents__entete">
        <h2>Impayés HelloAsso{lu?.campaign ? ` (${lu.members.length})` : ''}</h2>
        {lu?.campaign && (
          <button type="button" className="btn btn--secondary" onClick={rafraichir} disabled={enCours}>
            {enCours ? 'Rafraîchissement…' : 'Rafraîchir'}
          </button>
        )}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {lu && !lu.campaign && <p className="muted">Pas de campagne HelloAsso pour cette saison.</p>}
      {lu?.campaign && lu.members.length === 0 && <p className="muted">Aucun impayé.</p>}
      {lu?.campaign && lu.members.length > 0 && (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nom</th>
                <th>Prénom</th>
                <th>Email</th>
                <th>Total</th>
                <th>Impayé</th>
                <th>Échéances refusées</th>
              </tr>
            </thead>
            <tbody>
              {lu.members.map((m, i) => (
                <tr key={i}>
                  <td>{m.last_name}</td>
                  <td>{m.first_name}</td>
                  <td>{m.email}</td>
                  <td>{euros(m.total)}</td>
                  <td className="impayes__montant">{euros(m.unpaid)}</td>
                  <td>{m.refused.map((p) => dateFr(p.date)).join(', ')}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
