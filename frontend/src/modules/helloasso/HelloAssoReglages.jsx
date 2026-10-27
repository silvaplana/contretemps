import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'

// La connexion HelloAsso de l'école (spec/modules/helloasso.md §2, maquette
// « Connexion HelloAsso »), sur la ligne HelloAsso de Fonctionnalités : une
// petite ligne d'état, « Connecter » ou « Voir », puis l'écran des clés ou
// l'écran « Connecté ». Cocher la case sans connexion ouvre l'écran des clés.
// Écrans et toast hors de la ligne (portail) : la ligne est l'étiquette de la
// case, un clic dedans la cocherait.

const ANNULER_MS = 10000

const date = (iso) => new Date(iso).toLocaleDateString('fr-FR')

function Cles({ ecoleId, onEnregistre }) {
  const [clientId, setClientId] = useState('')
  const [secret, setSecret] = useState('')
  const [voir, setVoir] = useState(false)
  const [test, setTest] = useState(null) // null | 'run' | { ok, … }
  const cles = { client_id: clientId.trim(), client_secret: secret.trim() }

  async function tester() {
    setTest('run')
    try {
      setTest({ ok: true, ...(await api.tester(ecoleId, cles)) })
    } catch (e) {
      setTest({ ok: false, message: e.message })
    }
  }

  async function enregistrer() {
    setTest('run')
    try {
      await api.enregistrer(ecoleId, cles)
      onEnregistre()
    } catch (e) {
      setTest({ ok: false, message: e.message })
    }
  }

  return (
    <>
      <ol className="helloasso__guide">
        <li>
          <a href="https://admin.helloasso.com" target="_blank" rel="noreferrer">
            Ouvrir mon espace HelloAsso ↗
          </a>
        </li>
        <li>
          Menu <b>Mon compte</b> &gt; <b>Intégrations et API</b>.
        </li>
        <li>Copiez les deux clés, puis collez-les ici.</li>
      </ol>
      <div className="form-fields">
        <label htmlFor="helloasso-id">Mon clientId</label>
        <input
          id="helloasso-id"
          className="field-input"
          autoComplete="off"
          spellCheck="false"
          value={clientId}
          placeholder="ex. 3f9c2a…"
          onChange={(e) => {
            setClientId(e.target.value)
            setTest(null)
          }}
        />
        <label htmlFor="helloasso-secret">Mon clientSecret</label>
        <div className="helloasso__cle">
          <input
            id="helloasso-secret"
            className="field-input"
            type={voir ? 'text' : 'password'}
            autoComplete="off"
            spellCheck="false"
            value={secret}
            onChange={(e) => {
              setSecret(e.target.value)
              setTest(null)
            }}
          />
          <button
            type="button"
            className="icon-btn"
            aria-label={voir ? 'Cacher la clé' : 'Afficher la clé'}
            onClick={() => setVoir((v) => !v)}
          >
            <Icon name={voir ? 'eyeOff' : 'eye'} size={22} />
          </button>
        </div>
      </div>
      {test === 'run' && <div className="helloasso__resultat">Test en cours…</div>}
      {test?.ok === false && (
        <div className="helloasso__resultat helloasso__resultat--erreur" role="alert">
          <strong>La connexion n’a pas marché</strong>
          <span>{test.message}</span>
        </div>
      )}
      {test?.ok && (
        <div className="helloasso__resultat helloasso__resultat--ok" role="status">
          <strong>✓ Connexion réussie</strong>
          <dl>
            <dt>Association</dt>
            <dd>{test.name}</dd>
            <dt>Formulaires d’adhésion</dt>
            <dd>{test.forms.length}</dd>
          </dl>
        </div>
      )}
      {test?.ok ? (
        <button type="button" className="btn btn--primary btn--block creer-saison__principal" onClick={enregistrer}>
          Enregistrer
        </button>
      ) : (
        <button
          type="button"
          className="btn btn--primary btn--block creer-saison__principal"
          disabled={!cles.client_id || !cles.client_secret || test === 'run'}
          onClick={tester}
        >
          Tester la connexion
        </button>
      )}
      <p className="creer-saison__note">
        Les clés sont gardées chiffrées. Seuls l’administrateur principal et le super user voient cet écran.
      </p>
    </>
  )
}

function Connecte({ ecoleId, etat, onChangerCles, onDeconnecter }) {
  const [formulaires, setFormulaires] = useState(null)
  const [test, setTest] = useState(null)

  async function retester(premier) {
    setTest('run')
    try {
      const resultat = await api.retester(ecoleId)
      setFormulaires(resultat.forms)
      setTest(premier ? null : { ok: true })
    } catch (e) {
      setTest({ ok: false, message: e.message })
    }
  }

  useEffect(() => {
    retester(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return (
    <>
      <div className="helloasso__resultat helloasso__resultat--ok">
        <strong>✓ Connecté</strong>
        <dl>
          <dt>Association</dt>
          <dd>{etat.org_name}</dd>
          <dt>Depuis le</dt>
          <dd>{date(etat.connected_at)}</dd>
        </dl>
      </div>
      {formulaires && (
        <>
          <p className="helloasso__titre">Formulaires d’adhésion trouvés</p>
          <ul className="helloasso__formulaires">
            {formulaires.map((f) => (
              <li key={f}>{f}</li>
            ))}
          </ul>
          <p className="creer-saison__note">
            Le formulaire de chaque saison se choisit en créant la saison, à l’étape des élèves.
          </p>
        </>
      )}
      <button
        type="button"
        className="btn btn--primary btn--block creer-saison__principal"
        disabled={test === 'run'}
        onClick={() => retester(false)}
      >
        Tester la connexion
      </button>
      {test?.ok && (
        <div className="helloasso__resultat helloasso__resultat--ok" role="status">
          <strong>✓ La connexion marche toujours</strong>
        </div>
      )}
      {test?.ok === false && (
        <div className="helloasso__resultat helloasso__resultat--erreur" role="alert">
          <strong>La connexion n’a pas marché</strong>
          <span>{test.message}</span>
        </div>
      )}
      <button type="button" className="creer-saison__lien" onClick={onChangerCles}>
        Changer les clés
      </button>
      <button type="button" className="creer-saison__lien" onClick={onDeconnecter}>
        Déconnecter
      </button>
    </>
  )
}

export default function HelloAssoReglages({ ecole, enabled, onEnabledChange }) {
  const [etat, setEtat] = useState(null)
  const [ecran, setEcran] = useState(null) // null | 'cles' | 'connecte'
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)
  const avant = useRef(enabled)
  const restauration = useRef(false) // « Annuler » d'une déconnexion en cours

  async function relire() {
    const lu = await api.etat(ecole.id).catch(() => null)
    setEtat(lu)
    return lu
  }

  // Module éteint : ses routes répondent « introuvable », rien à lire.
  // Cocher la case sans connexion ouvre directement l'écran des clés.
  useEffect(() => {
    const vientDEtreCoche = enabled && !avant.current
    avant.current = enabled
    if (!enabled) {
      setEtat(null)
      return
    }
    relire().then((lu) => {
      if (vientDEtreCoche && !restauration.current && lu && !lu.connected) setEcran('cles')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecole.id, enabled])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  function montrerToast(texte, annuler) {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), ANNULER_MS)
  }

  async function enregistre() {
    await relire()
    setEcran(null)
    montrerToast('HelloAsso connecté')
  }

  async function deconnecter() {
    await api.deconnecter(ecole.id)
    await onEnabledChange(false)
    setEcran(null)
    montrerToast('HelloAsso déconnecté', async () => {
      restauration.current = true
      try {
        await onEnabledChange(true)
        await api.reprendre(ecole.id)
        await relire()
      } finally {
        restauration.current = false
      }
    })
  }

  const connecte = etat?.connected
  const petit = connecte
    ? `Connecté à ${etat.org_name}`
    : enabled
      ? 'Pas encore connecté'
      : 'Adhésions et paiements en ligne'

  return (
    <>
      <small className="helloasso__etat">{petit}</small>
      {enabled && etat && (
        <button
          type="button"
          className="helloasso__lien"
          onClick={(e) => {
            // Le bouton est dans l'étiquette de la case : ne pas la décocher.
            e.preventDefault()
            setEcran(connecte ? 'connecte' : 'cles')
          }}
        >
          {connecte ? 'Voir' : 'Connecter'}
        </button>
      )}
      {ecran &&
        createPortal(
          <div
            className="creer-saison"
            role="dialog"
            aria-label={ecran === 'cles' ? 'Connecter HelloAsso' : 'HelloAsso'}
          >
            <div className="thread-screen__header">
              <button
                type="button"
                className="icon-btn"
                onClick={(e) => {
                  e.preventDefault()
                  setEcran(null)
                }}
                aria-label="Retour"
              >
                <Icon name="chevronLeft" size={22} />
              </button>
              <h2 className="creer-saison__titre">{ecran === 'cles' ? 'Connecter HelloAsso' : 'HelloAsso'}</h2>
            </div>
            <div className="creer-saison__corps">
              {ecran === 'cles' ? (
                <Cles ecoleId={ecole.id} onEnregistre={enregistre} />
              ) : (
                <Connecte
                  ecoleId={ecole.id}
                  etat={etat}
                  onChangerCles={() => setEcran('cles')}
                  onDeconnecter={() => deconnecter().catch(() => null)}
                />
              )}
            </div>
          </div>,
          document.body,
        )}
      {toast &&
        createPortal(
          <div className="admin-groupes__toast" role="status">
            <span>{toast.texte}</span>
            {toast.annuler && (
              <button
                type="button"
                onClick={() => {
                  clearTimeout(minuteur.current)
                  setToast(null)
                  toast.annuler().catch(() => null)
                }}
              >
                Annuler
              </button>
            )}
          </div>,
          document.body,
        )}
    </>
  )
}
