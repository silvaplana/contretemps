import { useEffect, useRef, useState } from 'react'

// Document à signer, « 2. Diffuser » (signature-documents.md §2.3, maquette
// v3) : « Faire signer à qui ? ». Une puce par fonction du bureau, les
// Professeurs et les Élèves, ou quelqu'un d'autre (un membre cherché par son
// nom, ou une personne hors de l'école avec son adresse email). Puis
// « Envoyer aux N », Annuler pendant 10 s. Tout le monde signe en même temps.

const ANNULER_S = 10
const ROLES = ['role:professeur', 'role:eleve']
const cle = (p) => (p.type === 'other' ? `other:${p.email}` : `${p.type}:${p.id}`)

export default function SignSend({ file, api, onToast, onSent }) {
  const [etat, setEtat] = useState(null)
  const [erreur, setErreur] = useState('')
  const [roles, setRoles] = useState([])
  const [choisis, setChoisis] = useState([])
  const [recherche, setRecherche] = useState('')
  const [trouves, setTrouves] = useState([])
  const [autre, setAutre] = useState(null) // { name, email } : quelqu'un hors de l'école
  const [recap, setRecap] = useState(null)
  const [compte, setCompte] = useState(null) // secondes avant l'envoi
  const minuteur = useRef(null)

  useEffect(() => {
    api.signers(file.id).then(setEtat, (e) => setErreur(e.message))
    api.principals('').then((l) => setRoles(ROLES.map((r) => l.find((p) => p.id === r)).filter(Boolean)), () => {})
  }, [api, file.id])
  useEffect(() => () => clearInterval(minuteur.current), [])

  useEffect(() => {
    if (recherche.trim().length < 2) return undefined
    let actif = true
    const t = setTimeout(() => {
      api.principals(recherche.trim()).then((l) => actif && setTrouves(l), () => {})
    }, 200)
    return () => {
      actif = false
      clearTimeout(t)
    }
  }, [api, recherche])

  // Le récapitulatif nominatif suit le choix (le serveur résout les groupes).
  const membres = choisis.filter((p) => p.type !== 'other')
  const autres = choisis.filter((p) => p.type === 'other').map(({ name, email }) => ({ name, email }))
  const cleChoix = choisis.map(cle).join(',')
  useEffect(() => {
    if (!choisis.length) return undefined
    let actif = true
    api.signPreview(file.id, membres, autres).then((r) => actif && setRecap({ cle: cleChoix, ...r }), (e) => actif && onToast(e.message))
    return () => {
      actif = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, file.id, cleChoix])

  if (erreur) return <p className="dx-error" role="alert">{erreur}</p>
  if (!etat) return <p className="dx-note">Chargement…</p>

  const estChoisi = (p) => choisis.some((q) => cle(q) === cle(p))
  const basculer = (p) => setChoisis((l) => (l.some((q) => cle(q) === cle(p)) ? l.filter((q) => cle(q) !== cle(p)) : [...l, p]))
  const r = choisis.length && recap?.cle === cleChoix ? recap : null
  const nb = r?.count ?? 0
  const q = recherche.trim()
  const proposes = q.length >= 2 ? trouves.filter((p) => !estChoisi(p)).slice(0, 6) : []

  function lancer() {
    let reste = ANNULER_S
    setCompte(reste)
    minuteur.current = setInterval(() => {
      reste -= 1
      if (reste > 0) setCompte(reste)
      else {
        clearInterval(minuteur.current)
        setCompte(null)
        envoyer()
      }
    }, 1000)
  }

  async function envoyer() {
    try {
      const fait = await api.signSend(file.id, membres, autres)
      onToast(`Envoyé pour signature à ${fait.sent} personne${fait.sent > 1 ? 's' : ''}`)
      setChoisis([])
      onSent?.()
    } catch (e) {
      onToast(e.message)
    }
  }

  return (
    <div className="ag-send">
      <h3 className="sg-titre">Faire signer à qui ?</h3>
      {etat.signers.length > 0 && (
        <p className="af-hint">
          Déjà envoyé à {etat.signers.length} personne{etat.signers.length > 1 ? 's' : ''} : le suivi est dans « Voir les résultats ». Vous
          pouvez en ajouter d’autres ici.
        </p>
      )}

      <p className="sg-grp">Bureau</p>
      {etat.board.length ? (
        <div className="ag-groupes">
          {etat.board.map((b) => {
            const p = { type: 'member', id: String(b.person_id), label: b.name }
            return (
              <button
                key={`${b.function}-${b.person_id}`}
                type="button"
                className={`ag-groupe${estChoisi(p) ? ' ag-groupe--on' : ''}`}
                aria-pressed={estChoisi(p)}
                onClick={() => basculer(p)}
              >
                {estChoisi(p) ? '✓ ' : ''}
                {b.function} · {b.name}
              </button>
            )
          })}
        </div>
      ) : (
        <p className="af-hint">Personne n’a de fonction au bureau : cochez-les dans École › Administrateurs, colonne Bureau.</p>
      )}

      {roles.length > 0 && (
        <>
          <p className="sg-grp">Membres</p>
          <div className="ag-groupes">
            {roles.map((g) => (
              <button
                key={cle(g)}
                type="button"
                className={`ag-groupe${estChoisi(g) ? ' ag-groupe--on' : ''}`}
                aria-pressed={estChoisi(g)}
                onClick={() => basculer({ type: g.type, id: g.id, label: g.label })}
              >
                {estChoisi(g) ? '✓ ' : ''}
                {g.label}
              </button>
            ))}
          </div>
        </>
      )}

      <p className="sg-grp">Quelqu’un d’autre</p>
      {choisis.some((p) => p.type !== 'group' && !etat.board.some((b) => String(b.person_id) === p.id)) && (
        <div className="ad-choisis">
          {choisis
            .filter((p) => p.type !== 'group' && !etat.board.some((b) => String(b.person_id) === p.id))
            .map((p) => (
              <span key={cle(p)} className="ad-puce">
                {p.type === 'other' ? `${p.name} (${p.email})` : p.label}
                <button type="button" aria-label={`Retirer ${p.label ?? p.name}`} onClick={() => basculer(p)}>
                  ✕
                </button>
              </span>
            ))}
        </div>
      )}
      {autre ? (
        <form
          className="sg-autre"
          onSubmit={(e) => {
            e.preventDefault()
            basculer({ type: 'other', name: autre.name.trim(), email: autre.email.trim().toLowerCase() })
            setAutre(null)
            setRecherche('')
          }}
        >
          <label className="af-label" htmlFor="sg-autre-nom">Son nom</label>
          <input id="sg-autre-nom" className="dx-input" value={autre.name} onChange={(e) => setAutre({ ...autre, name: e.target.value })} />
          <label className="af-label" htmlFor="sg-autre-email">Son adresse email</label>
          <input
            id="sg-autre-email"
            className="dx-input"
            type="email"
            inputMode="email"
            autoFocus
            value={autre.email}
            onChange={(e) => setAutre({ ...autre, email: e.target.value })}
          />
          <div className="ad-boutons">
            <button type="submit" className="dx-btn dx-btn--small" disabled={!autre.name.trim() || !/^\S+@\S+\.\S+$/.test(autre.email.trim())}>
              Ajouter
            </button>
            <button type="button" className="dx-btn dx-btn--small dx-btn--ghost" onClick={() => setAutre(null)}>
              Annuler
            </button>
          </div>
        </form>
      ) : (
        <div className="dx-sugg">
          <input
            className="dx-input"
            type="search"
            placeholder="Chercher un nom"
            aria-label="Chercher un nom"
            value={recherche}
            onChange={(e) => setRecherche(e.target.value)}
          />
          {q.length >= 2 && (
            <div className="dx-sugg__list">
              {proposes.map((p) => (
                <button
                  key={cle(p)}
                  type="button"
                  onClick={() => {
                    basculer({ type: p.type, id: p.id, label: p.label })
                    setRecherche('')
                  }}
                >
                  <span className="dx-meta">
                    <span className="dx-n">{p.label}</span>
                    <span className="dx-s">{p.detail}</span>
                  </span>
                </button>
              ))}
              <button type="button" onClick={() => setAutre({ name: q, email: '' })}>
                <span className="dx-meta">
                  <span className="dx-n">Ajouter « {q} »</span>
                  <span className="dx-s">hors de l’école, avec son adresse email</span>
                </span>
              </button>
            </div>
          )}
        </div>
      )}

      {r && (
        <p className="ag-pour">
          <strong>
            {nb} signataire{nb > 1 ? 's' : ''}
          </strong>
          {nb > 0 && ` : ${r.recipients.map((d) => d.name).join(', ')}.`}
        </p>
      )}
      {r?.without_email?.length > 0 && <p className="af-hint">Sans adresse email (ne recevront rien) : {r.without_email.join(', ')}.</p>}
      {r?.signed?.length > 0 && <p className="af-hint">Ont déjà signé : {r.signed.join(', ')}.</p>}
      {!etat.available && <p className="af-hint">L’envoi d’emails n’est pas configuré sur ce serveur.</p>}

      {compte != null ? (
        <div className="ag-compte" role="status">
          <span>Envoi dans {compte} s…</span>
          <button
            type="button"
            className="dx-btn dx-btn--ghost"
            onClick={() => {
              clearInterval(minuteur.current)
              setCompte(null)
            }}
          >
            Annuler
          </button>
        </div>
      ) : (
        <button type="button" className="dx-btn" disabled={!file.can_manage || !nb || !etat.available} onClick={lancer}>
          {nb > 1 ? `Envoyer aux ${nb}` : nb === 1 ? `Envoyer à ${r.recipients[0].name}` : 'Envoyer'}
        </button>
      )}
    </div>
  )
}
