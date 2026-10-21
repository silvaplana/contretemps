import { useEffect, useState } from 'react'
import { telecharger } from './blocks.js'

// Onglet Diffuser d'un procès-verbal d'AG (proces-verbal-ag.md §1, étapes 5
// à 8). Validé : « Qui doit signer ? » (le bureau, présidence et secrétariat
// cochés d'avance), puis le suivi des signatures avec Relancer et « Signer
// moi-même ». Officiel (tout le monde a signé) : Télécharger le PDF, et
// « Envoyer aux N membres… » ouvre le Diffuser habituel.

const jour = (iso) => new Date(iso).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })

export default function MinutesSign({ file, api, onToast, onChanger }) {
  const [etat, setEtat] = useState(null)
  const [erreur, setErreur] = useState('')
  const [coches, setCoches] = useState(null) // { person_id: true }
  const [autres, setAutres] = useState([]) // [{ person_id, name }]
  const [ajout, setAjout] = useState(false)
  const [cherche, setCherche] = useState('')
  const [trouves, setTrouves] = useState([])
  const [envoi, setEnvoi] = useState(false)

  useEffect(() => {
    api.minutes(file.id).then(
      (e) => {
        setEtat(e)
        setCoches(Object.fromEntries(e.board.filter((b) => b.default).map((b) => [b.person_id, true])))
      },
      (e) => setErreur(e.message),
    )
  }, [api, file.id])
  useEffect(() => {
    if (!ajout || cherche.trim().length < 2) return
    let actif = true
    api.principals(cherche.trim()).then((r) => actif && setTrouves(r.filter((p) => p.type === 'member')), () => {})
    return () => {
      actif = false
    }
  }, [api, ajout, cherche])

  if (erreur) return <p className="dx-error" role="alert">{erreur}</p>
  if (!etat) return <p className="dx-note">Chargement…</p>

  async function pdf() {
    try {
      telecharger(await api.minutesPdf(file.id), `${file.name}.pdf`)
    } catch (e) {
      onToast(e.message)
    }
  }

  async function envoyer(ids, message) {
    setEnvoi(true)
    try {
      await api.signMinutes(file.id, ids)
      onToast(message)
      setEtat(await api.minutes(file.id))
    } catch (e) {
      onToast(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  if (etat.status === 'official') {
    return (
      <div className="ag-send">
        <p className="ad-ok">Signé par tous : le procès-verbal est officiel. Le PDF signé est rangé dans le dossier de l’assemblée.</p>
        <button type="button" className="dx-btn" onClick={pdf}>Télécharger le PDF</button>
        {etat.members > 0 && (
          <button type="button" className="dx-btn dx-btn--ghost" disabled={!file.can_manage} onClick={onChanger}>
            Envoyer aux {etat.members} membres…
          </button>
        )}
      </div>
    )
  }

  if (etat.signers.length) {
    const mien = etat.signers.find((s) => s.token && !s.signed_at)
    return (
      <div className="ag-send">
        <p className="ag-pour">
          Signatures : <strong>{etat.signed} sur {etat.signers.length}</strong>. Chaque signature est envoyée à l’adresse de contact de l’école, avec le PDF à jour.
        </p>
        <div className="em-liste">
          {etat.signers.map((s) => (
            <div key={s.person_id} className={`em-ligne${s.signed_at ? ' em-ligne--on' : ''}`}>
              <span className="em-coche" aria-hidden="true">{s.signed_at ? '✓' : ''}</span>
              <span className="em-nom">
                {s.name}
                <small>
                  {s.functions && `${s.functions} · `}
                  {s.signed_at ? `a signé le ${jour(s.signed_at)}` : s.send_status === 'failed' ? 'email non parti' : 'pas encore signé'}
                </small>
              </span>
              {!s.signed_at && !s.token && (
                <button
                  type="button"
                  className="dx-btn dx-btn--small dx-btn--ghost"
                  disabled={envoi || !file.can_manage}
                  onClick={() => envoyer([s.person_id], `Relance envoyée à ${s.name}`)}
                >
                  Relancer
                </button>
              )}
            </div>
          ))}
        </div>
        {mien && (
          <button type="button" className="dx-btn" onClick={() => window.location.assign(`${import.meta.env.BASE_URL}r/${mien.token}`)}>
            Signer moi-même
          </button>
        )}
        <button type="button" className="dx-btn dx-btn--ghost" onClick={pdf}>Télécharger le PDF</button>
      </div>
    )
  }

  const gens = [...etat.board, ...autres.filter((a) => !etat.board.some((b) => b.person_id === a.person_id))]
  const choisis = gens.filter((g) => coches[g.person_id]).map((g) => g.person_id)
  return (
    <div className="ag-send">
      <p className="dx-q">Qui doit signer ?</p>
      {etat.board.length === 0 && (
        <p className="af-hint">Personne n’a de fonction au bureau : cochez-les dans École › Administrateurs, colonne Bureau, ou ajoutez une personne.</p>
      )}
      <div className="em-liste">
        {gens.map((g) => (
          <button
            key={g.person_id}
            type="button"
            className={`em-ligne${coches[g.person_id] ? ' em-ligne--on' : ''}`}
            aria-pressed={Boolean(coches[g.person_id])}
            onClick={() => setCoches((c) => ({ ...c, [g.person_id]: !c[g.person_id] }))}
          >
            <span className="em-coche" aria-hidden="true">{coches[g.person_id] ? '✓' : ''}</span>
            <span className="em-nom">
              {g.name}
              {g.functions && <small>{g.functions}</small>}
            </span>
          </button>
        ))}
        {ajout ? (
          <>
            <input
              className="ap-input"
              type="search"
              placeholder="Nom de la personne"
              aria-label="Chercher une personne"
              value={cherche}
              onChange={(e) => setCherche(e.target.value)}
              autoFocus
            />
            {trouves
              .filter((p) => !gens.some((g) => String(g.person_id) === String(p.id)))
              .map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="em-ligne"
                  onClick={() => {
                    const id = Number(p.id)
                    setAutres((a) => [...a, { person_id: id, name: p.label, functions: '' }])
                    setCoches((c) => ({ ...c, [id]: true }))
                    setAjout(false)
                    setCherche('')
                  }}
                >
                  <span className="em-nom">{p.label}</span>
                </button>
              ))}
          </>
        ) : (
          <button type="button" className="ap-link" onClick={() => (setAjout(true), setTrouves([]))}>
            + Une autre personne
          </button>
        )}
      </div>
      {!etat.available && <p className="af-hint">L’envoi d’emails n’est pas configuré sur ce serveur.</p>}
      <button
        type="button"
        className="dx-btn"
        disabled={envoi || !file.can_manage || !choisis.length || !etat.available}
        onClick={() => envoyer(choisis, `Envoyé pour signature à ${choisis.length} personne${choisis.length > 1 ? 's' : ''}`)}
      >
        Envoyer pour signature
      </button>
      <button type="button" className="dx-btn dx-btn--ghost" onClick={pdf}>Télécharger le PDF (sans signatures)</button>
    </div>
  )
}
