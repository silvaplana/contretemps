import { useEffect, useRef, useState } from 'react'
import { telecharger } from './blocks.js'

// Onglet Diffuser d'une convocation d'AG (spec procurations.md §1.3) : une
// fois validée, « Envoyer aux N membres » (Annuler pendant 10 s) ou
// « Télécharger la convocation » ; « Changer » ouvre le Diffuser habituel
// pour choisir d'autres personnes. En option, un essai avec un membre choisi.

const ANNULER_S = 10

export default function AssemblySend({ file, api, onToast, onChanger, onSent }) {
  const [vue, setVue] = useState(null)
  const [erreur, setErreur] = useState('')
  const [compte, setCompte] = useState(null) // secondes avant l'envoi
  const [essai, setEssai] = useState(false)
  const [qui, setQui] = useState('')
  const minuteur = useRef(null)

  useEffect(() => {
    api.assembly(file.id).then(setVue, (e) => setErreur(e.message))
  }, [api, file.id])
  useEffect(() => () => clearInterval(minuteur.current), [])

  if (erreur) return <p className="dx-error" role="alert">{erreur}</p>
  if (!vue) return <p className="dx-note">Chargement…</p>

  const avecEmail = vue.recipients.filter((r) => r.email)
  const sansEmail = vue.recipients.filter((r) => !r.email)
  const deja = vue.summary.convoked

  async function envoyer() {
    try {
      const r = await api.send(file.id, vue.principals)
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
        <p className="ad-ok">Convocation envoyée à {deja} membre{deja > 1 ? 's' : ''}. Les réponses arrivent dans Résultats.</p>
      ) : (
        <p className="ag-pour">
          Pour : <strong>{avecEmail.length} membre{avecEmail.length > 1 ? 's' : ''}</strong> · par email ·{' '}
          <button type="button" className="ap-link" onClick={onChanger}>Changer</button>
        </p>
      )}
      {deja === 0 && sansEmail.length > 0 && (
        <p className="af-hint">Sans adresse email (à prévenir autrement) : {sansEmail.map((r) => r.name).join(', ')}.</p>
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
          <button type="button" className="dx-btn" disabled={!file.can_manage || !avecEmail.length} onClick={lancer}>
            Envoyer aux {avecEmail.length} membres
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
