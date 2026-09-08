import { useState } from 'react'
import Icon from '../../components/Icon.jsx'

const JOURS_ORDRE = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
const MINUTES_PAR_LIGNE = 5

// 'HH:MM' ou 'HHhMM' -> minutes depuis minuit (les cours utilisent 'HHhMM').
function versMinutes(heure) {
  const m = heure.match(/(\d{1,2})[h:](\d{2})/)
  if (!m) return 0
  return Number(m[1]) * 60 + Number(m[2])
}

function formatHeure(minutes) {
  const h = Math.floor(minutes / 60)
  const m = minutes % 60
  return `${h}h${String(m).padStart(2, '0')}`
}

// Vue "Planning hebdomadaire" (voir spec/SPEC.md §5.1.4) : grille jours ×
// horaires, chaque cours positionné selon son créneau. Accessible depuis le
// menu 3 points de l'écran Cours, jamais un onglet de navigation principal.
export default function PlanningHebdoView({ cours, professeurs, onBack }) {
  const [afficherProf, setAfficherProf] = useState(true)
  const [exportOuvert, setExportOuvert] = useState(false)
  const [exportChoisi, setExportChoisi] = useState(null)

  const joursUtilises = JOURS_ORDRE.filter((j) => cours.some((c) => c.jour === j))
  const jours = joursUtilises.length > 0 ? joursUtilises : ['Mercredi']

  const debuts = cours.map((c) => versMinutes(c.heureDebut))
  const fins = cours.map((c) => versMinutes(c.heureFin))
  const minGlobal = cours.length ? Math.min(...debuts) : 17 * 60
  const maxGlobal = cours.length ? Math.max(...fins) : 21 * 60
  const nbLignes = Math.max(1, Math.ceil((maxGlobal - minGlobal) / MINUTES_PAR_LIGNE))

  // Repères horaires toutes les 30 min, dans la marge de gauche.
  const reperesHoraires = []
  for (let m = minGlobal; m <= maxGlobal; m += 30) {
    reperesHoraires.push(m)
  }

  function ligneDebut(minutes) {
    return Math.round((minutes - minGlobal) / MINUTES_PAR_LIGNE) + 2 // +2 : ligne 1 = en-tête jours
  }

  return (
    <div className="thread-screen planning-hebdo">
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onBack} aria-label="Retour aux cours">
          <Icon name="chevronLeft" size={22} />
        </button>
        <span className="thread-screen__header-text">
          <strong>Planning hebdomadaire</strong>
        </span>
        <div className="header-menu">
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
              <button
                type="button"
                onClick={() => {
                  setExportChoisi('avec-prof')
                  setExportOuvert(false)
                }}
              >
                <Icon name="fileCheck" size={18} /> Exporter en PDF
              </button>
              <button
                type="button"
                onClick={() => {
                  setExportChoisi('sans-prof')
                  setExportOuvert(false)
                }}
              >
                <Icon name="fileCheck" size={18} /> Exporter en PDF sans professeur
              </button>
            </div>
          )}
        </div>
      </div>

      <div className="screen planning-hebdo__body">
        {exportChoisi && (
          <p className="muted">
            <Icon name="check" size={14} /> Export PDF{' '}
            {exportChoisi === 'sans-prof' ? '(sans professeur)' : ''} — bientôt disponible.
          </p>
        )}

        <label className="planning-hebdo__toggle">
          <input
            type="checkbox"
            checked={afficherProf}
            onChange={(e) => setAfficherProf(e.target.checked)}
          />
          Afficher le nom du prof
        </label>

        <div className="planning-hebdo__scroll">
          <div
            className="planning-hebdo__grid"
            style={{
              gridTemplateColumns: `56px repeat(${jours.length}, 1fr)`,
              gridTemplateRows: `32px repeat(${nbLignes}, ${MINUTES_PAR_LIGNE * 1.6}px)`,
            }}
          >
            {/* Coin vide + en-têtes de jour */}
            <div className="planning-hebdo__corner" style={{ gridColumn: 1, gridRow: 1 }} />
            {jours.map((j, i) => (
              <div
                key={j}
                className="planning-hebdo__day-header"
                style={{ gridColumn: i + 2, gridRow: 1 }}
              >
                {j}
              </div>
            ))}

            {/* Repères horaires */}
            {reperesHoraires.map((m) => (
              <div
                key={m}
                className="planning-hebdo__time-label"
                style={{ gridColumn: 1, gridRow: ligneDebut(m) }}
              >
                {formatHeure(m)}
              </div>
            ))}

            {/* Blocs de cours */}
            {cours
              .filter((c) => jours.includes(c.jour))
              .map((c) => {
                const debut = versMinutes(c.heureDebut)
                const fin = versMinutes(c.heureFin)
                const duree = fin - debut
                // Sur un créneau court, on masque d'abord la salle, puis le
                // prénom du prof — jamais le nom du cours ni l'horaire.
                const montrerSalle = duree >= 45
                const montrerProf = afficherProf && duree >= 30
                const prof = professeurs.find((p) => p.id === c.professeurId)
                const colonne = jours.indexOf(c.jour) + 2
                return (
                  <div
                    key={c.id}
                    className="planning-hebdo__cours-block"
                    style={{
                      gridColumn: colonne,
                      gridRow: `${ligneDebut(debut)} / ${ligneDebut(fin)}`,
                    }}
                  >
                    <strong>{c.nom}</strong>
                    <span>
                      {c.heureDebut}–{c.heureFin}
                    </span>
                    {montrerSalle && c.salle && <span className="muted">{c.salle}</span>}
                    {montrerProf && prof && <span className="muted">{prof.prenom}</span>}
                  </div>
                )
              })}
          </div>
        </div>
      </div>
    </div>
  )
}
