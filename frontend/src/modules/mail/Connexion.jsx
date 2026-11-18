import { useState } from 'react'
import * as api from './api.js'
import { FOURNISSEURS } from './fournisseurs.js'

// Connecter la boîte du club (spec/modules/mail.md §4), depuis Admin ›
// Fonctionnalités, ligne Mail : l'adresse, la page du fournisseur pour créer
// le code, coller, « Connecter ». Gmail ou Infomaniak (Seb, 18 novembre).

export default function Connexion({ ecoleId, fournisseur, adresseInitiale, onConnecte }) {
  const f = FOURNISSEURS[fournisseur]
  const [etape, setEtape] = useState('adresse') // adresse | code | test | refus
  const [adresse, setAdresse] = useState(adresseInitiale ?? '')
  const [code, setCode] = useState('')
  const [erreur, setErreur] = useState(null)

  function ouvrir() {
    window.open(f.url(adresse.trim()), '_blank', 'noopener')
    setErreur(null)
    setEtape('code')
  }

  async function coller() {
    try {
      setCode(await navigator.clipboard.readText())
    } catch {
      setErreur('Collez avec un appui long dans la case.')
    }
  }

  async function connecter() {
    setErreur(null)
    setEtape('test')
    try {
      onConnecte(await api.connecter(ecoleId, adresse, code, fournisseur))
    } catch (e) {
      setErreur(e.message)
      setEtape(e.status === 422 ? 'refus' : 'code')
    }
  }

  if (etape === 'test') {
    return (
      <div className="mail__pile mail__centre">
        <div className="mail__roue" aria-hidden="true" />
        <p>Connexion à {f.nom}…</p>
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
        <button type="button" className="btn btn--primary mail__principal" onClick={ouvrir}>
          Rouvrir {f.nom}
        </button>
      </div>
    )
  }
  if (etape === 'code') {
    return (
      <div className="mail__pile">
        <p>{f.consigne}</p>
        <label className="mail__champ">
          <span>{f.code}</span>
          <span className="mail__ligne">
            <input
              value={code}
              onChange={(e) => setCode(e.target.value)}
              placeholder={f.exemple}
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
        <button type="button" className="mail__lien" onClick={ouvrir}>
          Rouvrir {f.nom}
        </button>
        <button type="button" className="btn btn--primary mail__principal" onClick={connecter} disabled={!code.trim()}>
          Connecter
        </button>
      </div>
    )
  }
  return (
    <div className="mail__pile">
      <label className="mail__champ">
        <span>Adresse {f.nom} du club</span>
        <input type="email" value={adresse} onChange={(e) => setAdresse(e.target.value)} autoComplete="off" />
      </label>
      <div className="mail__avertissement">
        <strong>Toute la boîte sera visible</strong>
        Les personnes qui ont le droit « Boîte mail du club » verront tous les mails de cette adresse et pourront
        écrire en son nom. Utilisez la boîte du club, jamais une boîte personnelle.
      </div>
      <ol className="mail__etapes">
        {f.etapes(adresse.trim()).map((e) => (
          <li key={e}>{e}</li>
        ))}
      </ol>
      <p className="mail__discret">{f.note}</p>
      <button
        type="button"
        className="btn btn--primary mail__principal"
        onClick={ouvrir}
        disabled={!/^\S+@\S+\.\S+$/.test(adresse.trim())}
      >
        Ouvrir {f.nom}
      </button>
    </div>
  )
}
