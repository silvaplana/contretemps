// Courbe du solde par saison, reprise de Sambo Admin (CurveChart dans
// Seasons.jsx) pour la periode "Saisons" du graphique des Comptes (voir
// Comptes.jsx) : une courbe par saison sur le meme axe (debut -> fin de
// saison), pour comparer les saisons entre elles ; un clic sur une saison de
// la legende la masque ou la reaffiche. Seul le mode "overlay" est utilise
// ici ; les modes "spread" et "selected" de Sambo Admin sont gardes tels
// quels pour le sous-module Bilan a venir.
import { useEffect, useRef, useState } from 'react'
import { niceTicks } from './BalanceChart.jsx'

const CHART_HEIGHT = 260
const DAY_MS = 86_400_000
const ACCENT = 'var(--accent)'
// Mode "Superposées" : une couleur par saison, dans l'ordre des saisons (la
// plus ancienne en premier). Une saison garde sa couleur quelle que soit la
// saison choisie ou masquee ; la saison choisie a un trait plus epais.
// Couleurs voisines verifiees distinctes, y compris pour les daltoniens.
const SEASON_COLORS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#9085e9']
// Identifiants des saisons masquees dans le graphique.
const HIDDEN_KEY = 'finances-seasons-hidden'

function readSetting(key, fallback) {
  try {
    return localStorage.getItem(key) ?? fallback
  } catch {
    return fallback
  }
}

function writeSetting(key, value) {
  try {
    localStorage.setItem(key, value)
  } catch {
    // Stockage indisponible : le choix ne sera juste pas retenu.
  }
}

function readHidden(key) {
  try {
    const ids = JSON.parse(readSetting(key, '[]'))
    return new Set(Array.isArray(ids) ? ids : [])
  } catch {
    return new Set()
  }
}

const euros = (n) => `${n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`
// `|| 0` : pas de "-0 €" pour une graduation a peine negative.
const eurosRound = (n) => `${(Math.round(n) || 0).toLocaleString('fr-FR')} €`
const ts = (isoDate) => Date.parse(`${isoDate}T00:00:00Z`)
const dayMonth = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', timeZone: 'UTC' })
const dayMonthYear = new Intl.DateTimeFormat('fr-FR', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' })
const monthShort = new Intl.DateTimeFormat('fr-FR', { month: 'short', timeZone: 'UTC' })
const monthYear = new Intl.DateTimeFormat('fr-FR', { month: 'short', year: 'numeric', timeZone: 'UTC' })

// "2025-2026" -> "25-26" (axe sur telephone).
function shortName(name, narrow) {
  const match = narrow && name.match(/^\d{2}(\d{2})-\d{2}(\d{2})$/)
  return match ? `${match[1]}-${match[2]}` : name
}

// Largeur du conteneur, suivie quand l'ecran change (telephone tourne...).
function useWidth() {
  const ref = useRef(null)
  const [width, setWidth] = useState(600)
  useEffect(() => {
    const el = ref.current
    if (!el) return undefined
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(280, entry.contentRect.width)))
    observer.observe(el)
    return () => observer.disconnect()
  }, [])
  return [ref, width]
}

// Graphique "Compte detaille" : solde total (courant + Livret Bleu) apres
// chaque operation, en escalier (il ne change qu'aux operations).
// - Etalees : toutes les saisons a la suite, chacune dans sa bande ;
// - Superposees : une courbe par saison sur le meme axe (debut -> fin de
//   saison), pour comparer les saisons entre elles ; un clic sur une saison
//   de la legende la masque ou la reaffiche ;
// - Selectionnee : la saison choisie seule.
// Sert aussi a l'onglet Comptes (periode "Saisons", voir BankHistory.jsx) :
// hiddenKey : ou retenir les saisons masquees.
export function CurveChart({ data, selected, mode, hiddenKey = HIDDEN_KEY }) {
  const [ref, width] = useWidth()
  const narrow = width < 480
  const margin = { top: 26, right: 12, bottom: 28, left: narrow ? 46 : 66 }
  const innerW = width - margin.left - margin.right
  const innerH = CHART_HEIGHT - margin.top - margin.bottom
  const series = data.series.map((p) => ({ t: ts(p.date), v: p.total }))
  const today = ts(data.today)
  const lastKnown = series.length ? series[series.length - 1].t : today
  const seasons = data.seasons
  // Superposees : saisons masquees d'un clic dans la legende (choix retenu
  // sur cet appareil).
  const [hidden, setHidden] = useState(() => readHidden(hiddenKey))
  // Position horizontale du doigt ou de la souris sur le graphique (px).
  const [pointerX, setPointerX] = useState(null)
  function toggle(id) {
    const next = new Set(hidden)
    if (!next.delete(id)) next.add(id)
    setHidden(next)
    writeSetting(hiddenKey, JSON.stringify([...next]))
  }

  // Solde en fin de journee t (derniere operation ce jour-la ou avant).
  function valueAt(t) {
    let value = null
    for (const p of series) {
      if (p.t > t) break
      value = p.v
    }
    return value
  }

  // Points d'une saison, de son debut a sa fin (ou au dernier jour connu).
  function seasonPoints(season) {
    const start = ts(season.startDate)
    const end = Math.min(ts(season.endDate), Math.max(today, lastKnown))
    const points = []
    const initial = valueAt(start)
    if (initial != null) points.push({ t: start, v: initial })
    for (const p of series) if (p.t > start && p.t <= end) points.push(p)
    if (points.length) points.push({ t: end, v: points[points.length - 1].v })
    return points
  }

  // lines : [{key, color, width, points, x0, x1}] ; x0/x1 : debut et fin de
  // l'axe horizontal pour cette courbe.
  let lines
  let legend = []
  let bands = []
  if (mode === 'spread') {
    const x0 = Math.min(...[seasons[0] && ts(seasons[0].startDate), series[0]?.t].filter((v) => v != null))
    const x1 = Math.max(lastKnown, today, ...seasons.map((s) => ts(s.endDate)))
    const points = series.filter((p) => p.t >= x0 && p.t <= x1)
    if (points.length) points.push({ t: Math.min(Math.max(today, lastKnown), x1), v: points[points.length - 1].v })
    lines = [{ key: 'all', color: ACCENT, width: 2, points, x0, x1 }]
    bands = seasons.map((s) => ({ season: s, from: ts(s.startDate), to: ts(s.endDate), x0, x1 }))
  } else {
    const shown = mode === 'selected' ? [selected] : seasons
    legend = shown.map((s) => ({
      key: s.id,
      label: s.name,
      color: mode === 'selected' ? ACCENT : SEASON_COLORS[seasons.indexOf(s) % SEASON_COLORS.length],
      width: s.id === selected.id ? 2.6 : 2,
      points: seasonPoints(s),
      x0: ts(s.startDate),
      x1: ts(s.endDate),
    }))
    lines = mode === 'overlay' ? legend.filter((line) => !hidden.has(line.key)) : legend
  }
  const legendButtons = mode === 'overlay' && (
    <div className="seasons-legend">
      {legend.map((line) => {
        const off = hidden.has(line.key)
        const classes = [line.key === selected.id && 'seasons-legend-selected', off && 'seasons-legend-off']
        return (
          <button
            key={line.key}
            type="button"
            className={classes.filter(Boolean).join(' ') || undefined}
            aria-pressed={!off}
            title={off ? 'Afficher cette saison' : 'Masquer cette saison'}
            onClick={() => toggle(line.key)}
          >
            <i style={{ background: line.color }} />
            {line.label}
          </button>
        )
      })}
    </div>
  )

  const values = lines.flatMap((l) => l.points.map((p) => p.v))
  if (values.length === 0) {
    return (
      <div ref={ref} className="seasons-chart">
        <p className="balance-chart-empty">
          {legend.length > 0 && lines.length === 0
            ? "Toutes les saisons sont masquées : touchez une saison ci-dessous pour l'afficher."
            : "Pas encore d'opérations bancaires sur cette période (voir Comptes)."}
        </p>
        {legendButtons}
      </div>
    )
  }
  const rawMin = Math.min(...values)
  const rawMax = Math.max(...values)
  const pad = (rawMax - rawMin || Math.abs(rawMax) * 0.05 || 1) * 0.12
  const yMin = rawMin - pad
  const yMax = rawMax + pad
  const y = (v) => margin.top + (1 - (v - yMin) / (yMax - yMin)) * innerH
  const xOf = (line, t) => margin.left + ((t - line.x0) / (line.x1 - line.x0 || 1)) * innerW

  function stepPath(line) {
    return line.points
      .map((p, i) => {
        const x = xOf(line, p.t).toFixed(1)
        return i === 0 ? `M${x},${y(p.v).toFixed(1)}` : `H${x} V${y(p.v).toFixed(1)}`
      })
      .join(' ')
  }

  // Sous le doigt : une ligne verticale et, pour chaque courbe affichee, le
  // solde a cette date (meme position dans la saison en "Superposées").
  const fraction = pointerX == null ? null : Math.min(1, Math.max(0, (pointerX - margin.left) / innerW))
  const cursorX = fraction == null ? null : margin.left + fraction * innerW
  const dayAt = (line) => Math.round((line.x0 + fraction * (line.x1 - line.x0)) / DAY_MS) * DAY_MS
  const readout =
    fraction == null
      ? []
      : lines.flatMap((line) => {
          const t = dayAt(line)
          if (line.points.length === 0) return []
          if (t < line.points[0].t || t > line.points[line.points.length - 1].t) return []
          let v = line.points[0].v
          for (const p of line.points) {
            if (p.t > t) break
            v = p.v
          }
          return [{ line, t, v }]
        })
  const readoutDate =
    readout.length === 0
      ? null
      : mode === 'overlay'
        ? dayMonth.format(dayAt({ x0: ts(selected.startDate), x1: ts(selected.endDate) }))
        : dayMonthYear.format(readout[0].t)
  const track = (e) => setPointerX(e.clientX - e.currentTarget.getBoundingClientRect().left)

  // Axe horizontal : dates de la saison (Selectionnee) ou mois de la saison
  // choisie (Superposees, toutes les saisons ramenees sur le meme axe).
  const reference = lines[lines.length - 1] ?? legend[0]
  const xTicks =
    mode === 'spread'
      ? []
      : (narrow ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1]).map((f) => {
          const base = mode === 'overlay' ? { x0: ts(selected.startDate), x1: ts(selected.endDate) } : reference
          const t = base.x0 + f * (base.x1 - base.x0)
          return { x: margin.left + f * innerW, label: mode === 'overlay' ? monthShort.format(t) : monthYear.format(t) }
        })

  return (
    <div ref={ref} className="seasons-chart">
      <svg
        width={width}
        height={CHART_HEIGHT}
        role="img"
        aria-label="Évolution du solde total par saison"
        onPointerDown={track}
        onPointerMove={track}
        // Au doigt, la lecture reste affichee apres le toucher.
        onPointerLeave={(e) => e.pointerType === 'mouse' && setPointerX(null)}
      >
        {bands.map((b) => {
          const left = xOf(b, b.from)
          const right = xOf(b, b.to)
          const isSelected = b.season.id === selected.id
          return (
            <g key={b.season.id}>
              {isSelected && (
                <rect x={left} y={margin.top} width={right - left} height={innerH} fill={ACCENT} opacity="0.08" />
              )}
              <line x1={right} x2={right} y1={margin.top} y2={margin.top + innerH} className="balance-chart-grid" />
              <text
                x={(left + right) / 2}
                y={margin.top - 9}
                textAnchor="middle"
                className={isSelected ? 'seasons-axis-strong' : 'balance-chart-axis'}
              >
                {shortName(b.season.name, narrow || right - left < 70)}
              </text>
            </g>
          )
        })}
        {niceTicks(yMin, yMax, 5).map((v) => (
          <g key={v}>
            <line x1={margin.left} x2={width - margin.right} y1={y(v)} y2={y(v)} className="balance-chart-grid" />
            <text x={margin.left - 8} y={y(v) + 4} textAnchor="end" className="balance-chart-axis">
              {narrow ? `${Math.round(v / 100) / 10 || 0} k` : eurosRound(v)}
            </text>
          </g>
        ))}
        {xTicks.map((tick, i) => (
          <text
            key={i}
            x={tick.x}
            y={CHART_HEIGHT - 8}
            textAnchor={i === 0 ? 'start' : i === xTicks.length - 1 ? 'end' : 'middle'}
            className="balance-chart-axis"
          >
            {tick.label}
          </text>
        ))}
        {lines.map((line) => (
          <path
            key={line.key}
            d={stepPath(line)}
            fill="none"
            stroke={line.color}
            strokeWidth={line.width}
            strokeLinejoin="round"
          />
        ))}
        {readout.length > 0 && (
          <line x1={cursorX} x2={cursorX} y1={margin.top} y2={margin.top + innerH} className="balance-chart-cursor" />
        )}
        {readout.map(({ line, v }) => (
          <circle key={line.key} cx={cursorX} cy={y(v)} r="4.5" fill={line.color} className="seasons-chart-dot" />
        ))}
      </svg>
      {readout.length > 0 && (
        <div
          className="balance-chart-tooltip seasons-tooltip"
          style={
            cursorX > width / 2
              ? { top: margin.top, right: width - cursorX + 12 }
              : { top: margin.top, left: cursorX + 12 }
          }
        >
          <div className="seasons-tooltip-date">{readoutDate}</div>
          {readout.map(({ line, v }) => (
            <div key={line.key} className="seasons-tooltip-row">
              <b>{euros(v)}</b>
              {mode === 'overlay' && (
                <span>
                  <i style={{ background: line.color }} />
                  {line.label}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      {legendButtons}
    </div>
  )
}
