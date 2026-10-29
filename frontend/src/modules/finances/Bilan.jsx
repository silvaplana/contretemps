// Sous-module Bilan (spec/modules/financier.md §4), repris de Sambo Admin
// (FinancialReports.jsx) : bilans d'une saison (voir backend/src/finances/
// reports.py). Chaque bilan a un nom, un etat (brouillon, valide, officiel),
// des consignes et un modele ; « Produire le bilan » fait calculer le compte
// d'exploitation par l'appli (au centime, avec la verification des soldes)
// et l'analyse en arriere-plan : l'ecran relit le bilan jusqu'a la fin.
import { useCallback, useEffect, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import DocumentsAG from './compta/DocumentsAG.jsx'
import { enEuros } from '../../utils/euros.js'
import { telechargerFichier } from '../../utils/telechargement.js'
import * as api from './api.js'
import './finances.css'

const POLL_MS = 2000
const STATE_LABELS = { brouillon: 'Brouillon', valide: 'Validé', officiel: 'Officiel' }
const MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.']
// Saison choisie, retenue sur cet appareil.
const SEASON_KEY = 'finances-bilan-saison'
// Demande de nouveau bilan venue du menu ⋯ (voir requestNewReport).
const NEW_EVENT = 'finances-new-report'

// Entree « Nouveau bilan » du menu ⋯ (voir Financier.jsx).
export function requestNewReport() {
  window.dispatchEvent(new Event(NEW_EVENT))
}

const { euros, dateFr } = api
const eurosRound = (n) => (n == null ? '—' : `${(Math.round(n) || 0).toLocaleString('fr-FR')} €`)
const amount = (n) => (n == null || Math.abs(n) < 0.005 ? '' : n.toLocaleString('fr-FR', { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
const dateHeure = (iso) => dateFr(iso.slice(0, 10))

// "2025-07" -> "juil.-25" (comme le modele du tresorier).
const monthLabel = (month) => `${MONTHS[Number(month.slice(5, 7)) - 1]}-${month.slice(2, 4)}`

// Lignes recettes ou depenses avec la saison precedente : montant net de la
// meme categorie, du meme cote (une depense est comptee en positif).
function comparison(result, side) {
  const previous = result.previous?.net ?? {}
  const sign = side === 'income' ? 1 : -1
  return result[side].map((row) => {
    const before = previous[row.category] == null ? null : sign * previous[row.category]
    const pct = before ? Math.round(((row.amount - before) / Math.abs(before)) * 100) : null
    // Couleur de l'ecart : bonne nouvelle (plus de recettes, moins de
    // depenses) ou mauvaise ; neutre sous 5 %.
    const good = side === 'income' ? row.amount >= (before ?? 0) : row.amount <= (before ?? 0)
    const tone = pct === null || Math.abs(pct) < 5 ? '' : good ? 'reports-good' : 'reports-bad'
    return { ...row, previous: before, pct, tone }
  })
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

export default function Bilan() {
  const [seasons, setSeasons] = useState(null)
  const [seasonId, setSeasonId] = useState(null)
  const [listing, setListing] = useState(null)
  const [filter, setFilter] = useState('all')
  const [error, setError] = useState(null)
  // Bilan ouvert : null, 'new' ou l'id du bilan.
  const [editing, setEditing] = useState(null)

  useEffect(() => {
    api
      .saisons()
      .then((data) => {
        setSeasons(data.seasons)
        setSeasonId(readSeason(data.seasons))
      })
      .catch((err) => setError(err.message))
  }, [])

  const loadReports = useCallback(async () => {
    if (seasonId == null) return
    try {
      setListing(await api.bilans(seasonId))
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [seasonId])

  useEffect(() => {
    loadReports()
  }, [loadReports])

  // Menu ⋯ > « Nouveau bilan ».
  useEffect(() => {
    const open = () => setEditing('new')
    window.addEventListener(NEW_EVENT, open)
    return () => window.removeEventListener(NEW_EVENT, open)
  }, [])

  if (error) return <p className="login-screen__erreur">{error}</p>
  if (!seasons) return <p className="muted">Chargement…</p>
  if (seasons.length === 0) return <p className="muted">Aucune saison : créez-la d’abord dans Admin › École.</p>

  const season = seasons.find((s) => s.id === seasonId)
  const reports = listing?.reports ?? []
  const shown = reports.filter((r) => filter === 'all' || r.state === filter)

  async function remove(report) {
    if (!window.confirm(`Supprimer le bilan « ${report.name} » ?\n\nSon résultat est effacé. Les opérations bancaires ne sont pas touchées.`)) return
    try {
      await api.supprimerBilan(report.id)
      loadReports()
    } catch (err) {
      setError(err.message)
    }
  }

  if (editing !== null && listing && season)
    return (
      <ReportPanel
        key={editing}
        reportId={editing === 'new' ? null : editing}
        season={season}
        options={listing}
        onClose={() => {
          setEditing(null)
          loadReports()
        }}
        onCreated={(id) => setEditing(id)}
      />
    )

  return (
    <section className="fin-bilan reports">
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
          <Icon name="plus" size={18} /> Nouveau bilan
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
            {state === 'all' ? 'Tous' : STATE_LABELS[state]} ({reports.filter((r) => state === 'all' || r.state === state).length})
          </button>
        ))}
      </div>

      {!listing ? (
        <p className="muted">Chargement…</p>
      ) : shown.length === 0 ? (
        <p className="muted">{reports.length === 0 ? `Aucun bilan pour ${season?.name} : commencez un nouveau bilan.` : 'Aucun bilan dans cet état.'}</p>
      ) : (
        <ul className="reports-list">
          {shown.map((r) => (
            // Toute la carte ouvre le bilan.
            <li key={r.id} className="reports-item-open" onClick={() => setEditing(r.id)}>
              <div className="reports-item-main">
                <span className="reports-item-name">{r.name}</span>
                <span className="reports-item-meta">
                  <StateBadge state={r.state} />
                  {r.status === 'running' ? 'calcul en cours…' : r.status === 'error' ? 'dernier calcul en erreur' : r.hasResult ? r.modelLabel : 'pas encore calculé'}
                  {' · '}
                  {enEuros(r.aiCostUsd)}
                  {' · '}
                  {dateHeure(r.updatedAt)}
                </span>
              </div>
              <button
                type="button"
                className="icon-btn icon-btn--danger"
                onClick={(e) => {
                  e.stopPropagation()
                  remove(r)
                }}
                aria-label={`Supprimer ${r.name}`}
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

function StateBadge({ state }) {
  return <span className={`reports-badge reports-badge-${state}`}>{STATE_LABELS[state]}</span>
}

// Panneau d'un bilan : creation (reportId null) ou modification.
function ReportPanel({ reportId, season, options, onClose, onCreated }) {
  const [report, setReport] = useState(null)
  const [form, setForm] = useState({ name: `Bilan ${season.name}`, state: 'brouillon', prompt: '', model: options.defaultModel })
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  const [view, setView] = useState('category')
  // Bilan produit replié par défaut (Seb, 29 octobre) : les documents de l'AG
  // restent visibles dessous ; déplié après « Produire le bilan ».
  const [deplie, setDeplie] = useState(false)

  const load = useCallback(async () => {
    const data = await api.bilan(reportId)
    setReport(data)
    return data
  }, [reportId])

  useEffect(() => {
    if (reportId == null) return
    load()
      .then((data) => setForm({ name: data.name, state: data.state, prompt: data.prompt, model: data.model }))
      .catch((err) => setError(err.message))
  }, [reportId, load])

  // Calcul en cours : relu jusqu'a la fin.
  const running = report?.status === 'running'
  useEffect(() => {
    if (!running) return undefined
    const timer = setInterval(() => {
      load().catch(() => {
        // Coupure passagere : on reessaie au prochain tour.
      })
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [running, load])

  function update(key) {
    return (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))
  }

  // Cree le bilan s'il est nouveau, sinon enregistre ses champs ; retourne son id.
  async function save() {
    if (reportId == null) return (await api.creerBilan({ ...form, seasonId: season.id })).id
    setReport(await api.modifierBilan(reportId, form))
    return reportId
  }

  async function submit(run) {
    setPending(true)
    setError(null)
    setMessage(null)
    try {
      const id = await save()
      if (run) {
        const started = await api.calculerBilan(id, { prompt: form.prompt, model: form.model })
        setDeplie(true)
        if (reportId == null) {
          onCreated(id)
          return
        }
        setReport(started)
      } else if (reportId == null) {
        onCreated(id)
        return
      } else {
        setMessage('Bilan enregistré')
      }
    } catch (err) {
      setError(err.message)
    }
    setPending(false)
  }

  function download(format) {
    telechargerFichier(api.urlTelechargementBilan(reportId, format), `bilan-${season.name}.${format}`).catch((err) => setError(err.message))
  }

  const result = report?.result

  return (
    <section className="fin-bilan reports">
      <div className="reports-panel-header">
        <button type="button" className="btn btn--link nf-retour" onClick={onClose}>
          ← Bilans de {season.name}
        </button>
        <h2>{reportId == null ? 'Nouveau bilan' : form.name}</h2>
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
          Consignes pour l’analyse
          <textarea
            className="field-input"
            rows={3}
            value={form.prompt}
            onChange={update('prompt')}
            placeholder="Ex : mets en avant la hausse des cotisations, ton simple pour l’AG."
          />
          <span className="reports-hint">
            L’appli calcule le tableau au centime ; l’analyse classe les opérations « Autres » et écrit 5 lignes (faits marquants,
            comparaison avec les saisons précédentes).
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
          <b>{enEuros(report?.aiCostUsd ?? 0)}</b>
        </div>
      </div>

      {error && <p className="login-screen__erreur">{error}</p>}
      {message && <p className="muted">{message}</p>}
      {report?.status === 'error' && <p className="login-screen__erreur">{report.error}</p>}

      <div className="reports-actions">
        <button type="button" className="btn btn--secondary" onClick={() => submit(false)} disabled={pending || running}>
          Enregistrer
        </button>
        <button type="button" className="btn btn--primary" onClick={() => submit(true)} disabled={pending || running || !form.name.trim()}>
          {running ? 'Calcul en cours…' : 'Produire le bilan'}
        </button>
      </div>

      <div className="reports-result">
        <div className="reports-result-header">
          <h3>
            <button
              type="button"
              className="reports-result-toggle"
              aria-expanded={deplie || running}
              onClick={() => setDeplie((d) => !d)}
              disabled={!result || running}
            >
              <Icon name={deplie || running ? 'chevronDown' : 'chevronRight'} size={20} /> Résultat
            </button>
          </h3>
          {result && (
            <span className="reports-result-meta">
              {result.modelLabel} · {enEuros(result.costUsd)} · {dateHeure(result.generatedAt)}
            </span>
          )}
          {result && !running && (
            <div className="reports-downloads">
              <button type="button" className="btn btn--secondary" onClick={() => download('xlsx')}>
                <Icon name="download" size={18} /> Excel
              </button>
              <button type="button" className="btn btn--secondary" onClick={() => download('pdf')}>
                <Icon name="download" size={18} /> PDF
              </button>
            </div>
          )}
        </div>

        {running ? (
          <div className="reports-running">
            <div className="reports-progress" />
            <p>Le bilan se calcule… (jusqu’à quelques minutes)</p>
          </div>
        ) : !result ? (
          <p className="muted">Pas encore de résultat : appuyez sur « Produire le bilan ».</p>
        ) : (
          deplie && <ReportResult result={result} view={view} onView={setView} />
        )}
      </div>
      {reportId != null && !running && <DocumentsAG reportId={reportId} seasonName={season.name} />}
    </section>
  )
}

function ReportResult({ result, view, onView }) {
  const v = result.verification
  const unfinished = result.cutoff < result.end
  const known = result.opening != null && result.closing != null
  return (
    <>
      <p className="reports-period">
        Du {dateFr(result.start)} au {dateFr(result.cutoff)}
        {unfinished ? ' (saison en cours, arrêtée au dernier jour connu des comptes)' : ''}. Virements entre les comptes exclus.
      </p>

      <div className={known && v.ok ? 'reports-check' : 'reports-check reports-check-alert'}>
        {known ? (
          <>
            <b>{v.ok ? 'Vérifié' : `Écart de ${euros(v.gap)}`}</b> : {euros(result.opening)} au {dateFr(result.start)} + recettes{' '}
            {euros(result.totalIncome)} − dépenses {euros(result.totalExpense)} = {euros(v.expected)}
            {v.ok ? ', égal au' : ', au lieu du'} solde réel au {dateFr(result.cutoff)} (tous les comptes) : {euros(v.actual)}.
          </>
        ) : (
          <>Vérification impossible : soldes inconnus sur cette période (relevés manquants).</>
        )}
        {result.issues?.length > 0 && <span className="reports-issues">{result.issues.join(' ')}</span>}
      </div>

      <div className="seasons-figures">
        <Figure label="Recettes" value={eurosRound(result.totalIncome)} sub={result.previous && `${result.previous.season} : ${eurosRound(result.previous.totalIncome)}`} />
        <Figure label="Dépenses" value={eurosRound(result.totalExpense)} sub={result.previous && `${result.previous.season} : ${eurosRound(result.previous.totalExpense)}`} />
        <Figure
          label={result.result >= 0 ? 'Excédent' : 'Déficit'}
          value={`${result.result >= 0 ? '+' : '−'}${eurosRound(Math.abs(result.result))}`}
          tone={result.result >= 0 ? 'reports-good' : 'reports-bad'}
          sub={result.previous && `${result.previous.season} : ${result.previous.result >= 0 ? '+' : '−'}${eurosRound(Math.abs(result.previous.result))}`}
        />
        <Figure label="Solde fin (tous les comptes)" value={eurosRound(result.closing)} sub={`début ${eurosRound(result.opening)}`} />
      </div>

      <h4 className="reports-subtitle">Analyse</h4>
      <ol className="reports-analysis">
        {result.analysis.map((line, i) => (
          <li key={i}>{line}</li>
        ))}
      </ol>

      <div className="filter-chips" role="group" aria-label="Présentation du tableau">
        {[
          ['category', 'Par catégorie'],
          ['month', 'Par mois'],
        ].map(([id, label]) => (
          <button key={id} type="button" className={id === view ? 'filter-chip filter-chip-active' : 'filter-chip'} aria-pressed={id === view} onClick={() => onView(id)}>
            {label}
          </button>
        ))}
      </div>

      {view === 'category' ? <CategoryTables result={result} /> : <MonthTable result={result} />}
    </>
  )
}

function Figure({ label, value, sub, tone = '' }) {
  return (
    <div className="seasons-figure">
      <span className="seasons-figure-label">{label}</span>
      <span className={`seasons-figure-value ${tone}`}>{value}</span>
      {sub && <span className="seasons-figure-sub">{sub}</span>}
    </div>
  )
}

function CategoryTables({ result }) {
  const classified = new Set(Object.values(result.classifications ?? {}))
  const previousName = result.previous?.season
  return (
    <div className="reports-categories">
      {[
        ['income', 'Recettes', result.totalIncome],
        ['expense', 'Dépenses', result.totalExpense],
      ].map(([side, title, total]) => (
        <table key={side} className="reports-table">
          <thead>
            <tr>
              <th>{title}</th>
              <th>{result.seasonName}</th>
              {previousName && <th className="reports-wide-col">{previousName}</th>}
              {previousName && <th>Écart</th>}
            </tr>
          </thead>
          <tbody>
            {comparison(result, side).map((row) => (
              <tr key={row.category}>
                <td>
                  {row.category}
                  {classified.has(row.category) && <span className="reports-ai-badge">classé automatiquement</span>}
                  {previousName && <span className="reports-narrow-prev">{previousName} : {eurosRound(row.previous)}</span>}
                </td>
                <td>{eurosRound(row.amount)}</td>
                {previousName && <td className="reports-wide-col">{eurosRound(row.previous)}</td>}
                {previousName && <td className={row.tone}>{row.pct === null ? 'nouveau' : `${row.pct > 0 ? '+' : ''}${row.pct} %`}</td>}
              </tr>
            ))}
            <tr className="reports-total">
              <td>Total</td>
              <td>{eurosRound(total)}</td>
              {previousName && <td className="reports-wide-col">{eurosRound(side === 'income' ? result.previous.totalIncome : result.previous.totalExpense)}</td>}
              {previousName && <td />}
            </tr>
          </tbody>
        </table>
      ))}
    </div>
  )
}

function MonthTable({ result }) {
  const categories = result.categories
  const totals = categories.map((c) => result.months.reduce((sum, m) => sum + (m.amounts[c] ?? 0), 0))
  return (
    <>
      <p className="reports-month-title">Compte d’exploitation {result.seasonName}, établi suivant les relevés de banque</p>
      <div className="reports-scroll">
        <table className="reports-table reports-month-table">
          <thead>
            <tr>
              <th>Mois</th>
              <th>Solde au 1er</th>
              {categories.map((c) => (
                <th key={c}>{c}</th>
              ))}
              <th>Solde fin de mois</th>
            </tr>
          </thead>
          <tbody>
            {result.months.map((m) => (
              <tr key={m.month}>
                <td>{monthLabel(m.month)}</td>
                <td>{amount(m.opening)}</td>
                {categories.map((c) => (
                  <td key={c}>{amount(m.amounts[c])}</td>
                ))}
                <td>{amount(m.closing)}</td>
              </tr>
            ))}
            <tr className="reports-total">
              <td>Vérif</td>
              <td>{amount(result.opening)}</td>
              {totals.map((t, i) => (
                <td key={categories[i]}>{amount(t)}</td>
              ))}
              <td>{amount(result.verification.expected)}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  )
}
