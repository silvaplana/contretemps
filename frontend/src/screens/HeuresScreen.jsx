import { useRef, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { useFermerAuClicExterieur } from '../hooks/useFermerAuClicExterieur.js'

const MOIS_NOMS = [
  '',
  'Janvier',
  'Février',
  'Mars',
  'Avril',
  'Mai',
  'Juin',
  'Juillet',
  'Août',
  'Septembre',
  'Octobre',
  'Novembre',
  'Décembre',
]

// Les dates de présence sont stockées en 'JJ/MM', sans année (voir
// api/presence.js — le modèle backend a une vraie date par séance, mais
// ce pont plus simple perd l'année). En attendant, on affiche l'année en
// cours pour que "Août" se lise "Août 2026" — à corriger le jour où les
// dates portent une année.
const ANNEE_AFFICHAGE = new Date().getFullYear()

function libelleMois(mois) {
  return `${MOIS_NOMS[Number(mois)]} ${ANNEE_AFFICHAGE}`
}

// Label de l'option "toute la période" : le mois de début et de fin
// (ex. "Août 2026" s'il n'y en a qu'un, "Août 2026 - Décembre 2026" sinon)
// plutôt que le générique "Toute la période".
function libellePeriodeTotale(moisDisponibles) {
  if (moisDisponibles.length === 0) return 'Aucune séance'
  const premier = moisDisponibles[0]
  const dernier = moisDisponibles[moisDisponibles.length - 1]
  return premier === dernier ? libelleMois(premier) : `${libelleMois(premier)} - ${libelleMois(dernier)}`
}

// 'HH:MM' -> minutes depuis minuit, ou null si vide/invalide.
function versMinutes(hhmm) {
  if (!hhmm) return null
  const [h, m] = hhmm.split(':').map(Number)
  if (Number.isNaN(h) || Number.isNaN(m)) return null
  return h * 60 + m
}

function formatHeures(minutes) {
  if (!minutes) return '0h00'
  const signe = minutes < 0 ? '-' : ''
  const abs = Math.round(Math.abs(minutes))
  return `${signe}${Math.floor(abs / 60)}h${String(abs % 60).padStart(2, '0')}`
}

// Toutes les séances passées d'un professeur, tous cours confondus, à
// partir des heures réelles saisies (voir spec/SPEC.md §5.7 et §6.6).
// Rien n'est stocké séparément : tout est calculé à la volée ici.
function sessionsDuProf(profId, cours, presences) {
  const sessions = []
  cours
    .filter((c) => c.professeurId === profId)
    .forEach((c) => {
      const data = presences[c.id]
      if (!data?.parProf?.[profId]) return
      data.dates.forEach((date, i) => {
        const h = data.parProf[profId][i]
        const debut = versMinutes(h?.heureDebutReelle)
        const fin = versMinutes(h?.heureFinReelle)
        if (debut === null || fin === null) return
        const depassement = Number(h.depassementMinutes) || 0
        const total = fin - debut
        const [jour, mois] = date.split('/')
        sessions.push({
          date,
          jour,
          mois,
          coursNom: c.nom,
          heureDebut: h.heureDebutReelle,
          heureFin: h.heureFinReelle,
          minutesSup: depassement,
          minutesNormales: total - depassement,
        })
      })
    })
  sessions.sort((a, b) => Number(a.mois) - Number(b.mois) || Number(a.jour) - Number(b.jour))
  return sessions
}

// Écran "Comptage d'heures" (voir spec/SPEC.md §5.7) — pas un onglet de
// navigation principal, accessible depuis Admin > Professeurs (n'importe
// quel prof) ou depuis Profil > "Mes heures" (le prof lui-même seulement).
// ⚠️ Ce n'est pas une fiche de salaire, juste un relevé d'heures/justificatif.
export default function HeuresScreen({ professeur, cours, presences, estAdmin, onBack }) {
  const [periode, setPeriode] = useState('all')
  const [exportOuvert, setExportOuvert] = useState(false)
  const [exportChoisi, setExportChoisi] = useState(null)
  const menuRef = useRef(null)
  useFermerAuClicExterieur(menuRef, exportOuvert, () => setExportOuvert(false))

  if (!professeur) return null

  const sessions = sessionsDuProf(professeur.id, cours, presences)
  const moisDisponibles = [...new Set(sessions.map((s) => s.mois))].sort()
  const filtrees = periode === 'all' ? sessions : sessions.filter((s) => s.mois === periode)

  const totalNormales = filtrees.reduce((acc, s) => acc + s.minutesNormales, 0)
  const totalSup = filtrees.reduce((acc, s) => acc + s.minutesSup, 0)

  return (
    <div className="thread-screen heures-screen">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <span className="thread-screen__header-text">
          <strong>
            {professeur.prenom} {professeur.nom}
          </strong>
          <span className="muted">Relevé d’heures</span>
        </span>
        {estAdmin && (
          <div className="header-menu" ref={menuRef}>
            <button
              type="button"
              className="icon-btn"
              onClick={() => setExportOuvert((o) => !o)}
              aria-label="Exporter"
            >
              <Icon name="moreVertical" />
            </button>
            {exportOuvert && (
              <div className="dropdown-menu header-menu__panel">
                {[
                  ['pdf', 'Exporter en PDF'],
                  ['excel', 'Exporter en Excel'],
                  ['drive', 'Déposer sur Google Drive'],
                ].map(([valeur, label]) => (
                  <button
                    key={valeur}
                    type="button"
                    onClick={() => {
                      setExportChoisi(valeur)
                      setExportOuvert(false)
                    }}
                  >
                    <Icon name="fileCheck" size={18} /> {label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      <div className="screen heures-screen__body">
        {exportChoisi && (
          <p className="muted">
            <Icon name="check" size={14} /> Export {exportChoisi.toUpperCase()} — bientôt
            disponible.
          </p>
        )}

        <label htmlFor="heures-periode" className="section-label">
          Période
        </label>
        <select
          id="heures-periode"
          className="field-input heures-screen__periode"
          value={periode}
          onChange={(e) => setPeriode(e.target.value)}
        >
          <option value="all">{libellePeriodeTotale(moisDisponibles)}</option>
          {moisDisponibles.map((m) => (
            <option key={m} value={m}>
              {libelleMois(m)}
            </option>
          ))}
        </select>

        <div className="heures-cards">
          <div className="heures-card">
            <span className="muted">Heures normales</span>
            <strong>{formatHeures(totalNormales)}</strong>
          </div>
          <div className="heures-card">
            <span className="muted">Heures sup</span>
            <strong>{formatHeures(totalSup)}</strong>
          </div>
        </div>

        {filtrees.length === 0 ? (
          <p className="muted">Aucune heure enregistrée pour l’instant sur cette période.</p>
        ) : (
          <div className="table-scroll">
            <table className="data-table heures-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Cours</th>
                  <th>Début</th>
                  <th>Fin</th>
                  <th>Heures sup</th>
                  <th>Heures normales</th>
                </tr>
              </thead>
              <tbody>
                {filtrees.map((s, i) => (
                  <tr key={i}>
                    <td>{s.date}</td>
                    <td>{s.coursNom}</td>
                    <td>{s.heureDebut}</td>
                    <td>{s.heureFin}</td>
                    <td>{formatHeures(s.minutesSup)}</td>
                    <td>{formatHeures(s.minutesNormales)}</td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={4}>
                    <strong>Total</strong>
                  </td>
                  <td>
                    <strong>{formatHeures(totalSup)}</strong>
                  </td>
                  <td>
                    <strong>{formatHeures(totalNormales)}</strong>
                  </td>
                </tr>
              </tfoot>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
