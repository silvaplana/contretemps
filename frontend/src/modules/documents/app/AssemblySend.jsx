import { useEffect, useRef, useState } from 'react'
import { telecharger } from './blocks.js'

// Onglet Diffuser d'une convocation d'AG (spec procurations.md §1.3) : une
// fois validée, on choisit à qui (Seb, 21 octobre : Tout le monde, Admins,
// Trésoriers, Professeurs, Élèves, ou des personnes ; pas les cours), l'œil
// montre la liste, puis « Envoyer aux N membres » (Annuler pendant 10 s) ou
// « Télécharger la convocation ». En option, un essai avec un membre choisi.

const cle = (p) => `${p.type}:${p.id}`

function Oeil() {
  return (
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M2 12s3.5-6.5 10-6.5S22 12 22 12s-3.5 6.5-10 6.5S2 12 2 12z" />
      <circle cx="12" cy="12" r="3" />
    </svg>
  )
}

const ANNULER_S = 10

export default function AssemblySend({ file, api, onToast, onSent }) {
  const [vue, setVue] = useState(null)
  // À qui : groupes (rôles, Tout le monde) et personnes ; le récapitulatif
  // (noms et adresses) vient du serveur.
  const [choisis, setChoisis] = useState(null)
  const [groupes, setGroupes] = useState([])
  const [recherche, setRecherche] = useState('')
  const [trouves, setTrouves] = useState([])
  const [recap, setRecap] = useState(null)
  const [voirListe, setVoirListe] = useState(false)
  // Proposés d'office : les convoqués de la dernière AG, une étiquette pour
  // tous (retirable) plutôt qu'une par personne.
  const [precedents, setPrecedents] = useState([])
  const [erreur, setErreur] = useState('')
  const [compte, setCompte] = useState(null) // secondes avant l'envoi
  const [essai, setEssai] = useState(false)
  const [qui, setQui] = useState('')
  const minuteur = useRef(null)

  useEffect(() => {
    api.assembly(file.id).then((v) => {
      setVue(v)
      setChoisis((c) => c ?? v.principals.filter((p) => p.type === 'group'))
      setPrecedents(v.principals.filter((p) => p.type === 'member'))
    }, (e) => setErreur(e.message))
    // Les groupes proposés : les rôles et « Tout le monde », pas les cours.
    api.principals('').then((l) => setGroupes(l.filter((p) => p.type === 'group' && String(p.id).startsWith('role:'))), () => {})
  }, [api, file.id])

  // Ce qui part vraiment : les choix, plus les convoqués de la dernière AG.
  const cibles = choisis ? [...choisis, ...precedents] : null
  const cleChoix = (cibles ?? []).map(cle).sort().join(',')
  useEffect(() => {
    if (!cibles) return undefined
    let actif = true
    if (!cibles.length) {
      Promise.resolve().then(() => actif && setRecap({ count: 0, recipients: [], without_email: [] }))
    } else {
      api.sendPreview(file.id, cibles).then((r) => actif && setRecap(r), (e) => actif && onToast(e.message))
    }
    return () => {
      actif = false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [api, file.id, cleChoix])

  useEffect(() => {
    if (!recherche.trim()) return undefined
    let actif = true
    const t = setTimeout(() => {
      api.principals(recherche).then((l) => actif && setTrouves(l.filter((p) => p.type === 'member')), () => {})
    }, 200)
    return () => {
      actif = false
      clearTimeout(t)
    }
  }, [api, recherche])
  useEffect(() => () => clearInterval(minuteur.current), [])

  if (erreur) return <p className="dx-error" role="alert">{erreur}</p>
  if (!vue) return <p className="dx-note">Chargement…</p>

  const avecEmail = vue.recipients.filter((r) => r.email)
  const deja = vue.summary.convoked
  const nb = recap?.count ?? 0
  const estChoisi = (p) => (choisis ?? []).some((q) => cle(q) === cle(p))
  const basculer = (p) =>
    setChoisis((l) => (l.some((q) => cle(q) === cle(p)) ? l.filter((q) => cle(q) !== cle(p)) : [...l, { type: p.type, id: p.id, label: p.label }]))
  const personnes = (choisis ?? []).filter((p) => p.type === 'member')

  async function envoyer() {
    try {
      const r = await api.send(file.id, cibles)
      onToast(`Convocation envoyée à ${r.sent} membre${r.sent > 1 ? 's' : ''}`)
      setVue(await api.assembly(file.id))
      onSent?.()
    } catch (e) {
      onToast(e.message)
    }
  }

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

  async function faireEssai() {
    try {
      const r = await api.sendTrial(file.id, Number(qui))
      onToast(`Essai envoyé à ${r.email}`)
      setEssai(false)
    } catch (e) {
      onToast(e.message)
    }
  }

  return (
    <div className="ag-send">
      {deja > 0 ? (
        <>
          <p className="ad-ok">Convocation envoyée à {deja} membre{deja > 1 ? 's' : ''}. Les réponses arrivent dans Résultats.</p>
          <p className="af-hint">Sept jours avant l’assemblée, ceux qui n’ont pas répondu reçoivent un rappel par email.</p>
        </>
      ) : (
        <section className="ag-qui" aria-label="À qui envoyer">
          <h3>À qui ?</h3>
          <div className="ag-groupes">
            {groupes.map((g) => (
              <button
                key={cle(g)}
                type="button"
                className={`ag-groupe${estChoisi(g) ? ' ag-groupe--on' : ''}`}
                aria-pressed={estChoisi(g)}
                onClick={() => basculer(g)}
              >
                {estChoisi(g) ? '✓ ' : ''}
                {g.label}
              </button>
            ))}
          </div>
          {(personnes.length > 0 || precedents.length > 0) && (
            <div className="ad-choisis">
              {precedents.length > 0 && (
                <span className="ad-puce">
                  Les convoqués de la dernière AG ({precedents.length})
                  <button type="button" aria-label="Retirer les convoqués de la dernière AG" onClick={() => setPrecedents([])}>
                    ✕
                  </button>
                </span>
              )}
              {personnes.map((p) => (
                <span key={cle(p)} className="ad-puce">
                  {p.label ?? 'Une personne'}
                  <button type="button" aria-label={`Retirer ${p.label ?? ''}`} onClick={() => basculer(p)}>
                    ✕
                  </button>
                </span>
              ))}
            </div>
          )}
          <div className="dx-sugg">
            <input className="dx-input" placeholder="Ajouter une personne (nom)…" value={recherche} onChange={(e) => setRecherche(e.target.value)} />
            {recherche.trim() && trouves.length > 0 && (
              <div className="dx-sugg__list">
                {trouves.slice(0, 8).map((p) => (
                  <button
                    key={cle(p)}
                    type="button"
                    onClick={() => {
                      if (!estChoisi(p)) basculer(p)
                      setRecherche('')
                    }}
                  >
                    <span className="dx-meta">
                      <span className="dx-n">{p.label}</span>
                      <span className="dx-s">{p.detail}</span>
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
          <p className="ag-pour">
            Recevront la convocation : <strong>{nb} personne{nb > 1 ? 's' : ''}</strong>
            <button
              type="button"
              className="dx-ico ag-oeil"
              aria-label={voirListe ? 'Cacher la liste' : 'Voir qui la recevra'}
              aria-pressed={voirListe}
              title="Voir qui la recevra"
              onClick={() => setVoirListe((v) => !v)}
            >
              <Oeil />
            </button>
          </p>
          {voirListe && recap && (
            <ul className="ad-destinataires">
              {[...recap.recipients]
                .sort((a, b) => a.name.localeCompare(b.name, 'fr'))
                .map((d) => (
                  <li key={d.email + d.name}>
                    <span className="ad-destinataires__nom">{d.name}</span>
                    <span className="ad-destinataires__email">({d.email})</span>
                  </li>
                ))}
            </ul>
          )}
          {recap?.without_email?.length > 0 && (
            <p className="af-hint">Sans adresse email (à prévenir autrement) : {recap.without_email.join(', ')}.</p>
          )}
        </section>
      )}

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
        deja === 0 && (
          <button type="button" className="dx-btn" disabled={!file.can_manage || !nb} onClick={lancer}>
            Envoyer aux {nb} membre{nb > 1 ? 's' : ''}
          </button>
        )
      )}
      <button
        type="button"
        className="dx-btn dx-btn--ghost"
        onClick={async () => {
          try {
            telecharger(await api.assemblyFile(file.id, 'convocation.pdf'), `${file.name}.pdf`)
          } catch (e) {
            onToast(e.message)
          }
        }}
      >
        Télécharger la convocation
      </button>

      {deja === 0 && (
        <section className="ad-carte">
          <h3>Faire un essai avec un membre</h3>
          <p className="af-hint">Il reçoit le mail « [Essai] » et répond par son lien ; sa réponse ne compte pas.</p>
          {essai ? (
            <div className="ad-boutons">
              <select className="ap-input" aria-label="Membre" value={qui} onChange={(e) => setQui(e.target.value)}>
                <option value="">Choisir un membre</option>
                {avecEmail.map((r) => (
                  <option key={r.person_id} value={r.person_id}>{r.name}</option>
                ))}
              </select>
              <button type="button" className="dx-btn dx-btn--small" disabled={!qui} onClick={faireEssai}>
                Envoyer l’essai
              </button>
            </div>
          ) : (
            <button type="button" className="dx-btn dx-btn--small dx-btn--ghost" disabled={!file.can_manage} onClick={() => setEssai(true)}>
              Choisir un membre
            </button>
          )}
        </section>
      )}
    </div>
  )
}
