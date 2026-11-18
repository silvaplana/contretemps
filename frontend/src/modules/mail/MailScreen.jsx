import { useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import MenuEntete from '../../components/MenuEntete.jsx'
import * as api from './api.js'
import './mail.css'

// Messages › Mail (spec/modules/mail.md §4) : connecter la boîte Gmail du
// club (Administrateur principal), puis la boîte. Étape 1 : la connexion ;
// la liste des mails vient à l'étape 2.

// Page Google des mots de passe des applications (le compte doit avoir la
// validation en deux étapes ; Google interdit de créer le code à notre place).
const GOOGLE_URL = 'https://myaccount.google.com/apppasswords'
const ANNULER_MS = 10000

function Etapes() {
  return (
    <ol className="mail__etapes">
      <li>Google s'ouvre : appuyez sur Créer.</li>
      <li>Copiez le code de 16 lettres.</li>
      <li>Revenez ici et collez-le.</li>
    </ol>
  )
}

function Connexion({ ecoleId, adresseInitiale, onConnecte }) {
  const [etape, setEtape] = useState('adresse') // adresse | code | test | refus
  const [adresse, setAdresse] = useState(adresseInitiale ?? '')
  const [code, setCode] = useState('')
  const [erreur, setErreur] = useState(null)

  function ouvrirGoogle() {
    window.open(GOOGLE_URL, '_blank', 'noopener')
    setErreur(null)
    setEtape('code')
  }

  async function coller() {
    try {
      setCode(await navigator.clipboard.readText())
    } catch {
      setErreur('Collez le code avec un appui long dans la case.')
    }
  }

  async function connecter() {
    setErreur(null)
    setEtape('test')
    try {
      onConnecte(await api.connecter(ecoleId, adresse, code))
    } catch (e) {
      setErreur(e.message)
      setEtape(e.status === 422 ? 'refus' : 'code')
    }
  }

  if (etape === 'test') {
    return (
      <div className="mail__pile mail__centre">
        <div className="mail__roue" aria-hidden="true" />
        <p>Connexion à Gmail…</p>
      </div>
    )
  }
  if (etape === 'refus') {
    return (
      <div className="mail__pile">
        <h2 className="mail__titre">Code refusé</h2>
        <p className="mail__centre">{erreur}</p>
        <button type="button" className="mail__lien" onClick={() => setEtape('code')}>
          Recoller le code
        </button>
        <button type="button" className="btn btn--primary mail__principal" onClick={ouvrirGoogle}>
          Rouvrir Google
        </button>
      </div>
    )
  }
  if (etape === 'code') {
    return (
      <div className="mail__pile">
        <p>Collez le code de 16 lettres donné par Google.</p>
        <label className="mail__champ">
          <span>Code Google</span>
          <span className="mail__ligne">
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder="xxxx xxxx xxxx xxxx"
              autoComplete="off"
              autoCapitalize="none"
              spellCheck={false}
            />
            <button type="button" className="btn btn--secondary" onClick={coller}>
              Coller
            </button>
          </span>
        </label>
        <p className="mail__discret">Pour la boîte {adresse}.</p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        <button type="button" className="mail__lien" onClick={ouvrirGoogle}>
          Rouvrir Google
        </button>
        <button
          type="button"
          className="btn btn--primary mail__principal"
          onClick={connecter}
          disabled={!code.trim()}
        >
          Connecter
        </button>
      </div>
    )
  }
  return (
    <div className="mail__pile">
      <p>Connectez la boîte Gmail du club pour lire et envoyer ses mails depuis l'appli.</p>
      <label className="mail__champ">
        <span>Adresse Gmail du club</span>
        <input type="email" value={adresse} onChange={(e) => setAdresse(e.target.value)} autoComplete="off" />
      </label>
      <div className="mail__avertissement">
        <strong>Toute la boîte sera visible</strong>
        Les personnes qui ont le droit « Boîte mail du club » verront tous les mails de cette adresse et
        pourront écrire en son nom. Utilisez la boîte du club, jamais une boîte personnelle.
      </div>
      <Etapes />
      <p className="mail__discret">
        Si Google demande d'abord d'activer la validation en deux étapes, suivez ses indications : il faut un
        téléphone pour recevoir un code.
      </p>
      <button
        type="button"
        className="btn btn--primary mail__principal"
        onClick={ouvrirGoogle}
        disabled={!/^\S+@\S+\.\S+$/.test(adresse.trim())}
      >
        Ouvrir Google
      </button>
    </div>
  )
}

export default function MailScreen({ ecoleId, etat, onEtat }) {
  const [reconnecter, setReconnecter] = useState(false)
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)

  // « Déconnecter la boîte » : effacée au bout de 10 s, sauf Annuler.
  function deconnecter() {
    const avant = etat
    onEtat({ ...etat, connected: false, address: null, cut: false })
    clearTimeout(minuteur.current)
    minuteur.current = setTimeout(() => {
      setToast(null)
      api.deconnecter(ecoleId).catch(() => onEtat(avant))
    }, ANNULER_MS)
    setToast({ texte: 'Boîte déconnectée', avant })
  }

  function annuler() {
    clearTimeout(minuteur.current)
    onEtat(toast.avant)
    setToast(null)
  }

  let corps
  if (!etat.connected || reconnecter) {
    corps = etat.can_connect ? (
      <Connexion
        ecoleId={ecoleId}
        adresseInitiale={etat.address}
        onConnecte={(nouveau) => {
          setReconnecter(false)
          onEtat(nouveau)
        }}
      />
    ) : (
      <div className="mail__pile">
        <p>La boîte mail du club n'est pas encore connectée.</p>
        <p className="mail__discret">Seul l'Administrateur principal peut la connecter.</p>
      </div>
    )
  } else {
    corps = (
      <div className="mail__pile">
        {etat.cut && (
          <div className="mail__alerte" role="alert">
            <strong>La boîte mail n'est plus connectée</strong>
            Google a coupé l'accès, souvent après un changement du mot de passe du compte.
            {etat.can_connect ? (
              <button type="button" className="btn btn--primary" onClick={() => setReconnecter(true)}>
                Reconnecter
              </button>
            ) : (
              ' L’Administrateur principal doit la reconnecter.'
            )}
          </div>
        )}
        <p>
          Boîte connectée : <strong>{etat.address}</strong>
        </p>
        <p className="mail__discret">Les mails du club s'afficheront ici.</p>
      </div>
    )
  }

  const menu = etat.connected
    ? [
        { label: etat.address, icon: 'mail', onClick: () => {} },
        ...(etat.can_connect ? [{ label: 'Déconnecter la boîte', icon: 'logout', onClick: () => deconnecter() }] : []),
      ]
    : null

  return (
    <div className="mail">
      {menu && <MenuEntete label="Plus d'actions" actions={menu} />}
      {corps}
      {toast &&
        createPortal(
          <div className="admin-groupes__toast" role="status">
            <span>{toast.texte}</span>
            <button type="button" onClick={annuler}>
              Annuler
            </button>
          </div>,
          document.body,
        )}
    </div>
  )
}
