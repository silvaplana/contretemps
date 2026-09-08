import { Fragment, useState } from 'react'
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

// Écran Présence (Admin, Professeur — voir spec/SPEC.md §5.2 et §6.6).
// Professeur(s) du cours en premier (3 lignes chacun : heure début, heure
// fin, dépassement — plus de statut stocké, la présence se déduit des
// heures), puis les élèves (un statut par case, cliquable). Dates les plus
// récentes à gauche (visibles sans défiler), les plus anciennes à droite —
// `data.dates` reste stocké du plus ancien au plus récent (l'ajout d'une
// date l'ajoute à la fin), seul l'AFFICHAGE des colonnes est inversé.
export default function PresenceScreen({
  cours,
  eleves,
  professeurs,
  data,
  activeUser,
  onCycle,
  onAddDate,
  onSetHeureProf,
  // Contrôlé depuis App.jsx : le menu 3 points de l'en-tête propose aussi
  // "Ajouter une nouvelle date" (même action que le "+"), donc cet état ne
  // peut plus être purement interne à cet écran.
  showAdd,
  setShowAdd,
}) {
  if (!cours) return null

  const rosterEleves = eleves.filter((el) => el.coursIds.includes(cours.id))
  const rosterProfs = professeurs.filter((p) => p.id === cours.professeurId)
  const dates = data?.dates ?? []
  // Indices dans l'ordre d'affichage (le plus récent, donc le dernier de
  // `dates`, en premier) — les données elles-mêmes (parEleve/parProf, des
  // tableaux parallèles à `dates`) restent indexées normalement.
  const ordreAffichage = dates.map((_, i) => i).reverse()

  function statusFor(eleveId, index) {
    return data?.parEleve?.[eleveId]?.[index] ?? 'present'
  }

  function heuresProf(profId, index) {
    return data?.parProf?.[profId]?.[index] ?? { heureDebutReelle: '', heureFinReelle: '', depassementMinutes: '' }
  }

  function peutEditerProf(profId) {
    return activeUser.type === 'admin' || activeUser.id === profId
  }

  return (
    <div className="screen">
      <div className="table-scroll">
        <table className="presence-table">
          <thead>
            <tr>
              <th className="presence-table__sticky" aria-label="Nom" />
              {ordreAffichage.map((i) => (
                <th key={dates[i]}>{dates[i]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rosterProfs.map((p) => {
              const editable = peutEditerProf(p.id)
              return (
                <Fragment key={p.id}>
                  {/* Nom du prof affiché une fois, sur toute la largeur —
                      sinon répété devant "Début"/"Fin"/"Dépassement", ça
                      forçait la colonne de gauche à s'élargir (vécu). */}
                  <tr className="presence-table__group-header">
                    <td colSpan={dates.length + 1}>
                      {p.prenom} {p.nom} :
                    </td>
                  </tr>
                  <tr>
                    <td className="presence-table__sticky">Début</td>
                    {ordreAffichage.map((i) => (
                      <td key={dates[i]}>
                        {editable ? (
                          <input
                            type="time"
                            className="presence-heure-input"
                            value={heuresProf(p.id, i).heureDebutReelle}
                            onChange={(e) =>
                              onSetHeureProf(cours.id, p.id, i, 'heureDebutReelle', e.target.value)
                            }
                          />
                        ) : (
                          <span className="muted">{heuresProf(p.id, i).heureDebutReelle || '–'}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="presence-table__sticky">Fin</td>
                    {ordreAffichage.map((i) => (
                      <td key={dates[i]}>
                        {editable ? (
                          <input
                            type="time"
                            className="presence-heure-input"
                            value={heuresProf(p.id, i).heureFinReelle}
                            onChange={(e) =>
                              onSetHeureProf(cours.id, p.id, i, 'heureFinReelle', e.target.value)
                            }
                          />
                        ) : (
                          <span className="muted">{heuresProf(p.id, i).heureFinReelle || '–'}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                  <tr>
                    <td className="presence-table__sticky">Dépassement (min)</td>
                    {ordreAffichage.map((i) => (
                      <td key={dates[i]}>
                        {editable ? (
                          <input
                            type="number"
                            className="presence-heure-input presence-heure-input--nombre"
                            placeholder="–"
                            value={heuresProf(p.id, i).depassementMinutes}
                            onChange={(e) =>
                              onSetHeureProf(cours.id, p.id, i, 'depassementMinutes', e.target.value)
                            }
                          />
                        ) : (
                          <span className="muted">{heuresProf(p.id, i).depassementMinutes || '–'}</span>
                        )}
                      </td>
                    ))}
                  </tr>
                </Fragment>
              )
            })}

            {rosterEleves.length > 0 && (
              <tr className="presence-table__group-header">
                <td colSpan={dates.length + 1}>Élèves :</td>
              </tr>
            )}

            {rosterEleves.map((el) => (
              <tr key={el.id}>
                <td className="presence-table__sticky">{el.prenom}</td>
                {ordreAffichage.map((i) => {
                  const status = statusFor(el.id, i)
                  return (
                    <td key={dates[i]}>
                      <button
                        type="button"
                        className={`presence-cell presence-cell--${status}`}
                        onClick={() => onCycle(cours.id, el.id, i, CYCLE)}
                        aria-label={`${el.prenom} — ${dates[i]} — ${LABELS[status]}`}
                      >
                        <Icon name={ICONS[status]} size={16} />
                      </button>
                    </td>
                  )
                })}
              </tr>
            ))}

            {rosterEleves.length === 0 && rosterProfs.length === 0 && (
              <tr>
                <td className="presence-table__sticky muted">Personne inscrite à ce cours</td>
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
