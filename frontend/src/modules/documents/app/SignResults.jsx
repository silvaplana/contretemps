import { useCallback, useEffect, useState } from 'react'

// Document à signer, « 3. Voir les résultats » (signature-documents.md §2.5,
// maquette v3) : qui a signé, Relancer, Signer moi-même. Le journal de
// preuves et « Produire le document signé » viennent à l'étape 3.

const quand = (iso) => {
  const d = new Date(iso)
  return `le ${d.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })} à ${d.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }).replace(':', ' h ')}`
}

function etiquette(s) {
  switch (s.state) {
    case 'signed':
      return { texte: `Signé ${quand(s.at)}`, classe: 'sg-pill--ok' }
    case 'refused':
      return { texte: 'A refusé', classe: 'sg-pill--ko' }
    case 'read':
      return { texte: 'A lu', classe: '' }
    case 'opened':
      return { texte: 'A ouvert', classe: '' }
    case 'failed':
      return { texte: 'Email non parti', classe: 'sg-pill--ko' }
    case 'pending':
      return { texte: 'En cours d’envoi', classe: '' }
    default:
      return { texte: 'Pas encore', classe: '' }
  }
}

export default function SignResults({ file, api, onToast }) {
  const [etat, setEtat] = useState(null)
  const [erreur, setErreur] = useState('')
  const [envoi, setEnvoi] = useState(false)

  const recharger = useCallback(() => api.signers(file.id).then(setEtat, (e) => setErreur(e.message)), [api, file.id])
  useEffect(() => {
    recharger()
  }, [recharger])
  // Pendant l'envoi des emails (après la réponse du serveur), le suivi se met à jour.
  useEffect(() => {
    if (!etat?.signers.some((s) => s.state === 'pending')) return undefined
    const t = setTimeout(recharger, 1500)
    return () => clearTimeout(t)
  }, [etat, recharger])

  if (erreur) return <p className="dx-error" role="alert">{erreur}</p>
  if (!etat) return <p className="dx-note">Chargement…</p>

  const gens = etat.signers
  // « Relancer les N » : ni ceux qui ont signé, ni ceux qui ont refusé.
  const aRelancer = gens.filter((s) => s.state !== 'signed' && s.state !== 'refused')
  const mien = gens.find((s) => s.token && s.state !== 'signed')

  async function relancer(ids, message) {
    setEnvoi(true)
    try {
      await api.signRemind(file.id, ids)
      onToast(message)
      await recharger()
    } catch (e) {
      onToast(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  return (
    <div className="ag-send">
      <p className="sg-titre">
        {etat.signed} sur {gens.length} ont signé
      </p>
      <div className="em-liste">
        {gens.map((s) => {
          const e = etiquette(s)
          return (
            <div key={s.id} className="sg-ligne">
              <span className="em-nom">
                {s.name}
                <small>{s.functions || s.email}</small>
                {s.reason && <small className="sg-motif">« {s.reason} »</small>}
              </span>
              <span className={`sg-pill ${e.classe}`}>{e.texte}</span>
              {s.state !== 'signed' && !s.token && (
                <button
                  type="button"
                  className="dx-btn dx-btn--small dx-btn--ghost"
                  disabled={envoi || !file.can_manage}
                  onClick={() => relancer([s.id], `Relance envoyée à ${s.name}`)}
                >
                  Relancer
                </button>
              )}
            </div>
          )
        })}
      </div>
      {aRelancer.length > 1 && (
        <button
          type="button"
          className="dx-btn dx-btn--ghost"
          disabled={envoi || !file.can_manage}
          onClick={() => relancer(null, `Relance envoyée à ${aRelancer.length} personnes`)}
        >
          Relancer les {aRelancer.length}
        </button>
      )}
      {mien && (
        <button type="button" className="dx-btn dx-btn--ghost" onClick={() => window.location.assign(`${import.meta.env.BASE_URL}r/${mien.token}`)}>
          Signer moi-même
        </button>
      )}
      <button type="button" className="dx-btn" disabled>
        Produire le document signé
      </button>
      <p className="af-hint sg-centre">
        {etat.signed < gens.length ? 'Possible quand tout le monde a signé.' : 'Tout le monde a signé : le document signé se produira à la prochaine version.'}
      </p>
    </div>
  )
}
