import { useEffect, useState } from 'react'
import * as auth from '../api/auth.js'
import * as notificationsApi from '../api/notifications.js'
import Logo from '../components/Logo.jsx'
import { ChampMotDePasse } from './LoginScreen.jsx'

const LONGUEUR_MIN = 8

// « Créer mon mot de passe » (lien d'invitation) et « Nouveau mot de passe »
// (lien de mot de passe oublié) — voir spec/SPEC.md §2.2. Même écran :
// email affiché (non modifiable), prénoms des profils, mot de passe saisi
// deux fois. Son ouverture signale au serveur que le lien a été cliqué
// (suivi de l'invitation). À la validation, la personne est connectée
// directement.
export default function CreerMotDePasseScreen({ jeton, onConnecte, onAbandon }) {
  const [lien, setLien] = useState(null)
  const [lienInvalide, setLienInvalide] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [visible, setVisible] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    let annule = false
    auth
      .lireLien(jeton)
      .then((l) => !annule && setLien(l))
      .catch((err) => !annule && setLienInvalide(err.message))
    return () => {
      annule = true
    }
  }, [jeton])

  const invitation = lien?.type === 'invitation'
  const tropCourt = motDePasse.length < LONGUEUR_MIN
  const different = confirmation !== motDePasse

  async function valider(e) {
    e.preventDefault()
    // Notifications proposées pendant CE clic (voir LoginScreen.jsx).
    const permissionNotifications = notificationsApi.proposerAuPremierLancement()
    setErreur('')
    setEnCours(true)
    try {
      const resultat = await auth.definirMotDePasse(jeton, motDePasse)
      if (resultat) notificationsApi.abonnerSiAccepte(permissionNotifications, resultat.compte.id)
      onConnecte(resultat)
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <div className="login-screen">
      <div className="login-screen__brand">
        <Logo size={90} />
        <h1>{lien && !invitation ? 'Nouveau mot de passe' : 'Créer mon mot de passe'}</h1>
        {lien?.ecoleNom && <p>{lien.ecoleNom}</p>}
      </div>

      {lienInvalide ? (
        <div className="login-screen__form">
          <p className="login-screen__erreur">{lienInvalide}</p>
          <p className="muted">
            Sur l’écran de connexion, « Mot de passe oublié ? » vous envoie un nouveau lien.
          </p>
          <button type="button" className="btn btn--primary btn--block" onClick={onAbandon}>
            Aller à l’écran de connexion
          </button>
        </div>
      ) : !lien ? (
        <p className="muted">Vérification du lien…</p>
      ) : (
        <form className="login-screen__form" onSubmit={valider}>
          {lien.destinataire && (
            <p>
              Bonjour <strong>{lien.destinataire}</strong>,{' '}
              {invitation ? 'créez votre mot de passe.' : 'choisissez votre nouveau mot de passe.'}
            </p>
          )}
          <label htmlFor="activation-email">Email</label>
          <input id="activation-email" type="email" autoComplete="username" value={lien.email} readOnly />
          {lien.prenoms.length > 1 && <p className="muted">Profils : {lien.prenoms.join(', ')}</p>}

          <label htmlFor="activation-mdp">Mot de passe (au moins {LONGUEUR_MIN} caractères)</label>
          <ChampMotDePasse
            id="activation-mdp"
            autoComplete="new-password"
            value={motDePasse}
            onChange={setMotDePasse}
            visible={visible}
            setVisible={setVisible}
          />
          <label htmlFor="activation-mdp2">Mot de passe, à nouveau</label>
          <ChampMotDePasse
            id="activation-mdp2"
            autoComplete="new-password"
            value={confirmation}
            onChange={setConfirmation}
            visible={visible}
            setVisible={setVisible}
          />
          {confirmation && different && (
            <p className="login-screen__erreur">Les deux mots de passe ne correspondent pas.</p>
          )}
          {erreur && <p className="login-screen__erreur">{erreur}</p>}

          <button
            type="submit"
            className="btn btn--primary btn--block"
            disabled={enCours || tropCourt || different}
          >
            Valider
          </button>
        </form>
      )}
    </div>
  )
}
