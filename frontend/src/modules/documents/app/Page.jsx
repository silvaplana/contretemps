import { useEffect, useRef, useState } from 'react'
import { BLOCKS, MEMBER_FIELDS, euros, label, options } from './blocks.js'

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

function Layout({ block, index }) {
  const c = <Inline content={block.content} />
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
    ctx.lineWidth = 2.5
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
        width={600}
        height={180}
        aria-label="Zone de signature"
        onPointerDown={(e) => {
          if (disabled) return
          e.currentTarget.setPointerCapture(e.pointerId)
          trace.current = true
          const ctx = toile.current.getContext('2d')
          ctx.beginPath()
          ctx.moveTo(...point(e))
        }}
        onPointerMove={(e) => {
          if (!trace.current) return
          const ctx = toile.current.getContext('2d')
          ctx.lineTo(...point(e))
          ctx.stroke()
        }}
        onPointerUp={() => {
          if (!trace.current) return
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

function Question({ block, value, onChange, disabled }) {
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

function Blocks({ blocks, values, setValue, disabled }) {
  let numero = 0
  return blocks.map((b) => {
    numero = b.type === 'numberedListItem' ? numero + 1 : 0
    const enfants = b.children?.length ? (
      <div className="ap-children">
        <Blocks blocks={b.children} values={values} setValue={setValue} disabled={disabled} />
      </div>
    ) : null
    if (BLOCKS[b.type]) {
      return (
        <div key={b.id}>
          <Question block={b} value={values[b.id]} onChange={(v) => setValue(b.id, v)} disabled={disabled} />
          {enfants}
        </div>
      )
    }
    return (
      <div key={b.id}>
        <Layout block={b} index={numero} />
        {enfants}
      </div>
    )
  })
}

// `onSubmit(values)` : renvoie une promesse ; absent = page à lire seulement.
export default function Page({ content, size = 'phone', onSubmit, submitLabel = 'Envoyer ma réponse', note }) {
  const [values, setValues] = useState({})
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
        <button type="button" className="ap-link" onClick={() => (setValues({}), setMerci(false))}>
          Répondre encore
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
      <Blocks blocks={blocks} values={values} setValue={setValue} disabled={!onSubmit || size === 'a4'} />
      {onSubmit && size !== 'a4' && (
        <button type="submit" className="ap-send" disabled={envoi}>
          {envoi ? 'Envoi…' : submitLabel}
        </button>
      )}
    </form>
  )
}
