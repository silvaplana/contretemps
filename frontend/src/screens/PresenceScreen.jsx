import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import Modal from '../components/Modal.jsx'

const CYCLE = ['present', 'absent', 'retard']
const ICONS = { present: 'check', absent: 'x', retard: 'clock' }
const LABELS = { present: 'Présent', absent: 'Absent', retard: 'Retard' }

// Date locale du jour au format 'YYYY-MM-DD'. Volontairement pas
// `new Date().toISOString()` : ça convertit en UTC et peut donner la date
// d'hier ou de demain selon l'heure et le fuseau (ex. la nuit en France,
// UTC+1/+2 en avance sur UTC).
function isoAujourdhui() {
  const d = new Date()
  const deuxChiffres = (n) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${deuxChiffres(d.getMonth() + 1)}-${deuxChiffres(d.getDate())}`
}

// 'YYYY-MM-DD' (valeur native d'un <input type="date">) -> 'JJ/MM', le
// format déjà utilisé pour les colonnes existantes (voir data/mockData.js).
function versLabelAffiche(dateIso) {
  const [, mois, jour] = dateIso.split('-')
  return `${jour}/${mois}`
}

// Écran Présence (Admin, Professeur — voir spec/SPEC.md 5.2 et images/presence.png).
// Élèves en lignes, dates en colonnes (défilement horizontal). Cliquer une
// case fait tourner le statut (droit d'édition réservé à Admin/Professeur).
export default function PresenceScreen({ cours, eleves, data, onCycle, onAddDate }) {
  const [showAdd, setShowAdd] = useState(false)

  if (!cours) return null

  const roster = eleves.filter((el) => el.coursIds.includes(cours.id))
  const dates = data?.dates ?? []

  function statusFor(eleveId, index) {
    return data?.parEleve?.[eleveId]?.[index] ?? 'present'
  }

  return (
    <div className="screen">
      <div className="table-scroll">
        <table className="presence-table">
          <thead>
            <tr>
              <th className="presence-table__sticky">Élève</th>
              {dates.map((d) => (
                <th key={d}>{d}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {roster.map((el) => (
              <tr key={el.id}>
                <td className="presence-table__sticky">{el.prenom}</td>
                {dates.map((d, i) => {
                  const status = statusFor(el.id, i)
                  return (
                    <td key={d}>
                      <button
                        type="button"
                        className={`presence-cell presence-cell--${status}`}
                        onClick={() => onCycle(cours.id, el.id, i, CYCLE)}
                        aria-label={`${el.prenom} — ${d} — ${LABELS[status]}`}
                      >
                        <Icon name={ICONS[status]} size={16} />
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}
            {roster.length === 0 && (
              <tr>
                <td className="presence-table__sticky muted">Aucun élève inscrit</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="legend">
        {CYCLE.map((status) => (
          <span key={status} className="legend__item">
            <span className={`legend__dot legend__dot--${status}`} />
            {LABELS[status]}
          </span>
        ))}
      </div>

      <button type="button" className="fab" onClick={() => setShowAdd(true)} aria-label="Ajouter une date">
        <Icon name="plus" size={24} />
      </button>

      {showAdd && (
        <AddDateModal
          datesExistantes={dates}
          onClose={() => setShowAdd(false)}
          onAdd={(dateIso) => {
            onAddDate(cours.id, versLabelAffiche(dateIso))
            setShowAdd(false)
          }}
        />
      )}
    </div>
  )
}

function AddDateModal({ datesExistantes, onClose, onAdd }) {
  const [dateIso, setDateIso] = useState(isoAujourdhui())
  const dejaPresente = datesExistantes.includes(versLabelAffiche(dateIso))

  return (
    <Modal
      title="Ajouter une date de présence"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!dateIso || dejaPresente}
          onClick={() => onAdd(dateIso)}
        >
          Ajouter
        </button>
      }
    >
      <label htmlFor="add-date-presence">Date</label>
      {/* input[type=date] : par défaut la date du jour, modifiable via le
          calendrier natif du navigateur/téléphone. */}
      <input
        id="add-date-presence"
        type="date"
        value={dateIso}
        onChange={(e) => setDateIso(e.target.value)}
      />
      {dejaPresente && <p className="muted">Cette date est déjà dans la table.</p>}
    </Modal>
  )
}
