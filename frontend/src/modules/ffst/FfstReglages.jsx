import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Icon from '../../components/Icon.jsx'
import * as api from './api.js'

// La connexion au site de la FFST (spec/modules/ffst.md §2), sur la ligne
// FFST de Fonctionnalités, comme HelloAsso : une petite ligne d'état,
// « Connecter » ou « Voir », puis l'écran des identifiants ou l'écran
// « Connecté ». Cocher la case sans connexion ouvre l'écran des identifiants.
// Écrans hors de la ligne (portail) : la ligne est l'étiquette de la case.

const date = (iso) => new Date(iso).toLocaleDateString('fr-FR')

function Identifiants({ ecoleId, onEnregistre }) {
  const [champs, setChamps] = useState({ part1: '', part2: '', part3: '', password: '' })
  const [voir, setVoir] = useState(false)
  const [test, setTest] = useState(null) // null | 'run' | { ok, … }
  const identifiants = { ...champs, part1: champs.part1.trim(), part2: champs.part2.trim(), part3: champs.part3.trim() }
  const complet = identifiants.part1 && identifiants.part2 && identifiants.part3 && champs.password

  const changer = (cle) => (e) => {
    setChamps((c) => ({ ...c, [cle]: e.target.value }))
    setTest(null)
  }

  async function lancer(action) {
    setTest('run')
    try {
      const resultat = await action(ecoleId, identifiants)
      if (action === api.enregistrer) onEnregistre()
      else setTest({ ok: true, ...resultat })
    } catch (e) {
      setTest({ ok: false, message: e.message })
    }
  }

  return (
    <>
      <p>L’identifiant et le mot de passe du club sur le site des licences de la FFST.</p>
      <div className="form-fields">
        <label htmlFor="ffst-part1">Identifiant du club, en trois parties comme sur le site</label>
        <div className="ffst__identifiant">
          {['part1', 'part2', 'part3'].map((cle, i) => (
            <input
              key={cle}
              id={i === 0 ? 'ffst-part1' : undefined}
              aria-label={`Partie ${i + 1} de l’identifiant`}
              className="field-input"
              inputMode="numeric"
              autoComplete="off"
              spellCheck="false"
              value={champs[cle]}
              onChange={changer(cle)}
            />
          ))}
        </div>
        <label htmlFor="ffst-password">Mot de passe</label>
        <div className="helloasso__cle">
          <input
            id="ffst-password"
            className="field-input"
            type={voir ? 'text' : 'password'}
            // « new-password » : le navigateur ne remplit pas tout seul les
            // identifiants de connexion à l'appli (l'email arrivait dans la
            // 3e case de l'identifiant, Seb 18/11).
            autoComplete="new-password"
            spellCheck="false"
            value={champs.password}
            onChange={changer('password')}
          />
          <button
            type="button"
            className="icon-btn"
            aria-label={voir ? 'Cacher le mot de passe' : 'Afficher le mot de passe'}
            onClick={() => setVoir((v) => !v)}
          >
            <Icon name={voir ? 'eyeOff' : 'eye'} size={22} />
          </button>
        </div>
      </div>
      {test === 'run' && <div className="helloasso__resultat">Connexion au site de la FFST…</div>}
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
            <dt>Licenciés cette saison</dt>
            <dd>{test.licensees}</dd>
          </dl>
        </div>
      )}
      {test?.ok ? (
        <button type="button" className="btn btn--primary btn--block creer-saison__principal" onClick={() => lancer(api.enregistrer)}>
          Enregistrer
        </button>
      ) : (
        <button
          type="button"
          className="btn btn--primary btn--block creer-saison__principal"
          disabled={!complet || test === 'run'}
          onClick={() => lancer(api.tester)}
        >
          Tester la connexion
        </button>
      )}
      <p className="creer-saison__note">
        Le mot de passe est gardé chiffré. Seuls l’administrateur principal et le super user voient cet écran.
      </p>
    </>
  )
}

// Les réglages de l'école pour une demande (spec §2), écrits pour ASC dans
// Sambo Admin : la discipline d'une nouvelle demande, la commune de naissance
// quand celle de l'adhérent n'est pas trouvée, « Droit à l'image ».
function Reglages({ ecoleId, etat, onEnregistre }) {
  const [r, setR] = useState(etat.settings)
  const [message, setMessage] = useState(null)
  const changer = (cle, valeur) => {
    setR((x) => ({ ...x, [cle]: valeur }))
    setMessage(null)
  }

  async function enregistrer() {
    try {
      onEnregistre(await api.reglages(ecoleId, r))
      setMessage({ ok: true, texte: '✓ Réglages enregistrés' })
    } catch (e) {
      setMessage({ ok: false, texte: e.message })
    }
  }

  return (
    <div className="helloasso__saison">
      <p className="helloasso__titre">Pour les demandes de licence</p>
      <div className="form-fields">
        <label htmlFor="ffst-discipline">Discipline d’une nouvelle demande, comme sur le site</label>
        <input
          id="ffst-discipline"
          className="field-input"
          placeholder="ex. 0470-SAMBO"
          value={r.discipline}
          onChange={(e) => changer('discipline', e.target.value)}
        />
        <label htmlFor="ffst-commune">Commune de naissance si celle de l’adhérent n’est pas trouvée</label>
        <input
          id="ffst-commune"
          className="field-input"
          placeholder={etat.school_town ?? ''}
          value={r.default_birth_town}
          onChange={(e) => changer('default_birth_town', e.target.value)}
        />
        <label className="ffst__case">
          <input type="checkbox" checked={r.image_rights} onChange={(e) => changer('image_rights', e.target.checked)} />
          Cocher « Droit à l’image » sur une nouvelle demande
        </label>
      </div>
      <button type="button" className="btn btn--secondary btn--block" onClick={enregistrer}>
        Enregistrer les réglages
      </button>
      {message && (
        <div
          className={`helloasso__resultat ${message.ok ? 'helloasso__resultat--ok' : 'helloasso__resultat--erreur'}`}
          role="status"
        >
          <strong>{message.texte}</strong>
        </div>
      )}
    </div>
  )
}

function Connecte({ ecoleId, etat, onChangerIdentifiants, onEtat }) {
  const [test, setTest] = useState(null)

  async function retester() {
    setTest('run')
    try {
      setTest({ ok: true, ...(await api.retester(ecoleId)) })
    } catch (e) {
      setTest({ ok: false, message: e.message })
    }
  }

  return (
    <>
      <div className="helloasso__resultat helloasso__resultat--ok">
        <strong>✓ Connecté</strong>
        <dl>
          <dt>Identifiant</dt>
          <dd>{etat.login}</dd>
          <dt>Depuis le</dt>
          <dd>{date(etat.connected_at)}</dd>
        </dl>
      </div>
      <button
        type="button"
        className="btn btn--primary btn--block creer-saison__principal"
        disabled={test === 'run'}
        onClick={retester}
      >
        Tester la connexion
      </button>
      {test === 'run' && <div className="helloasso__resultat">Connexion au site de la FFST…</div>}
      {test?.ok && (
        <div className="helloasso__resultat helloasso__resultat--ok" role="status">
          <strong>✓ La connexion marche toujours</strong>
          <span>{test.licensees} licenciés cette saison</span>
        </div>
      )}
      {test?.ok === false && (
        <div className="helloasso__resultat helloasso__resultat--erreur" role="alert">
          <strong>La connexion n’a pas marché</strong>
          <span>{test.message}</span>
        </div>
      )}
      <Reglages ecoleId={ecoleId} etat={etat} onEnregistre={onEtat} />
      <button type="button" className="creer-saison__lien" onClick={onChangerIdentifiants}>
        Changer les identifiants
      </button>
    </>
  )
}

export default function FfstReglages({ ecole, enabled }) {
  const [etat, setEtat] = useState(null)
  const [ecran, setEcran] = useState(null) // null | 'identifiants' | 'connecte'
  const [toast, setToast] = useState(null)
  const avant = useRef(enabled)
  const minuteur = useRef(null)

  async function relire() {
    const lu = await api.etat(ecole.id).catch(() => null)
    setEtat(lu)
    return lu
  }

  // Module éteint : ses routes répondent « introuvable », rien à lire.
  useEffect(() => {
    const vientDEtreCoche = enabled && !avant.current
    avant.current = enabled
    if (!enabled) {
      setEtat(null)
      return
    }
    relire().then((lu) => {
      if (vientDEtreCoche && lu && !lu.connected) setEcran('identifiants')
    })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecole.id, enabled])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  async function enregistre() {
    await relire()
    setEcran(null)
    clearTimeout(minuteur.current)
    setToast('Site de la FFST connecté')
    minuteur.current = setTimeout(() => setToast(null), 4000)
  }

  const connecte = etat?.connected
  const petit = connecte
    ? `Connecté, identifiant ${etat.login}`
    : enabled
      ? 'Pas encore connecté'
      : 'Licences de la fédération'

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
            setEcran(connecte ? 'connecte' : 'identifiants')
          }}
        >
          {connecte ? 'Voir' : 'Connecter'}
        </button>
      )}
      {ecran &&
        createPortal(
          <div className="creer-saison" role="dialog" aria-label="Site de la FFST">
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
              <h2 className="creer-saison__titre">{ecran === 'identifiants' ? 'Connecter le site de la FFST' : 'Site de la FFST'}</h2>
            </div>
            <div className="creer-saison__corps connexion-ecran">
              {ecran === 'identifiants' ? (
                <Identifiants ecoleId={ecole.id} onEnregistre={enregistre} />
              ) : (
                <Connecte
                  ecoleId={ecole.id}
                  etat={etat}
                  onEtat={setEtat}
                  onChangerIdentifiants={() => setEcran('identifiants')}
                />
              )}
            </div>
          </div>,
          document.body,
        )}
      {toast &&
        createPortal(
          <div className="admin-groupes__toast" role="status">
            <span>{toast}</span>
          </div>,
          document.body,
        )}
    </>
  )
}
