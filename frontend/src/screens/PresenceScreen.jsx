import Icon from '../components/Icon.jsx'

const CYCLE = ['present', 'absent', 'retard']
const ICONS = { present: 'check', absent: 'x', retard: 'clock' }
const LABELS = { present: 'Présent', absent: 'Absent', retard: 'Retard' }

// Écran Présence (Admin, Professeur — voir spec/SPEC.md 5.2 et images/presence.png).
// Élèves en lignes, dates en colonnes (défilement horizontal). Cliquer une
// case fait tourner le statut (droit d'édition réservé à Admin/Professeur).
export default function PresenceScreen({ cours, eleves, data, onCycle }) {
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
    </div>
  )
}
