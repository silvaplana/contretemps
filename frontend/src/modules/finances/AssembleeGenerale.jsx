// Sous-module Assemblée générale (spec/modules/financier.md §5), repris de
// Sambo Admin (GeneralAssemblies.jsx) : base du PowerPoint de l'AG d'une
// saison (voir backend/src/finances/assemblies.py). Même écran que Bilan
// (liste par saison, états, panneau consignes / modèle / coût) ; chaque AG
// garde 3 PowerPoint (voir KINDS) : le modèle choisi (fichier de
// l'ordinateur ou PowerPoint d'une autre AG), celui produit par le calcul et
// celui retouché par le trésorier. « Produire le PowerPoint » écrit les
// diapos du trésorier à partir du bilan de la saison, en arrière-plan :
// l'écran relit l'AG jusqu'à la fin.
import { useCallback, useEffect, useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { enEuros } from '../../utils/euros.js'
import { telechargerFichier } from '../../utils/telechargement.js'
import * as api from './api.js'
import './finances.css'

const POLL_MS = 2000
const STATE_LABELS = { brouillon: 'Brouillon', valide: 'Validé', officiel: 'Officiel' }
// Les 3 PowerPoint d'une AG (voir backend assemblies.py), dans l'ordre d'affichage.
const KINDS = [
  { id: 'modele', label: 'Modèle' },
  { id: 'genere', label: 'Produit' },
  { id: 'modifie', label: 'Modifié' },
]
const SEASON_KEY = 'finances-ag-saison'
const NEW_EVENT = 'finances-new-assembly'
const TEMPLATE_EVENT = 'finances-general-template'
const PPTX_ACCEPT = '.pptx,application/vnd.openxmlformats-officedocument.presentationml.presentation'

// Entrées du menu ⋯ (voir Financier.jsx).
export function requestNewAssembly() {
  window.dispatchEvent(new Event(NEW_EVENT))
}
export function requestGeneralTemplate() {
  window.dispatchEvent(new Event(TEMPLATE_EVENT))
}

const { dateFr } = api
const dateHeure = (iso) => dateFr(iso.slice(0, 10))
const timeFr = (iso) => new Date(iso).toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' })

function readSeason(seasons) {
  try {
    const id = Number(localStorage.getItem(SEASON_KEY))
    if (seasons.some((s) => s.id === id)) return id
  } catch {
    // Stockage indisponible : la saison en cours.
  }
  return (seasons.find((s) => s.current) ?? seasons[seasons.length - 1])?.id ?? null
}

// Bouton qui ouvre le choix d'un fichier .pptx.
function PptxButton({ label, onFile, disabled, className = 'btn btn--secondary', icon = 'paperclip' }) {
  const input = useRef(null)
  return (
    <>
      <button type="button" className={className} onClick={() => input.current.click()} disabled={disabled}>
        <Icon name={icon} size={18} /> {label}
      </button>
      <input
        ref={input}
        type="file"
        accept={PPTX_ACCEPT}
        hidden
        onChange={(e) => {
          const file = e.target.files[0]
          e.target.value = ''
          if (file) onFile(file)
        }}
      />
    </>
  )
}

export default function AssembleeGenerale() {
  const [seasons, setSeasons] = useState(null)
  const [seasonId, setSeasonId] = useState(null)
  const [listing, setListing] = useState(null)
  const [filter, setFilter] = useState('all')
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  // AG ouverte : null, 'new' ou l'id de l'AG.
  const [editing, setEditing] = useState(null)
  const templateInput = useRef(null)

  useEffect(() => {
    api
      .saisons()
      .then((data) => {
        setSeasons(data.seasons)
        setSeasonId(readSeason(data.seasons))
      })
      .catch((err) => setError(err.message))
  }, [])

  const load = useCallback(async () => {
    if (seasonId == null) return
    try {
      setListing(await api.assemblees(seasonId))
      setError(null)
    } catch (err) {
      setError(err.message)
    }
  }, [seasonId])

  useEffect(() => {
    load()
  }, [load])

  // Menu ⋯ : « Nouvelle AG », « Modèle général… ».
  useEffect(() => {
    const open = () => setEditing('new')
    const template = () => templateInput.current?.click()
    window.addEventListener(NEW_EVENT, open)
    window.addEventListener(TEMPLATE_EVENT, template)
    return () => {
      window.removeEventListener(NEW_EVENT, open)
      window.removeEventListener(TEMPLATE_EVENT, template)
    }
  }, [])

  async function uploadTemplate(file) {
    setMessage(null)
    try {
      await api.envoyerModeleGeneral(file)
      setMessage('Modèle général enregistré : il sert aux AG sans modèle.')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (error) return <p className="login-screen__erreur">{error}</p>
  if (!seasons) return <p className="muted">Chargement…</p>
  if (seasons.length === 0) return <p className="muted">Aucune saison : créez-la d’abord dans Admin › École.</p>

  const season = seasons.find((s) => s.id === seasonId)
  const assemblies = listing?.assemblies ?? []
  const shown = assemblies.filter((a) => filter === 'all' || a.state === filter)

  async function remove(assembly) {
    if (!window.confirm(`Supprimer « ${assembly.name} » ?\n\nSes PowerPoint sont effacés. Le bilan n'est pas touché.`)) return
    try {
      await api.supprimerAssemblee(assembly.id)
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (editing !== null && listing && season)
    return (
      <AssemblyPanel
        key={editing}
        assemblyId={editing === 'new' ? null : editing}
        season={season}
        options={listing}
        onClose={() => {
          setEditing(null)
          load()
        }}
        onCreated={(id) => setEditing(id)}
      />
    )

  return (
    <section className="fin-bilan fin-ag reports">
      <input
        ref={templateInput}
        type="file"
        accept={PPTX_ACCEPT}
        hidden
        onChange={(e) => {
          const file = e.target.files[0]
          e.target.value = ''
          if (file) uploadTemplate(file)
        }}
      />
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
          <Icon name="plus" size={18} /> Nouvelle AG
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
            {state === 'all' ? 'Tous' : STATE_LABELS[state]} ({assemblies.filter((a) => state === 'all' || a.state === state).length})
          </button>
        ))}
      </div>

      {message && <p className="muted">{message}</p>}
      {listing && !listing.report && (
        <p className="muted">Pas encore de bilan calculé pour {season?.name} : produisez-le d’abord dans Bilan.</p>
      )}

      {!listing ? (
        <p className="muted">Chargement…</p>
      ) : shown.length === 0 ? (
        <p className="muted">{assemblies.length === 0 ? `Aucune AG pour ${season?.name} : commencez une nouvelle AG.` : 'Aucune AG dans cet état.'}</p>
      ) : (
        <ul className="reports-list">
          {shown.map((a) => (
            // Toute la carte ouvre l'AG.
            <li key={a.id} className="reports-item-open" onClick={() => setEditing(a.id)}>
              <div className="reports-item-main">
                <span className="reports-item-name">{a.name}</span>
                <span className="reports-item-meta">
                  <span className={`reports-badge reports-badge-${a.state}`}>{STATE_LABELS[a.state]}</span>
                  {a.status === 'running'
                    ? 'préparation en cours…'
                    : a.status === 'error'
                      ? 'dernier calcul en erreur'
                      : a.hasPpt
                        ? `PowerPoint prêt · ${a.modelLabel}`
                        : 'pas encore produit'}
                  {' · '}
                  {enEuros(a.aiCostUsd)}
                  {' · '}
                  {dateHeure(a.updatedAt)}
                </span>
              </div>
              <button
                type="button"
                className="icon-btn icon-btn--danger"
                onClick={(e) => {
                  e.stopPropagation()
                  remove(a)
                }}
                aria-label={`Supprimer ${a.name}`}
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

// Panneau d'une AG : création (assemblyId null) ou modification.
function AssemblyPanel({ assemblyId, season, options, onClose, onCreated }) {
  const [assembly, setAssembly] = useState(null)
  const [form, setForm] = useState({ name: `AG ${season.name}`, state: 'brouillon', prompt: '', model: options.defaultModel })
  const [pending, setPending] = useState(false)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState(null)
  // PowerPoint affiché dans le résultat : une sorte de KINDS (null : le plus abouti).
  const [kind, setKind] = useState(null)
  // PowerPoint des autres AG utilisables comme modèle.
  const [sources, setSources] = useState([])

  const load = useCallback(async () => {
    const data = await api.assemblee(assemblyId)
    setAssembly(data)
    return data
  }, [assemblyId])

  useEffect(() => {
    if (assemblyId == null) return
    load()
      .then((data) => setForm({ name: data.name, state: data.state, prompt: data.prompt, model: data.model }))
      .catch((err) => setError(err.message))
  }, [assemblyId, load])

  useEffect(() => {
    api
      .sourcesDeModele(assemblyId)
      .then(setSources)
      .catch(() => {
        // Liste indisponible : le modèle peut toujours être envoyé en fichier.
      })
  }, [assemblyId])

  const running = assembly?.status === 'running'
  useEffect(() => {
    if (!running) return undefined
    const timer = setInterval(() => {
      load()
        .then((data) => {
          if (data.status === 'idle') setKind('genere')
        })
        .catch(() => {
          // Coupure passagère : on réessaie au prochain tour.
        })
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [running, load])

  function update(key) {
    return (e) => setForm((prev) => ({ ...prev, [key]: e.target.value }))
  }

  // Crée l'AG si elle est nouvelle, sinon enregistre ses champs ; retourne son id.
  async function save() {
    if (assemblyId == null) return (await api.creerAssemblee({ ...form, seasonId: season.id })).id
    setAssembly(await api.modifierAssemblee(assemblyId, form))
    return assemblyId
  }

  async function submit(run) {
    setPending(true)
    setError(null)
    setMessage(null)
    try {
      const id = await save()
      if (run) {
        const started = await api.produireAssemblee(id, { prompt: form.prompt, model: form.model })
        if (assemblyId == null) {
          onCreated(id)
          return
        }
        setAssembly(started)
      } else if (assemblyId == null) {
        onCreated(id)
        return
      } else {
        setMessage('AG enregistrée')
      }
    } catch (err) {
      setError(err.message)
    }
    setPending(false)
  }

  const files = assembly?.files ?? {}
  const shownKind = files[kind] ? kind : ['modifie', 'genere', 'modele'].find((k) => files[k])
  const shownFile = files[shownKind]

  function download() {
    const nom = shownFile.filename.replace(/[\\/:*?"<>|]/g, '-')
    telechargerFichier(api.urlTelechargementAssemblee(assemblyId, shownKind), nom).catch((err) => setError(err.message))
  }

  async function uploadModified(file) {
    setError(null)
    try {
      setAssembly(await api.envoyerPptModifie(assemblyId, file))
      setKind('modifie')
      setMessage('PowerPoint modifié enregistré')
    } catch (err) {
      setError(err.message)
    }
  }

  // Choix du PowerPoint modèle : send(id) l'enregistre pour l'AG id. Une
  // nouvelle AG est d'abord créée (il lui faut un identifiant).
  async function chooseModel(send) {
    setPending(true)
    setError(null)
    try {
      const id = await save()
      const updated = await send(id)
      if (assemblyId == null) {
        onCreated(id)
        return
      }
      setAssembly(updated)
      setKind('modele')
      setMessage('PowerPoint modèle enregistré')
    } catch (err) {
      setError(err.message)
    }
    setPending(false)
  }

  const uploadModel = (file) => chooseModel((id) => api.envoyerPptModele(id, file))

  function copyModel(value) {
    const source = sources.find((x) => `${x.assemblyId}:${x.kind}` === value)
    if (source) chooseModel((id) => api.copierPptModele(id, source.assemblyId, source.kind))
  }

  const result = assembly?.result
  const locked = pending || running

  return (
    <section className="fin-bilan fin-ag reports">
      <div className="reports-panel-header">
        <button type="button" className="btn btn--link nf-retour" onClick={onClose}>
          ← AG de {season.name}
        </button>
        <h2>{assemblyId == null ? 'Nouvelle AG' : form.name}</h2>
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

        <div className="reports-form-wide ag-model">
          <span className="ag-model-label">PowerPoint modèle</span>
          <b>
            {files.modele
              ? files.modele.filename
              : options.template
                ? `Pas encore choisi. Par défaut : ${options.template.name}`
                : 'Aucun pour l’instant'}
          </b>
          {files.modele?.source && <span className="ag-model-source">{files.modele.source}</span>}
          <div className="ag-model-actions">
            <PptxButton label="Choisir un fichier" onFile={uploadModel} disabled={locked || !form.name.trim()} />
            <select
              className="field-input"
              aria-label="Prendre le PowerPoint d’une autre AG"
              value=""
              onChange={(e) => copyModel(e.target.value)}
              disabled={locked || !form.name.trim() || sources.length === 0}
            >
              <option value="">{sources.length === 0 ? 'Aucun PowerPoint dans les autres AG' : 'Prendre le PowerPoint d’une autre AG…'}</option>
              {sources.map((x) => (
                <option key={`${x.assemblyId}:${x.kind}`} value={`${x.assemblyId}:${x.kind}`}>
                  {x.label}
                </option>
              ))}
            </select>
          </div>
          <span className="reports-hint">
            L’exemple dont on reprend la mise en page : un fichier de votre ordinateur, ou un PowerPoint déjà enregistré dans une
            autre AG. Il est copié dans cette AG.
          </span>
        </div>

        <label className="reports-form-wide">
          Consignes
          <textarea
            className="field-input"
            rows={3}
            value={form.prompt}
            onChange={update('prompt')}
            placeholder="Ex : la cotisation reste à 300 €, l’AG a lieu le 04/07, mets en avant la hausse des inscrits."
          />
          <span className="reports-hint">
            S’ajoutent aux consignes fixes : partir du PowerPoint modèle, garder sa mise en page, écrire les diapos du trésorier
            avec les chiffres du bilan, mettre les années à jour et marquer « À compléter » ce qui n’est pas connu.
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
          <b>{enEuros(assembly?.aiCostUsd ?? 0)}</b>
        </div>
      </div>

      {error && <p className="login-screen__erreur">{error}</p>}
      {message && <p className="muted">{message}</p>}
      {assembly?.status === 'error' && <p className="login-screen__erreur">{assembly.error}</p>}

      <div className="reports-actions">
        <button type="button" className="btn btn--secondary" onClick={() => submit(false)} disabled={locked}>
          Enregistrer
        </button>
        <button type="button" className="btn btn--primary" onClick={() => submit(true)} disabled={locked || !form.name.trim()}>
          {running ? 'Préparation en cours…' : 'Produire le PowerPoint'}
        </button>
      </div>

      <div className="reports-result">
        <div className="reports-result-header">
          <h3>Résultat</h3>
          {result && (
            <span className="reports-result-meta">
              {result.modelLabel} · {enEuros(result.costUsd)} · {dateHeure(result.generatedAt)}
            </span>
          )}
          <div className="reports-downloads">
            <PptxButton label="Importer le PowerPoint modifié" onFile={uploadModified} disabled={assemblyId == null || running} />
          </div>
        </div>

        {running ? (
          <div className="reports-running">
            <div className="reports-progress" />
            <p>Le PowerPoint se prépare… (jusqu’à quelques minutes)</p>
          </div>
        ) : !shownFile ? (
          <p className="muted">Pas encore de PowerPoint : choisissez un PowerPoint modèle, puis appuyez sur « Produire le PowerPoint ».</p>
        ) : (
          <>
            <div className="filter-chips" role="group" aria-label="PowerPoint affiché">
              {KINDS.map((k) => (
                <button
                  key={k.id}
                  type="button"
                  className={k.id === shownKind ? 'filter-chip filter-chip-active' : 'filter-chip'}
                  aria-pressed={k.id === shownKind}
                  disabled={!files[k.id]}
                  title={files[k.id] ? files[k.id].filename : 'Pas encore de PowerPoint de cette sorte'}
                  onClick={() => setKind(k.id)}
                >
                  {k.label}
                </button>
              ))}
            </div>
            <div className="ag-shown-file">
              <span className="reports-period">
                {shownFile.filename}, enregistré le {dateHeure(shownFile.createdAt)} à {timeFr(shownFile.createdAt)}.
                {shownFile.source && ` ${shownFile.source}.`}
              </span>
              <button type="button" className="btn btn--secondary" onClick={download}>
                <Icon name="download" size={18} /> Télécharger
              </button>
            </div>
            {result && shownKind === 'genere' && <RunDetails result={result} />}
            <SlidesPreview
              key={`${shownKind}-${shownFile.createdAt}`}
              assemblyId={assemblyId}
              kind={shownKind}
              changed={result && shownKind === 'genere' ? result.changedSlides : []}
            />
          </>
        )}
      </div>
    </section>
  )
}

function RunDetails({ result }) {
  return (
    <div className="ag-details">
      <p className="reports-period">
        À partir de « {result.report.name} » ({STATE_LABELS[result.report.state].toLowerCase()}) et de : {result.template.name}.
      </p>
      {result.warnings.length > 0 && (
        <div className="reports-check reports-check-alert">
          <b>Montants à vérifier</b>
          <ul className="ag-warnings">
            {result.warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </div>
      )}
      {result.summary.length > 0 && (
        <ul className="ag-summary">
          {result.summary.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

// Image d'une diapo (route protégée : chargée avec la session, que
// api/identite.js ajoute à fetch).
function useImage(url) {
  const [src, setSrc] = useState(null)
  useEffect(() => {
    if (!url) return undefined
    let objectUrl = null
    let cancelled = false
    fetch(url)
      .then((r) => (r.ok ? r.blob() : null))
      .then((blob) => {
        if (blob && !cancelled) {
          objectUrl = URL.createObjectURL(blob)
          setSrc(objectUrl)
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
      if (objectUrl) URL.revokeObjectURL(objectUrl)
    }
  }, [url])
  return src
}

function SlideText({ slide }) {
  return (
    <div className="ag-slide-text">
      <span className="ag-slide-title">{slide.title || `Diapo ${slide.number}`}</span>
      <ul>
        {slide.lines.map((line, i) => (
          <li key={i} style={{ marginLeft: `${line.level * 0.8}em` }}>
            {line.text.split('À compléter').map((part, j) => (
              <span key={j}>
                {j > 0 && <mark>À compléter</mark>}
                {part}
              </span>
            ))}
          </li>
        ))}
      </ul>
    </div>
  )
}

function SlideView({ assemblyId, kind, slide }) {
  const src = useImage(slide.image ? api.urlDiapo(assemblyId, kind, slide.image) : null)
  if (slide.image && src) return <img src={src} alt={`Diapo ${slide.number} : ${slide.title}`} />
  return <SlideText slide={slide} />
}

function SlidesPreview({ assemblyId, kind, changed }) {
  const [preview, setPreview] = useState(null)
  const [error, setError] = useState(null)
  const [open, setOpen] = useState(null)

  useEffect(() => {
    api
      .diapos(assemblyId, kind)
      .then(setPreview)
      .catch((err) => setError(err.message))
  }, [assemblyId, kind])

  useEffect(() => {
    if (open === null) return undefined
    function onKey(e) {
      if (e.key === 'Escape') setOpen(null)
      if (e.key === 'ArrowRight') setOpen((i) => Math.min(i + 1, preview.slides.length - 1))
      if (e.key === 'ArrowLeft') setOpen((i) => Math.max(i - 1, 0))
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, preview])

  if (error) return <p className="login-screen__erreur">{error}</p>
  if (!preview) return <p className="muted">Préparation de l’aperçu des diapos…</p>
  const changedSet = new Set(changed)
  const current = open === null ? null : preview.slides[open]

  return (
    <>
      {!preview.thumbnails && <p className="reports-hint">Images des diapos indisponibles sur le serveur : aperçu du texte.</p>}
      <div className="ag-slides">
        {preview.slides.map((slide, i) => (
          <button
            key={slide.number}
            type="button"
            className={slide.hidden ? 'ag-thumb ag-thumb-hidden' : 'ag-thumb'}
            onClick={() => setOpen(i)}
            aria-label={`Diapo ${slide.number} : ${slide.title}`}
          >
            <div className="ag-thumb-stage">
              <SlideView assemblyId={assemblyId} kind={kind} slide={slide} />
            </div>
            <span className="ag-thumb-caption">
              <span className="ag-thumb-number">{slide.number}</span>
              <span className="ag-thumb-title">{slide.title || '—'}</span>
              {changedSet.has(slide.number) && <span className="ag-written-dot" title="Diapo écrite par le calcul" />}
              {slide.hidden && <span className="ag-thumb-tag">masquée</span>}
            </span>
          </button>
        ))}
      </div>
      {changedSet.size > 0 && (
        <p className="reports-hint">
          <span className="ag-written-dot" /> diapo écrite automatiquement ; <mark>À compléter</mark> : à remplir par vous.
        </p>
      )}

      {current && (
        <div className="ag-viewer" role="dialog" aria-modal="true" aria-label={`Diapo ${current.number}`} onClick={(e) => e.target === e.currentTarget && setOpen(null)}>
          <div className="ag-viewer-box">
            <div className="ag-viewer-stage">
              <SlideView assemblyId={assemblyId} kind={kind} slide={current} />
            </div>
            <div className="ag-viewer-footer">
              <span>
                {current.number} / {preview.slides.length}
                {changedSet.has(current.number) ? ' · écrite automatiquement' : ''}
              </span>
              <span className="reports-downloads">
                <button type="button" className="btn btn--secondary" onClick={() => setOpen(Math.max(open - 1, 0))} disabled={open === 0}>
                  Précédente
                </button>
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => setOpen(Math.min(open + 1, preview.slides.length - 1))}
                  disabled={open === preview.slides.length - 1}
                >
                  Suivante
                </button>
                <button type="button" className="btn btn--primary" onClick={() => setOpen(null)}>
                  Fermer
                </button>
              </span>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
