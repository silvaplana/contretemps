// Sous-module Prévisionnel (spec/modules/financier.md §6), repris de Sambo
// Admin (Forecasts.jsx) : prévisionnels d'une saison (voir backend/src/
// finances/forecasts.py). Même écran que Bilan (liste par saison, états,
// panneau). Chaque prévisionnel a un nom, un état, une date de départ, des
// consignes et un modèle ; « Produire le prévisionnel » fait écrire une
// formule Python (vérifiée et exécutée à part par l'appli) qui prévoit le
// solde de tous les comptes chaque semaine jusqu'à la fin de la saison. Les
// curseurs règlent les paramètres de la formule : la courbe est recalculée
// sans rappeler le modèle, et leur position est enregistrée.
import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { enEuros } from '../../utils/euros.js'
import { telechargerFichier } from '../../utils/telechargement.js'
import * as api from './api.js'
import { niceTicks } from './BalanceChart.jsx'
import './finances.css'

const POLL_MS = 2000
// Délai après le dernier mouvement d'un curseur avant de recalculer.
const SLIDER_DELAY_MS = 250
const STATE_LABELS = { brouillon: 'Brouillon', valide: 'Validé', officiel: 'Officiel' }
// Couleurs des courbes (thème clair ; les mêmes que forecast_exports.py).
const REAL = '#7c3aed'
const FORECAST = '#d8722a'
const ACTUAL = '#8a8a8a'
// Saisons comparées : mêmes couleurs que « Saisons » dans Comptes (CurveChart.jsx).
const SEASON_COLORS = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#9085e9']
const CHART_HEIGHT = 280
const DAY_MS = 86_400_000
const SEASON_KEY = 'finances-previsionnel-saison'
const COMPARE_KEY = 'finances-previsionnel-comparer'
const NEW_EVENT = 'finances-new-forecast'

// Entrée « Nouveau prévisionnel » du menu ⋯ (voir Financier.jsx).
export function requestNewForecast() {
  window.dispatchEvent(new Event(NEW_EVENT))
}

const { euros, dateFr } = api
const eurosRound = (n) => (n == null ? '—' : `${(Math.round(n) || 0).toLocaleString('fr-FR')} €`)
const dateHeure = (iso) => dateFr(iso.slice(0, 10))
const ts = (isoDate) => Date.parse(`${isoDate.slice(0, 10)}T00:00:00Z`)
const monthShort = new Intl.DateTimeFormat('fr-FR', { month: 'short', timeZone: 'UTC' })

function paramLabel(param, value) {
  const text = Number(value).toLocaleString('fr-FR', { maximumFractionDigits: 2 })
  return param.unit ? `${text} ${param.unit}` : text
}

function readSeason(seasons) {
  try {
    const id = Number(localStorage.getItem(SEASON_KEY))
    if (seasons.some((s) => s.id === id)) return id
  } catch {
    // Stockage indisponible : la saison en cours.
  }
  return (seasons.find((s) => s.current) ?? seasons[seasons.length - 1])?.id ?? null
}

function readCompare() {
  try {
    const ids = JSON.parse(localStorage.getItem(COMPARE_KEY) ?? 'null')
    return Array.isArray(ids) ? new Set(ids) : null
  } catch {
    return null
  }
}

function writeCompare(ids) {
  try {
    localStorage.setItem(COMPARE_KEY, JSON.stringify([...ids]))
  } catch {
    // Stockage indisponible : le choix ne sera juste pas retenu.
  }
}

// Solde total de tous les comptes, un point par jour d'opération, du plus
// ancien au plus récent (les lignes de l'historique arrivent du plus récent).
function totalSeries(ledger) {
  const series = []
  for (const row of [...ledger.rows].reverse()) {
    if (row.total == null) continue
    const t = ts(row.date)
    if (series.length && series[series.length - 1].t === t) series[series.length - 1].v = row.total
    else series.push({ t, v: row.total })
  }
  return series
}

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

export default function Previsionnel() {
  // Saisons et date du jour (GET /seasons), historique des comptes pour le graphique.
  const [seasonsData, setSeasonsData] = useState(null)
  const [ledger, setLedger] = useState(null)
  const [seasonId, setSeasonId] = useState(null)
  const [listing, setListing] = useState(null)
  const [filter, setFilter] = useState('all')
  const [error, setError] = useState(null)
  // Prévisionnel ouvert : null, 'new' ou son id.
  const [editing, setEditing] = useState(null)

  useEffect(() => {
    Promise.all([api.saisons(), api.historique()])
      .then(([data, history]) => {
        setSeasonsData(data)
        setLedger(history)
        setSeasonId(readSeason(data.seasons))
      })
      .catch((err) => setError(err.message))
  }, [])

  const load = useCallback(async () => {
    if (seasonId == null) return
    try {
      setListing(await api.previsionnels(seasonId))
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [seasonId])

  useEffect(() => {
    load()
  }, [load])

  // Menu ⋯ : « Nouveau prévisionnel ».
  useEffect(() => {
    const open = () => setEditing('new')
    window.addEventListener(NEW_EVENT, open)
    return () => window.removeEventListener(NEW_EVENT, open)
  }, [])

  if (error) return <p className="login-screen__erreur">{error}</p>
  if (!seasonsData || !ledger) return <p className="muted">Chargement…</p>
  const seasons = seasonsData.seasons
  if (seasons.length === 0) return <p className="muted">Aucune saison : créez-la d’abord dans Admin › École.</p>

  const season = seasons.find((s) => s.id === seasonId)
  const forecasts = listing?.forecasts ?? []
  const shown = forecasts.filter((f) => filter === 'all' || f.state === filter)

  async function remove(forecast) {
    if (
      !window.confirm(
        `Supprimer le prévisionnel « ${forecast.name} » ?\n\nSes consignes, sa formule, la position des curseurs et son coût sont effacés. Les opérations bancaires ne sont pas touchées.`,
      )
    )
      return
    try {
      await api.supprimerPrevisionnel(forecast.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (editing !== null && listing && season)
    return (
      <ForecastPanel
        key={editing}
        forecastId={editing === 'new' ? null : editing}
        season={season}
        seasonsData={seasonsData}
        ledger={ledger}
        options={listing}
        onClose={() => {
          setEditing(null)
          load()
        }}
        onCreated={(id) => setEditing(id)}
      />
    )

  return (
    <section className="fin-bilan fin-prev reports">
      <div className="seasons-toolbar">
        <select
          aria-label="Saison"
          value={seasonId ?? ''}
          onChange={(e) => {
            const id = Number(e.target.value)
            setSeasonId(id)
            try {
              localStorage.setItem(SEASON_KEY, String(id))
            } catch {
              // Stockage indisponible : le choix ne sera juste pas retenu.
            }
          }}
        >
          {[...seasons].reverse().map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
              {s.current ? ' (en cours)' : ''}
              {listing?.counts && ` : ${listing.counts[s.id] ?? 0}`}
            </option>
          ))}
        </select>
        <button type="button" className="btn btn--primary" onClick={() => setEditing('new')} disabled={!listing}>
          <Icon name="plus" size={18} /> Nouveau prévisionnel
        </button>
      </div>

      <div className="filter-chips" role="group" aria-label="État">
        {['all', ...Object.keys(STATE_LABELS)].map((state) => (
          <button
            key={state}
            type="button"
            className={state === filter ? 'filter-chip filter-chip-active' : 'filter-chip'}
            aria-pressed={state === filter}
            onClick={() => setFilter(state)}
          >
            {state === 'all' ? 'Tous' : STATE_LABELS[state]} ({forecasts.filter((f) => state === 'all' || f.state === state).length})
          </button>
        ))}
      </div>

      {!listing ? (
        <p className="muted">Chargement…</p>
      ) : shown.length === 0 ? (
        <p className="muted">
          {forecasts.length === 0 ? `Aucun prévisionnel pour ${season?.name} : créez-en un.` : 'Aucun prévisionnel dans cet état.'}
        </p>
      ) : (
        <ul className="reports-list">
          {shown.map((f) => (
            // Toute la carte ouvre le prévisionnel.
            <li key={f.id} className="reports-item-open" onClick={() => setEditing(f.id)}>
              <div className="reports-item-main">
                <span className="reports-item-name">{f.name}</span>
                <span className="reports-item-meta">
                  <span className={`reports-badge reports-badge-${f.state}`}>{STATE_LABELS[f.state]}</span>
                  {f.status === 'running' ? (
                    'calcul en cours…'
                  ) : f.status === 'error' ? (
                    'dernier calcul en erreur'
                  ) : f.endBalance != null ? (
                    <>
                      au {dateFr(season.endDate)} : <b className="forecasts-end">{eurosRound(f.endBalance)}</b>
                    </>
                  ) : (
                    'pas encore calculé'
                  )}
                  {' · '}
                  {f.hasResult ? `${f.modelLabel} · ` : ''}
                  {enEuros(f.aiCostUsd)}
                  {' · '}
                  {dateHeure(f.updatedAt)}
                </span>
              </div>
              <button
                type="button"
                className="icon-btn icon-btn--danger"
                onClick={(e) => {
                  e.stopPropagation()
                  remove(f)
                }}
                aria-label={`Supprimer ${f.name}`}
                title="Supprimer"
              >
                <Icon name="trash" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}

// Panneau d'un prévisionnel : création (forecastId null) ou modification.
function ForecastPanel({ forecastId, season, seasonsData, ledger, options, onClose, onCreated }) {
  const [forecast, setForecast] = useState(null)
  const [form, setForm] = useState({
    name: `Prévision ${season.name}`,
    state: 'brouillon',
    startDate: '',
    prompt: '',
    model: options.defaultModel,
  })
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [tab, setTab] = useState('explain')
  // Position des curseurs à l'écran (enregistrée après SLIDER_DELAY_MS).
  const [params, setParams] = useState({})
  const [replaying, setReplaying] = useState(false)
  const timer = useRef(null)

  const load = useCallback(async () => {
    const data = await api.previsionnel(forecastId)
    setForecast(data)
    return data
  }, [forecastId])

  useEffect(() => {
    if (forecastId == null) return
    load()
      .then((data) => {
        setForm({ name: data.name, state: data.state, startDate: data.startDate ?? '', prompt: data.prompt, model: data.model })
        setParams(data.params)
      })
      .catch((err) => setError(err.message))
  }, [forecastId, load])

  // Calcul en cours : relu jusqu'à la fin.
  const running = forecast?.status === 'running'
  useEffect(() => {
    if (!running) return undefined
    const poll = setInterval(() => {
      load()
        .then((data) => {
          if (data.status === 'idle') setParams(data.params)
        })
        .catch(() => {
          // Coupure passagère : on réessaie au prochain tour.
        })
    }, POLL_MS)
    return () => clearInterval(poll)
  }, [running, load])

  useEffect(() => () => clearTimeout(timer.current), [])

  function update(key) {
    return (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))
  }

  // Crée le prévisionnel s'il est nouveau, sinon enregistre ses champs ; retourne son id.
  async function save() {
    if (forecastId == null) return (await api.creerPrevisionnel({ ...form, seasonId: season.id })).id
    setForecast(await api.modifierPrevisionnel(forecastId, form))
    return forecastId
  }

  async function submit(run) {
    setPending(true)
    setError(null)
    setMessage(null)
    try {
      const id = await save()
      if (run) {
        const started = await api.calculerPrevisionnel(id, form)
        if (forecastId == null) {
          onCreated(id)
          return
        }
        setForecast(started)
      } else if (forecastId == null) {
        onCreated(id)
        return
      } else {
        setMessage('Prévisionnel enregistré')
      }
    } catch (err) {
      setError(err.message)
    }
    setPending(false)
  }

  // Un curseur bouge : la valeur s'affiche tout de suite, la formule est
  // rejouée (et la position enregistrée) une fois le curseur immobile.
  function slide(name, value) {
    const next = { ...params, [name]: value }
    setParams(next)
    clearTimeout(timer.current)
    timer.current = setTimeout(() => replay(next), SLIDER_DELAY_MS)
  }

  async function replay(next) {
    setReplaying(true)
    try {
      setForecast(await api.reglerPrevisionnel(forecastId, next))
    } catch (err) {
      setError(err.message)
    }
    setReplaying(false)
  }

  function resetParams() {
    const defaults = Object.fromEntries(forecast.result.parameters.map((p) => [p.name, p.default]))
    setParams(defaults)
    clearTimeout(timer.current)
    replay(defaults)
  }

  // seasonIds : saisons affichées dans le graphique pour comparer ; le fichier
  // contient les mêmes.
  function download(format, seasonIds) {
    const nom = `previsionnel-${season.name}-${form.name}.${format}`.replace(/[\\/:*?"<>|]/g, '-')
    telechargerFichier(api.urlTelechargementPrevisionnel(forecastId, format, seasonIds), nom).catch((err) => setError(err.message))
  }

  const result = forecast?.result
  const locked = pending || running
  const ended = seasonsData.today > season.endDate

  return (
    <section className="fin-bilan fin-prev reports">
      <div className="reports-panel-header">
        <button type="button" className="btn btn--link nf-retour" onClick={onClose}>
          ← Prévisionnels de {season.name}
        </button>
        <h2>{forecastId == null ? 'Nouveau prévisionnel' : form.name}</h2>
      </div>

      <div className="reports-form">
        <label>
          Nom
          <input className="field-input" value={form.name} onChange={update('name')} autoComplete="off" />
        </label>
        <label>
          État
          <select className="field-input" value={form.state} onChange={update('state')}>
            {options.states.map((s) => (
              <option key={s.id} value={s.id}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label className="reports-form-wide">
          Date de départ
          <input
            className="field-input"
            type="date"
            value={form.startDate}
            min={season.startDate}
            max={season.endDate}
            onChange={update('startDate')}
          />
          {/* Raccourcis : aujourd'hui (si la saison est en cours) ou le 1er jour de la saison. */}
          <span className="forecasts-date-shortcuts">
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => setForm((prev) => ({ ...prev, startDate: seasonsData.today }))}
              disabled={seasonsData.today < season.startDate || seasonsData.today >= season.endDate}
            >
              Aujourd’hui
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => setForm((prev) => ({ ...prev, startDate: season.startDate }))}>
              Début de saison
            </button>
            <button type="button" className="btn btn--secondary" onClick={() => setForm((prev) => ({ ...prev, startDate: '' }))} disabled={!form.startDate}>
              Dernier relevé
            </button>
          </span>
          <span className="reports-hint">
            {form.startDate
              ? 'Le réel après cette date s’affiche pour comparer.'
              : ended
                ? 'Saison terminée : choisissez une date pour tester.'
                : 'Vide : dernier jour connu des comptes.'}
          </span>
        </label>
        <label className="reports-form-wide">
          Consignes
          <textarea
            className="field-input"
            rows={3}
            value={form.prompt}
            onChange={update('prompt')}
            placeholder="Ex : prévois le solde jusqu’à fin juin. Curseurs : nouveaux inscrits d’ici mars (0 à 20, défaut 5), salaire mensuel (400 à 800 €, défaut 580)…"
          />
          <span className="reports-hint">
            S’ajoutent aux consignes fixes : écrire une formule qui donne le solde de tous les comptes chaque semaine jusqu’à la fin
            de la saison, et déclarer les curseurs nommés dans les consignes (libellé, min, max, défaut). L’appli lui prépare les
            données : solde réel à la date de départ, moyennes mensuelles par catégorie des 12 derniers mois.
          </span>
        </label>
        <label>
          Modèle
          <select className="field-input" value={form.model} onChange={update('model')}>
            {options.models.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
        </label>
        <div className="reports-cost">
          <span>Coût cumulé</span>
          <b>{enEuros(forecast?.aiCostUsd ?? 0)}</b>
        </div>
      </div>

      {error && <p className="login-screen__erreur">{error}</p>}
      {message && <p className="muted">{message}</p>}
      {forecast?.status === 'error' && <p className="login-screen__erreur">{forecast.error}</p>}

      <div className="reports-actions">
        <button type="button" className="btn btn--secondary" onClick={() => submit(false)} disabled={locked}>
          Enregistrer
        </button>
        <button type="button" className="btn btn--primary" onClick={() => submit(true)} disabled={locked || !form.name.trim()}>
          {running ? 'Calcul en cours…' : 'Produire le prévisionnel'}
        </button>
      </div>

      <div className="reports-result">
        <div className="reports-result-header">
          <h3>Formule</h3>
          {result && (
            <span className="reports-result-meta">
              {result.modelLabel} · {enEuros(result.costUsd)} · {dateHeure(result.generatedAt)}
            </span>
          )}
        </div>

        {running ? (
          <div className="reports-running">
            <div className="reports-progress" />
            <p>La formule s’écrit, puis l’appli la vérifie et la teste… (jusqu’à quelques minutes)</p>
          </div>
        ) : !result ? (
          <p className="muted">Pas encore de formule : appuyez sur « Produire le prévisionnel ».</p>
        ) : (
          <>
            <div className="filter-chips" role="group" aria-label="Formule">
              {[
                ['explain', 'Explication'],
                ['code', 'Formule Python'],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  className={id === tab ? 'filter-chip filter-chip-active' : 'filter-chip'}
                  aria-pressed={id === tab}
                  onClick={() => setTab(id)}
                >
                  {label}
                </button>
              ))}
            </div>
            <div className="reports-check">
              <b>Formule vérifiée</b> : une seule fonction prevoir, aucun import hors math et datetime, ni fichier ni réseau ;
              exécutée à part par l’appli. Départ le {dateFr(result.data.dateDepart)} avec {euros(result.data.soldeDepart)} (tous
              les comptes).
            </div>
            {tab === 'explain' ? <p className="forecasts-explanation">{result.explanation}</p> : <pre className="forecasts-code">{result.code}</pre>}
          </>
        )}
      </div>

      {result && !running && (
        <>
          <div className="reports-result">
            <div className="reports-result-header">
              <h3>Curseurs</h3>
              <span className="reports-result-meta">{replaying ? 'recalcul…' : 'position enregistrée automatiquement'}</span>
              <div className="reports-downloads">
                <button type="button" className="btn btn--secondary" onClick={resetParams}>
                  Revenir aux défauts
                </button>
              </div>
            </div>
            {result.parameters.length === 0 ? (
              <p className="muted">Cette formule n’a pas de curseur.</p>
            ) : (
              <div className="forecasts-params">
                {result.parameters.map((p) => {
                  const value = params[p.name] ?? p.default
                  return (
                    <label key={p.name} className="forecasts-param">
                      <span className="forecasts-param-head">
                        <span>{p.label}</span>
                        <b>{paramLabel(p, value)}</b>
                      </span>
                      <input type="range" min={p.min} max={p.max} step={p.step} value={value} onChange={(e) => slide(p.name, Number(e.target.value))} />
                      <span className="forecasts-param-bounds">
                        <span>{paramLabel(p, p.min)}</span>
                        <span>défaut {paramLabel(p, p.default)}</span>
                        <span>{paramLabel(p, p.max)}</span>
                      </span>
                    </label>
                  )
                })}
              </div>
            )}
          </div>
          <ForecastResult result={result} season={season} seasonsData={seasonsData} ledger={ledger} onDownload={download} />
        </>
      )}
    </section>
  )
}

// Solde total en fin de journée t.
function valueAt(series, t) {
  let value = null
  for (const p of series) {
    if (p.t > t) break
    value = p.v
  }
  return value
}

// Points (t, v) du solde réel de from à to, en escalier ; le dernier point
// prolonge le solde jusqu'à `to`.
function realPoints(series, from, to) {
  const points = []
  const initial = valueAt(series, from - DAY_MS)
  if (initial != null) points.push({ t: from, v: initial })
  for (const p of series) if (p.t >= from && p.t <= to) points.push(p)
  if (points.length) points.push({ t: to, v: points[points.length - 1].v })
  return points
}

// Chiffres clés et graphique : saisons superposées (comme « Saisons » dans
// Comptes), réel puis prévision, autres saisons au choix.
function ForecastResult({ result, season, seasonsData, ledger, onDownload }) {
  const seasons = seasonsData.seasons
  const others = seasons.filter((s) => s.id !== season.id && s.startDate < season.startDate)
  const previous = others[others.length - 1]
  // Saisons comparées (choix retenu sur cet appareil) ; par défaut la précédente.
  const [compare, setCompare] = useState(() => readCompare() ?? new Set(previous ? [previous.id] : []))
  function toggle(id) {
    const next = new Set(compare)
    if (!next.delete(id)) next.add(id)
    setCompare(next)
    writeCompare(next)
  }

  // Saisons réellement affichées pour comparer (reprises dans les fichiers).
  const shownSeasons = others.filter((s) => compare.has(s.id)).map((s) => s.id)
  const points = result.points
  const end = points[points.length - 1]
  const series = totalSeries(ledger)
  const start = ts(result.data.dateDepart)
  const lastKnown = series.length ? series[series.length - 1].t : start
  const afterStart = lastKnown > start ? realPoints(series, start, Math.min(lastKnown, ts(season.endDate))) : []
  const actualEnd = afterStart.length ? afterStart[afterStart.length - 1] : null
  // Solde du début de la saison (la « ligne d'équilibre » du graphique) et
  // résultat prévu de la saison : ce qu'elle aura gagné ou perdu.
  const opening = result.data.soldeDebutSaison ?? null
  const outcome = opening == null ? null : Math.round((end.solde - opening) * 100) / 100

  return (
    <div className="reports-result">
      <div className="seasons-figures forecasts-figures">
        <div className="seasons-figure">
          <span className="seasons-figure-label">Solde au {dateFr(season.startDate)}</span>
          <span className="seasons-figure-value">{opening != null ? euros(opening) : '—'}</span>
          <span className="seasons-figure-sub">début de saison</span>
        </div>
        <div className="seasons-figure">
          <span className="seasons-figure-label">Solde prévu au {dateFr(season.endDate)}</span>
          <span className="seasons-figure-value forecasts-end">{euros(end.solde)}</span>
          <span className="seasons-figure-sub">
            {actualEnd ? `réel : ${eurosRound(actualEnd.v)} le ${dateFr(new Date(actualEnd.t).toISOString())}` : 'fin de saison'}
          </span>
        </div>
        <div className="seasons-figure">
          <span className="seasons-figure-label">Résultat prévu au {dateFr(season.endDate)}</span>
          <span className={`seasons-figure-value${outcome == null ? '' : outcome >= 0 ? ' forecasts-positive' : ' forecasts-negative'}`}>
            {outcome == null ? '—' : `${outcome >= 0 ? '+' : '−'}${euros(Math.abs(outcome))}`}
          </span>
          <span className="seasons-figure-sub">solde prévu moins solde de début de saison</span>
        </div>
      </div>
      <ForecastChart
        series={series}
        season={season}
        start={start}
        points={points}
        afterStart={afterStart}
        others={others}
        seasons={seasons}
        compare={compare}
        onToggle={toggle}
        baseline={opening}
      />
      <div className="reports-downloads forecasts-downloads">
        <button type="button" className="btn btn--secondary" onClick={() => onDownload('png', shownSeasons)}>
          <Icon name="download" size={18} /> Image
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => onDownload('pdf', shownSeasons)}>
          <Icon name="download" size={18} /> PDF
        </button>
      </div>
      <p className="reports-hint">
        Saisons superposées du début à la fin de saison. Prévision : un point par semaine ; bouger un curseur la recalcule sans
        rappeler le modèle.
      </p>
    </div>
  )
}

// baseline : solde du début de la saison, tracé en « ligne d'équilibre » (au-
// dessus, la saison a gagné de l'argent ; en dessous, elle en a perdu).
function ForecastChart({ series, season, start, points, afterStart, others, seasons, compare, onToggle, baseline }) {
  const [ref, width] = useWidth()
  const narrow = width < 480
  const margin = { top: 22, right: 12, bottom: 28, left: narrow ? 46 : 66 }
  const innerW = width - margin.left - margin.right
  const innerH = CHART_HEIGHT - margin.top - margin.bottom
  const x0 = ts(season.startDate)
  const x1 = ts(season.endDate)
  const [pointerX, setPointerX] = useState(null)

  // Courbes, ramenées sur l'axe de la saison choisie (décalage en jours).
  const lines = [
    ...others
      .filter((s) => compare.has(s.id))
      .map((s) => {
        const offset = x0 - ts(s.startDate)
        return {
          key: `s${s.id}`,
          label: s.name,
          color: SEASON_COLORS[seasons.indexOf(s) % SEASON_COLORS.length],
          width: 1.6,
          step: true,
          points: realPoints(series, ts(s.startDate), ts(s.endDate)).map((p) => ({ t: p.t + offset, v: p.v })),
        }
      }),
    { key: 'after', label: 'réel après le départ', color: ACTUAL, width: 1.8, step: true, points: afterStart },
    { key: 'real', label: `${season.name} réalisé`, color: REAL, width: 2.6, step: true, points: realPoints(series, x0, start) },
    { key: 'forecast', label: 'prévision', color: FORECAST, width: 2.6, dashed: true, points: points.map((p) => ({ t: ts(p.date), v: p.solde })) },
  ].filter((l) => l.points.length > 0)

  const values = [...lines.flatMap((l) => l.points.map((p) => p.v)), ...(baseline == null ? [] : [baseline])]
  const rawMin = Math.min(...values)
  const rawMax = Math.max(...values)
  const pad = (rawMax - rawMin || Math.abs(rawMax) * 0.05 || 1) * 0.12
  const yMin = rawMin - pad
  const yMax = rawMax + pad
  const y = (v) => margin.top + (1 - (v - yMin) / (yMax - yMin)) * innerH
  const x = (t) => margin.left + ((t - x0) / (x1 - x0 || 1)) * innerW

  function path(line) {
    return line.points
      .map((p, i) => {
        const px = x(p.t).toFixed(1)
        if (i === 0) return `M${px},${y(p.v).toFixed(1)}`
        return line.step ? `H${px} V${y(p.v).toFixed(1)}` : `L${px},${y(p.v).toFixed(1)}`
      })
      .join(' ')
  }

  // Lecture sous le doigt : solde de chaque courbe à cette date.
  const fraction = pointerX == null ? null : Math.min(1, Math.max(0, (pointerX - margin.left) / innerW))
  const cursorT = fraction == null ? null : Math.round((x0 + fraction * (x1 - x0)) / DAY_MS) * DAY_MS
  const readout =
    cursorT == null
      ? []
      : lines.flatMap((line) => {
          const pts = line.points
          if (cursorT < pts[0].t || cursorT > pts[pts.length - 1].t) return []
          let v = pts[0].v
          for (let i = 0; i < pts.length; i++) {
            if (pts[i].t > cursorT) {
              if (!line.step && i > 0) {
                const a = pts[i - 1]
                const b = pts[i]
                v = a.v + ((b.v - a.v) * (cursorT - a.t)) / (b.t - a.t || 1)
              }
              break
            }
            v = pts[i].v
          }
          return [{ line, v }]
        })
  const cursorX = cursorT == null ? null : x(cursorT)
  const track = (e) => setPointerX(e.clientX - e.currentTarget.getBoundingClientRect().left)
  const xTicks = (narrow ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1]).map((f) => ({ x: margin.left + f * innerW, t: x0 + f * (x1 - x0) }))

  return (
    <div className="forecasts-chart-block">
      <div className="seasons-legend forecasts-legend">
        <span>
          <i style={{ background: REAL }} />
          réalisé
        </span>
        <span>
          <i className="forecasts-dash" />
          prévision
        </span>
        {afterStart.length > 0 && (
          <span>
            <i style={{ background: ACTUAL }} />
            réel après le départ
          </span>
        )}
        {baseline != null && (
          <span>
            <i className="forecasts-baseline-key" />
            ligne d’équilibre
          </span>
        )}
        {others.map((s) => {
          const on = compare.has(s.id)
          return (
            <button
              key={s.id}
              type="button"
              className={on ? undefined : 'seasons-legend-off'}
              aria-pressed={on}
              title={on ? 'Masquer cette saison' : 'Comparer avec cette saison'}
              onClick={() => onToggle(s.id)}
            >
              <i style={{ background: SEASON_COLORS[seasons.indexOf(s) % SEASON_COLORS.length] }} />
              {s.name}
            </button>
          )
        })}
      </div>
      <div ref={ref} className="seasons-chart">
        <svg
          width={width}
          height={CHART_HEIGHT}
          role="img"
          aria-label="Solde réel et prévu de la saison"
          onPointerDown={track}
          onPointerMove={track}
          onPointerLeave={(e) => e.pointerType === 'mouse' && setPointerX(null)}
        >
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
              {monthShort.format(tick.t)}
            </text>
          ))}
          {baseline != null && (
            <line x1={margin.left} x2={width - margin.right} y1={y(baseline)} y2={y(baseline)} className="forecasts-baseline" />
          )}
          <line x1={x(start)} x2={x(start)} y1={margin.top} y2={margin.top + innerH} className="forecasts-start" />
          <text x={x(start)} y={margin.top - 8} textAnchor="middle" className="balance-chart-axis">
            départ
          </text>
          {lines.map((line) => (
            <path
              key={line.key}
              d={path(line)}
              fill="none"
              stroke={line.color}
              strokeWidth={line.width}
              strokeDasharray={line.dashed ? '7 5' : undefined}
              strokeLinejoin="round"
            />
          ))}
          {/* Par-dessus les courbes, avec un liseré pour rester lisible. */}
          {baseline != null && (
            <text x={width - margin.right} y={y(baseline) - 6} textAnchor="end" className="balance-chart-axis forecasts-baseline-label">
              ligne d’équilibre : {eurosRound(baseline)}
            </text>
          )}
          {readout.length > 0 && <line x1={cursorX} x2={cursorX} y1={margin.top} y2={margin.top + innerH} className="balance-chart-cursor" />}
          {readout.map(({ line, v }) => (
            <circle key={line.key} cx={cursorX} cy={y(v)} r="4.5" fill={line.color} className="seasons-chart-dot" />
          ))}
        </svg>
        {readout.length > 0 && (
          <div
            className="balance-chart-tooltip seasons-tooltip"
            style={cursorX > width / 2 ? { top: margin.top, right: width - cursorX + 12 } : { top: margin.top, left: cursorX + 12 }}
          >
            <div className="seasons-tooltip-date">{dateFr(new Date(cursorT).toISOString())}</div>
            {readout.map(({ line, v }) => (
              <div key={line.key} className="seasons-tooltip-row">
                <b>{euros(v)}</b>
                <span>
                  <i style={{ background: line.color }} />
                  {line.label}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
