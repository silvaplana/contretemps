import { useCallback, useEffect, useRef, useState } from 'react'
import { debutTrait, finTrait, pointsDe, suiteTrait } from './trait.js'

// La page du signataire (signature-documents.md §2.4, maquette v3), ouverte
// par son lien personnel, sans compte. Un écran par étape, un bouton
// principal chacun : Bonjour, Lire le document (jusqu'en bas), Signer (case
// de consentement, signature au doigt, initiales si le paraphe est demandé),
// C'est signé. Sous la lecture, « Je ne signe pas » avec un motif. Le serveur
// note chaque pas au journal de preuves et refuse une signature sans lecture
// ni case cochée.

const heure = (iso) => {
  const d = new Date(iso)
  return `le ${d.toLocaleDateString('fr-FR')} à ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }).replace(':', ' h ')}`
}

function Pad({ label, small, onChange }) {
  const toile = useRef(null)
  const trace = useRef(false)
  const [vide, setVide] = useState(true)

  useEffect(() => {
    const c = toile.current
    const r = c.getBoundingClientRect()
    const dpr = window.devicePixelRatio || 1
    c.width = r.width * dpr
    c.height = r.height * dpr
    const ctx = c.getContext('2d')
    ctx.scale(dpr, dpr)
    ctx.lineWidth = 2.5
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    ctx.strokeStyle = '#1f2a44'
  }, [])

  const point = (e) => {
    const r = toile.current.getBoundingClientRect()
    return [e.clientX - r.left, e.clientY - r.top]
  }
  return (
    <div className={`sl-pad${small ? ' sl-pad--small' : ''}`}>
      <canvas
        ref={toile}
        aria-label={label}
        onPointerDown={(e) => {
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
          setVide(false)
          onChange(toile.current.toDataURL('image/png'))
        }}
      />
      {vide && <span>{label}</span>}
    </div>
  )
}

// Les pages du PDF figé, en images ; `onFin` quand la dernière a défilé à l'écran.
function Pages({ base, count, onFin }) {
  const [urls, setUrls] = useState([])
  const fin = useRef(null)
  useEffect(() => {
    let actif = true
    const faites = []
    ;(async () => {
      for (let n = 1; n <= count; n += 1) {
        try {
          const r = await fetch(`${base}/pages/${n}`)
          if (!r.ok || !actif) break
          faites.push(URL.createObjectURL(await r.blob()))
          setUrls([...faites])
        } catch {
          break
        }
      }
    })()
    return () => {
      actif = false
      faites.forEach((u) => URL.revokeObjectURL(u))
    }
  }, [base, count])
  const toutes = urls.length === count
  useEffect(() => {
    if (!toutes || !fin.current) return undefined
    const o = new IntersectionObserver((entrees) => entrees.some((e) => e.isIntersecting) && onFin())
    o.observe(fin.current)
    return () => o.disconnect()
  }, [toutes, onFin])
  return (
    <div className="sl-pages">
      {urls.map((url, i) => (
        <figure key={url} className="sg-page">
          <img src={url} alt={`Page ${i + 1} sur ${count}`} />
        </figure>
      ))}
      {toutes ? (
        <p ref={fin} className="sl-fin">
          Fin du document
        </p>
      ) : (
        <p className="pp-attente">Chargement des pages…</p>
      )}
    </div>
  )
}

export default function SignLink({ jeton, lire, baseUrl }) {
  const base = `${baseUrl}/documents/public/signing/${encodeURIComponent(jeton)}`
  const [vue, setVue] = useState(null)
  const [erreur, setErreur] = useState('')
  const [etape, setEtape] = useState('bonjour') // bonjour, lire, signer
  const [lu, setLu] = useState(false)
  const [refus, setRefus] = useState(null) // motif en cours d'écriture
  const [accord, setAccord] = useState(false)
  const [signature, setSignature] = useState(null)
  const [initiales, setInitiales] = useState(null)
  const [cle, setCle] = useState(0) // « Effacer » redessine les cadres
  const [envoi, setEnvoi] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    lire(base).then(
      (v) => {
        setVue(v)
        setLu(v.read)
      },
      (e) => setErreur(e.message),
    )
  }, [base, lire])

  // Le serveur note la lecture à son heure (§1, obligation 3).
  const finLue = useRef(false)
  const onFin = useCallback(() => {
    if (finLue.current || lu) return
    finLue.current = true
    lire(`${base}/read`, { method: 'POST' }).then(() => setLu(true), (e) => setMessage(e.message))
  }, [base, lire, lu])

  if (erreur) return <p className="pp-erreur">{erreur}</p>
  if (!vue) return <p className="pp-attente">Chargement…</p>

  const prenom = vue.person.split(' ')[0]

  if (vue.state === 'signed') {
    return (
      <section className="sl">
        <p className="sl-ok">
          ✓ Merci {prenom}. Votre signature est enregistrée {heure(vue.signed_at)}.
        </p>
        <p>Vous recevrez le document signé par mail quand il sera produit.</p>
        <p className="sl-petit">Le lien est fermé : il ne permet plus de signer une deuxième fois.</p>
      </section>
    )
  }
  if (vue.state === 'expired') {
    return <p className="pp-note">Ce lien a expiré. Demandez à {vue.sender} de vous le renvoyer.</p>
  }
  if (vue.state === 'draft') {
    return <p className="pp-note">Le document est en cours de correction. Vous recevrez un nouveau mail.</p>
  }

  async function signer() {
    setEnvoi(true)
    setMessage('')
    try {
      const r = await lire(`${base}/sign`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ consent: accord, signature, initials: initiales }),
      })
      setVue({ ...vue, state: 'signed', signed_at: r.signed_at })
      window.scrollTo(0, 0)
    } catch (e) {
      setMessage(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  async function refuser() {
    setEnvoi(true)
    setMessage('')
    try {
      await lire(`${base}/refuse`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reason: refus }),
      })
      setVue({ ...vue, refused: refus.trim() })
      setRefus(null)
      setEtape('bonjour')
      window.scrollTo(0, 0)
    } catch (e) {
      setMessage(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  const paraphe = vue.mode === 'initials'
  const pret = accord && signature && (!paraphe || initiales)

  if (etape === 'bonjour') {
    return (
      <section className="sl">
        <h1 className="sl-titre">Bonjour {prenom}</h1>
        <p>
          {vue.sender} vous demande de signer le document <b>« {vue.document} »</b> ({vue.pages} page{vue.pages > 1 ? 's' : ''}).
        </p>
        {vue.message && <p className="sl-consigne">{vue.message}</p>}
        {vue.refused && (
          <p className="pp-note">
            Vous avez indiqué ne pas signer : « {vue.refused} ». Vous pouvez encore le signer si vous changez d’avis.
          </p>
        )}
        <div className="sl-bas">
          <button type="button" className="sl-btn" onClick={() => (setEtape('lire'), window.scrollTo(0, 0))}>
            Lire le document
          </button>
        </div>
      </section>
    )
  }

  if (etape === 'lire') {
    return (
      <section className="sl">
        <h1 className="sl-titre">{vue.document}</h1>
        <Pages base={base} count={vue.pages} onFin={onFin} />
        {refus == null ? (
          <button type="button" className="sl-lien" onClick={() => setRefus('')}>
            Je ne signe pas
          </button>
        ) : (
          <div className="sl-refus">
            <label htmlFor="sl-motif">Pourquoi ne signez-vous pas ?</label>
            <textarea id="sl-motif" rows={3} maxLength={1000} value={refus} onChange={(e) => setRefus(e.target.value)} />
            <p className="sl-petit">{vue.sender} recevra votre message. Vous pourrez encore signer ensuite.</p>
            <div className="sl-ligne">
              <button type="button" className="sl-btn" disabled={envoi || !refus.trim()} onClick={refuser}>
                Envoyer
              </button>
              <button type="button" className="sl-btn sl-btn--ghost" onClick={() => setRefus(null)}>
                Annuler
              </button>
            </div>
          </div>
        )}
        {message && <p className="pp-erreur" role="alert">{message}</p>}
        <div className="sl-bas">
          <button type="button" className="sl-btn" disabled={!lu} onClick={() => (setEtape('signer'), window.scrollTo(0, 0))}>
            {lu ? 'J’ai lu, je signe' : 'Faites défiler jusqu’en bas'}
          </button>
        </div>
      </section>
    )
  }

  return (
    <section className="sl">
      <h1 className="sl-titre">Signer</h1>
      <label className="sl-accord">
        <input type="checkbox" checked={accord} onChange={(e) => setAccord(e.target.checked)} />
        <span>{vue.consent}</span>
      </label>
      {vue.mention && (
        <p className="sl-petit">
          Sera écrit au-dessus de votre signature : <b>{vue.mention}</b>
        </p>
      )}
      <Pad key={`s${cle}`} label="Signez ici avec le doigt" onChange={setSignature} />
      {paraphe && (
        <>
          <p>Vos initiales, reprises en bas des {vue.pages} pages :</p>
          <Pad key={`i${cle}`} small label="Initiales" onChange={setInitiales} />
        </>
      )}
      <button type="button" className="sl-lien" onClick={() => (setEtape('lire'), window.scrollTo(0, 0))}>
        Relire le document
      </button>
      <button
        type="button"
        className="sl-btn sl-btn--ghost"
        onClick={() => {
          setSignature(null)
          setInitiales(null)
          setCle((k) => k + 1)
        }}
      >
        Effacer
      </button>
      {message && <p className="pp-erreur" role="alert">{message}</p>}
      <div className="sl-bas">
        <button type="button" className="sl-btn" disabled={!pret || envoi} onClick={signer}>
          Signer
        </button>
      </div>
    </section>
  )
}
