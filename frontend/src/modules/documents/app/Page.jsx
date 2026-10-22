import { useEffect, useRef, useState } from 'react'
import { BLOCKS, MEMBER_FIELDS, euros, label, options, texteBrut } from './blocks.js'
import { debutTrait, finTrait, pointsDe, suiteTrait } from './trait.js'

// Le formulaire d'entrée tel que le reçoivent les gens (Aperçu, et plus tard
// la page publique), dessiné depuis le JSON : jamais de HTML stocké, le
// texte passe par React (fichier-de-base.md §6).

const STYLES = { bold: 'strong', italic: 'em', underline: 'u', strike: 's', code: 'code' }

export function Inline({ content }) {
  if (typeof content === 'string') return content
  return (content ?? []).map((m, i) => {
    if (m.type === 'link') {
      const sur = /^(https?:|mailto:)/.test(m.href ?? '')
      return sur ? (
        <a key={i} href={m.href} target="_blank" rel="noopener noreferrer">
          <Inline content={m.content} />
        </a>
      ) : (
        <Inline key={i} content={m.content} />
      )
    }
    let el = m.text
    for (const [style, balise] of Object.entries(STYLES)) {
      if (m.styles?.[style]) {
        const B = balise
        el = <B>{el}</B>
      }
    }
    return <span key={i}>{el}</span>
  })
}

// Blocs de texte qu'on peut corriger dans l'Aperçu (pas ceux qui ont un lien).
const TEXTES = ['heading', 'paragraph', 'quote', 'bulletListItem', 'numberedListItem', 'checkListItem']

// Un texte de l'Aperçu modifiable : on le touche et on écrit ; enregistré en
// quittant le texte (Entrée aussi). La clé suit le texte : React repart du
// nouveau contenu au lieu de se battre avec ce qui a été tapé.
function Modifiable({ as: Balise, block, onTexte, className, children }) {
  return (
    <Balise
      className={`${className ?? ''} ap-modifiable`}
      contentEditable
      suppressContentEditableWarning
      spellCheck
      onKeyDown={(e) => {
        if (e.key === 'Enter') {
          e.preventDefault()
          e.currentTarget.blur()
        }
      }}
      onBlur={(e) => {
        const texte = e.currentTarget.innerText.replace(/\s+/g, ' ').trim()
        if (texte !== texteBrut(block.content).replace(/\s+/g, ' ').trim()) onTexte(block.id, texte)
      }}
    >
      {children}
    </Balise>
  )
}

function Layout({ block, index, onTexte }) {
  const modifiable = onTexte && TEXTES.includes(block.type) && !(block.content ?? []).some?.((m) => m.type === 'link')
  const c = modifiable ? (
    <Modifiable key={texteBrut(block.content)} as="span" block={block} onTexte={onTexte}>
      <Inline content={block.content} />
    </Modifiable>
  ) : (
    <Inline content={block.content} />
  )
  switch (block.type) {
    case 'heading': {
      const H = `h${Math.min(Math.max(block.props?.level ?? 1, 1), 3) + 1}`
      return <H className="ap-h">{c}</H>
    }
    case 'quote':
      return <blockquote className="ap-quote">{c}</blockquote>
    case 'bulletListItem':
      return <div className="ap-li"><span aria-hidden="true">•</span><div>{c}</div></div>
    case 'numberedListItem':
      return <div className="ap-li"><span aria-hidden="true">{index}.</span><div>{c}</div></div>
    case 'checkListItem':
      return <div className="ap-li"><span aria-hidden="true">{block.props?.checked ? '☑' : '☐'}</span><div>{c}</div></div>
    case 'divider':
      return <hr className="ap-hr" />
    default:
      return <p className="ap-p">{c}</p>
  }
}

function Signature({ value, onChange, disabled }) {
  const toile = useRef(null)
  const trace = useRef(false)

  useEffect(() => {
    const c = toile.current
    const ctx = c.getContext('2d')
    ctx.lineWidth = 5
    ctx.lineCap = 'round'
    ctx.strokeStyle = '#3a2410'
    if (!value) ctx.clearRect(0, 0, c.width, c.height)
  }, [value])

  const point = (e) => {
    const r = toile.current.getBoundingClientRect()
    return [((e.clientX - r.left) * toile.current.width) / r.width, ((e.clientY - r.top) * toile.current.height) / r.height]
  }
  return (
    <div className="ap-sig">
      <canvas
        ref={toile}
        // Deux fois la taille affichée : un trait net à l'écran et dans le PDF.
        width={1200}
        height={360}
        aria-label="Zone de signature"
        onPointerDown={(e) => {
          if (disabled) return
          e.currentTarget.setPointerCapture(e.pointerId)
          trace.current = debutTrait(point(e))
        }}
        onPointerMove={(e) => {
          if (!trace.current) return
          const ctx = toile.current.getContext('2d')
          for (const p of pointsDe(e)) suiteTrait(ctx, trace.current, point(p))
        }}
        onPointerUp={() => {
          if (!trace.current) return
          finTrait(toile.current.getContext('2d'), trace.current)
          trace.current = false
          onChange(toile.current.toDataURL('image/png'))
        }}
      />
      {!value && <span className="ap-sig__hint">Signez ici avec le doigt</span>}
      {value && !disabled && (
        <button type="button" className="ap-link" onClick={() => onChange(null)}>
          Effacer la signature
        </button>
      )}
    </div>
  )
}

const sansAccents = (t) => String(t ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
const leJour = (iso) => {
  const d = new Date(iso)
  return `${d.getDate()}${d.getDate() === 1 ? 'er' : ''} ${MOIS[d.getMonth()]} ${d.getFullYear()}`
}

// Présence et procuration (spec procurations.md §1.1 et §3) : trois choix ;
// pour une procuration, qui me représente (recherche + liste), le texte du
// pouvoir rempli par l'appli, la signature au doigt. `ctx` vient du serveur
// (lien personnel) : les adhérents, ceux qui ont déjà assez de pouvoirs. Un nom
// absent de la liste s'écrit à la main (Seb, 21 octobre) ; pas de pouvoir en blanc.
function Assembly({ block, value, onChange, disabled, ctx }) {
  const [cherche, setCherche] = useState('')
  const v = value ?? {}
  const p = block.props ?? {}
  const gens = ctx?.candidates ?? []
  const choisir = (answer) =>
    onChange(answer === 'proxy' ? { answer, proxy_to: v.proxy_to, proxy_name: v.proxy_name, signature: v.signature } : { answer })
  const nom = v.proxy_to === 'blank' ? null : gens.find((g) => g.id === v.proxy_to)?.name ?? v.proxy_name
  const sorte = (ctx?.kind ?? p.kind) === 'extraordinary' ? 'extraordinaire' : 'ordinaire'
  const debut = ctx?.starts_at ?? p.startsAt
  const qui =
    v.proxy_to === 'blank'
      ? `la personne désignée par le bureau${ctx?.blank_to || p.blankTo ? ` (à défaut, ${ctx?.blank_to || p.blankTo})` : ''}`
      : nom
  const filtre = sansAccents(cherche.trim())
  const liste = filtre ? gens.filter((g) => sansAccents(g.name).includes(filtre)) : gens
  const libre = cherche.trim().replace(/\s+/g, ' ')
  const exact = gens.some((g) => sansAccents(g.name) === sansAccents(libre))
  const ferme = disabled || ctx?.closed
  return (
    <fieldset className="ap-field ap-ag" disabled={ferme}>
      <legend className="ap-q">{label(block)}</legend>
      {ctx?.closed && <p className="ap-ag__note">L’assemblée a commencé : la réponse ne peut plus changer.</p>}
      {ctx?.received > 0 && (
        <p className="ap-ag__note">
          Vous avez reçu {ctx.received} pouvoir{ctx.received > 1 ? 's' : ''} : venez à l’assemblée pour voter pour eux.
        </p>
      )}
      <div className="ap-ag__choix">
        {[['attend', 'Je viens'], ['proxy', 'Je donne procuration'], ['absent', 'Je ne viens pas']].map(([c, t]) => (
          <button
            key={c}
            type="button"
            className={`ap-ag__btn${v.answer === c ? ' ap-ag__btn--on' : ''}`}
            aria-pressed={v.answer === c}
            onClick={() => choisir(c)}
          >
            {t}
          </button>
        ))}
      </div>
      {v.answer === 'proxy' && (
        <>
          <p className="ap-q">Qui vous représente ?</p>
          <input
            className="ap-input"
            type="search"
            placeholder="Nom de la personne"
            aria-label="Nom de la personne"
            value={cherche}
            onChange={(e) => setCherche(e.target.value)}
          />
          <div className="ap-ag__liste" role="radiogroup" aria-label="Membres">
            {v.proxy_to === 'other' && v.proxy_name && !libre && (
              <label className="ap-choice">
                <input type="radio" name={`ag-${block.id}`} checked readOnly />
                <span>{v.proxy_name}</span>
              </label>
            )}
            {liste.map((g) => (
              <label key={g.id} className={`ap-choice${g.full ? ' ap-choice--off' : ''}`}>
                <input
                  type="radio"
                  name={`ag-${block.id}`}
                  disabled={g.full}
                  checked={v.proxy_to === g.id}
                  onChange={() => onChange({ ...v, proxy_to: g.id })}
                />
                <span>
                  {g.name}
                  {g.full && <small> · {g.why}</small>}
                </span>
              </label>
            ))}
            {libre && !exact && (
              <label className="ap-choice">
                <input
                  type="radio"
                  name={`ag-${block.id}`}
                  checked={v.proxy_to === 'other' && v.proxy_name === libre}
                  onChange={() => onChange({ ...v, proxy_to: 'other', proxy_name: libre })}
                />
                <span>{liste.length ? `Une autre personne : ${libre}` : libre}</span>
              </label>
            )}
            {!gens.length && !libre && <p className="ap-ag__note">La liste des membres s’affiche dans le lien reçu par email ; vous pouvez aussi écrire un nom.</p>}
          </div>
          {v.proxy_to != null && (
            <>
              <p className="ap-ag__pouvoir">
                Je soussigné(e) {ctx?.person ?? '…'}, membre de {ctx?.org_name || 'l’association'}, donne pouvoir à {qui} pour me
                représenter à l’assemblée générale {sorte}
                {debut ? ` du ${leJour(debut)}` : ''} et prendre part aux votes en mon nom.
              </p>
              <Signature value={v.signature} onChange={(signature) => onChange({ ...v, signature })} disabled={ferme} />
            </>
          )}
        </>
      )}
    </fieldset>
  )
}

// Document à signer (signature-documents.md §3) : où iront les signatures,
// ajoutées à la fin du document, une case par signataire.
export function SignZone({ block }) {
  const p = block.props ?? {}
  return (
    <div className="ap-field sg-zone">
      <b>Signatures</b>
      <span>
        Une case par signataire, ajoutée à la fin du document
        {p.mode === 'initials' ? ', et un paraphe en bas de chaque page' : ''}.
      </span>
      {p.mention && <span>Écrit au-dessus de chaque signature : « {p.mention} ».</span>}
    </div>
  )
}

function Question({ block, value, onChange, disabled, ctx }) {
  const p = block.props ?? {}
  const id = `ap-${block.id}`
  const titre = (
    <label className="ap-q" htmlFor={block.type === 'choice' || block.type === 'member' ? undefined : id}>
      {label(block)}
      {p.required && block.type !== 'payment' && <span className="ap-req" aria-label="obligatoire"> *</span>}
    </label>
  )
  if (block.type === 'choice') {
    const multiple = Boolean(p.multiple)
    const choisis = multiple ? (value ?? []) : value
    return (
      <fieldset className="ap-field" disabled={disabled}>
        <legend className="ap-q">{label(block)}{p.required && <span className="ap-req"> *</span>}</legend>
        {options(block).map((o, i) => (
          <label key={i} className="ap-choice">
            <input
              type={multiple ? 'checkbox' : 'radio'}
              name={id}
              checked={multiple ? choisis.includes(o) : choisis === o}
              onChange={() => onChange(multiple ? (choisis.includes(o) ? choisis.filter((x) => x !== o) : [...choisis, o]) : o)}
            />
            <span>{o}</span>
          </label>
        ))}
      </fieldset>
    )
  }
  if (block.type === 'member') {
    const v = value ?? {}
    return (
      <fieldset className="ap-field" disabled={disabled}>
        <legend className="ap-q">{label(block)}{p.required && <span className="ap-req"> *</span>}</legend>
        <div className="ap-grid">
          {MEMBER_FIELDS.map(([cle, nom]) => (
            <input
              key={cle}
              className="ap-input"
              aria-label={nom}
              placeholder={nom}
              type={cle === 'email' ? 'email' : cle === 'phone' ? 'tel' : 'text'}
              value={v[cle] ?? ''}
              onChange={(e) => onChange({ ...v, [cle]: e.target.value })}
            />
          ))}
        </div>
      </fieldset>
    )
  }
  if (block.type === 'payment') {
    return (
      <div className="ap-field">
        <div className="ap-pay">
          <span>{label(block)}</span>
          <strong>{euros(p.amount)}</strong>
        </div>
        <label className="ap-choice">
          <input type="checkbox" disabled={disabled} checked={Boolean(value)} onChange={(e) => onChange(e.target.checked || null)} />
          <span>Je règle {euros(p.amount)}</span>
        </label>
      </div>
    )
  }
  if (block.type === 'yesNo') {
    return (
      <div className="ap-field">
        <label className="ap-choice">
          <input type="checkbox" id={id} disabled={disabled} checked={value === true} onChange={(e) => onChange(e.target.checked)} />
          <span>{label(block)}</span>
        </label>
      </div>
    )
  }
  if (block.type === 'signDocument') return <SignZone block={block} />
  if (block.type === 'assembly') {
    return <Assembly block={block} value={value} onChange={onChange} disabled={disabled} ctx={ctx} />
  }
  if (block.type === 'signature') {
    return (
      <div className="ap-field">
        {titre}
        <Signature value={value} onChange={onChange} disabled={disabled} />
      </div>
    )
  }
  const commun = { id, className: 'ap-input', disabled, value: value ?? '' }
  return (
    <div className="ap-field">
      {titre}
      {block.type === 'longText' ? (
        <textarea {...commun} rows={3} maxLength={5000} onChange={(e) => onChange(e.target.value)} />
      ) : block.type === 'date' ? (
        <input {...commun} type="date" onChange={(e) => onChange(e.target.value)} />
      ) : block.type === 'number' ? (
        <input {...commun} type="number" inputMode="decimal" onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))} />
      ) : (
        <input {...commun} type="text" maxLength={500} onChange={(e) => onChange(e.target.value)} />
      )}
    </div>
  )
}

function Blocks({ blocks, values, setValue, disabled, ctx, onTexte }) {
  let numero = 0
  return blocks.map((b) => {
    numero = b.type === 'numberedListItem' ? numero + 1 : 0
    const enfants = b.children?.length ? (
      <div className="ap-children">
        <Blocks blocks={b.children} values={values} setValue={setValue} disabled={disabled} ctx={ctx} onTexte={onTexte} />
      </div>
    ) : null
    if (BLOCKS[b.type]) {
      return (
        <div key={b.id}>
          <Question block={b} value={values[b.id]} onChange={(v) => setValue(b.id, v)} disabled={disabled} ctx={ctx} />
          {enfants}
        </div>
      )
    }
    return (
      <div key={b.id}>
        <Layout block={b} index={numero} onTexte={onTexte} />
        {enfants}
      </div>
    )
  })
}

// `onSubmit(values)` : renvoie une promesse ; absent = page à lire seulement.
// `initial` : la réponse déjà donnée (lien personnel) ; on la corrige.
// `assembly` : ce que le serveur dit du bloc Présence et procuration.
// `onTexte(id, texte)` : présent, les textes se corrigent en les touchant
// (Aperçu d'un brouillon). `interactif` : les questions se cliquent sans
// bouton d'envoi (Aperçu).
export default function Page({
  content, size = 'phone', onSubmit, submitLabel = 'Envoyer ma réponse', note, initial, assembly, onTexte, interactif = false,
}) {
  const [values, setValues] = useState(initial ?? {})
  const [envoi, setEnvoi] = useState(false)
  const [merci, setMerci] = useState(false)
  const blocks = content?.entry?.blocks ?? []
  const setValue = (id, v) => setValues((x) => ({ ...x, [id]: v }))

  if (!blocks.length) {
    return <div className={`ap-page ap-page--${size}`}><p className="ap-empty">La page est vide. Préparez-la d’abord.</p></div>
  }
  if (merci) {
    return (
      <div className={`ap-page ap-page--${size}`}>
        <div className="ap-merci">Merci, votre réponse est enregistrée.{note && <span> {note}</span>}</div>
        <button type="button" className="ap-link" onClick={() => (initial ? null : setValues({}), setMerci(false))}>
          {initial ? 'Modifier ma réponse' : 'Répondre encore'}
        </button>
      </div>
    )
  }
  return (
    <form
      className={`ap-page ap-page--${size}`}
      onSubmit={async (e) => {
        e.preventDefault()
        if (!onSubmit || envoi) return
        setEnvoi(true)
        try {
          const vides = Object.fromEntries(Object.entries(values).filter(([, v]) => v != null && v !== ''))
          await onSubmit(vides)
          setMerci(true)
        } catch {
          // le message d'erreur est affiché par l'appelant
        } finally {
          setEnvoi(false)
        }
      }}
    >
      <Blocks blocks={blocks} values={values} setValue={setValue} disabled={!(onSubmit || interactif) || size === 'a4'} ctx={assembly} onTexte={onTexte} />
      {onSubmit && size !== 'a4' && (
        <button type="submit" className="ap-send" disabled={envoi}>
          {envoi ? 'Envoi…' : submitLabel}
        </button>
      )}
    </form>
  )
}
