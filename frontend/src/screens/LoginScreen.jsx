import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import Logo from '../components/Logo.jsx'
import Modal from '../components/Modal.jsx'
import * as auth from '../api/auth.js'
import * as notificationsApi from '../api/notifications.js'
import { ROLE_LABEL } from '../data/roles.js'

// Écran de connexion (voir spec/SPEC.md §2.2) : une seule page pour toutes
// les écoles. Nom prénom ou email, et le mot de passe personnel (créé à
// partir d'une invitation reçue par mail). Créer une école est réservé au
// Super User (décision du 2026-10-01, voir ChoixEcoleScreen.jsx).
export default function LoginScreen({ onLogin }) {
  const [identifiant, setIdentifiant] = useState('')
  const [motDePasse, setMotDePasse] = useState('')
  const [showOubli, setShowOubli] = useState(false)
  // Plusieurs écoles possibles pour cet identifiant et ce mot de passe
  // (cas rare) : la liste à proposer.
  const [choix, setChoix] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [visible, setVisible] = useState(false)

  async function connecter(compteId = null, permissionNotifications = null) {
    setErreur('')
    setEnCours(true)
    try {
      const resultat = await auth.login({ identifiant, motDePasse, compteId })
      if (resultat.choix) {
        setChoix(resultat.choix)
        return
      }
      setChoix(null)
      onLogin(resultat)
      notificationsApi.abonnerSiAccepte(permissionNotifications, resultat.compte.id)
    } catch (err) {
      setChoix(null)
      setErreur(err.message || 'Connexion impossible')
    } finally {
      setEnCours(false)
    }
  }

  function seConnecter(e) {
    e.preventDefault()
    // Premier lancement sur cet appareil : notifications proposées pendant
    // CE clic (le navigateur l'exige), avant tout `await` — voir
    // api/notifications.js : proposerAuPremierLancement.
    connecter(null, notificationsApi.proposerAuPremierLancement())
  }

  return (
    <div className="login-screen">
      <div className="login-screen__brand">
        <Logo size={110} />
        <h1>Contretemps</h1>
        <p>Gestion d'école de danse du cours au gala</p>
      </div>

      <form className="login-screen__form" onSubmit={seConnecter}>
        <label htmlFor="login-identifiant">Nom Prénom ou Email</label>
        <input
          id="login-identifiant"
          type="text"
          autoComplete="username"
          value={identifiant}
          onChange={(e) => setIdentifiant(e.target.value)}
          placeholder="Julia Dho ou jd@contretemps.fr"
        />

        <label htmlFor="login-mot-de-passe">Mot de passe</label>
        <ChampMotDePasse
          id="login-mot-de-passe"
          autoComplete="current-password"
          value={motDePasse}
          onChange={setMotDePasse}
          visible={visible}
          setVisible={setVisible}
        />

        {erreur && <p className="login-screen__erreur">{erreur}</p>}

        <button type="submit" className="btn btn--primary btn--block" disabled={enCours}>
          Se connecter
        </button>
        <button type="button" className="btn btn--link" onClick={() => setShowOubli(true)}>
          Mot de passe oublié ?
        </button>
      </form>

      {showOubli && <MotDePasseOublieModal identifiantInitial={identifiant} onClose={() => setShowOubli(false)} />}

      {choix && (
        <Modal title="Choisissez votre école" onClose={() => setChoix(null)}>
          <div className="checkbox-list">
            {choix.map((c) => (
              <button
                key={c.compteId}
                type="button"
                className="btn btn--secondary btn--block"
                disabled={enCours}
                onClick={() => connecter(c.compteId)}
              >
                {c.ecoleNom ?? 'Toutes les écoles'} ({ROLE_LABEL[c.role] ?? c.role})
              </button>
            ))}
          </div>
        </Modal>
      )}
    </div>
  )
}

// Champ mot de passe avec l'œil pour l'afficher (voir aussi
// CreerMotDePasseScreen.jsx et Profil).
export function ChampMotDePasse({ id, value, onChange, visible, setVisible, autoComplete, placeholder }) {
  return (
    <div className="login-screen__champ-code">
      <input
        id={id}
        type={visible ? 'text' : 'password'}
        autoComplete={autoComplete}
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
      <button
        type="button"
        className="icon-btn login-screen__toggle-code"
        onClick={() => setVisible((v) => !v)}
        aria-label={visible ? 'Masquer le mot de passe' : 'Afficher le mot de passe'}
      >
        <Icon name={visible ? 'eyeOff' : 'eye'} size={20} />
      </button>
    </div>
  )
}

// « Mot de passe oublié ? » (§2.2) : toujours le même message, qu'un compte
// existe ou non, pour ne pas révéler qui est inscrit.
function MotDePasseOublieModal({ identifiantInitial, onClose }) {
  const [identifiant, setIdentifiant] = useState(identifiantInitial)
  const [envoye, setEnvoye] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  async function demander() {
    setErreur('')
    setEnCours(true)
    try {
      await auth.motDePasseOublie(identifiant)
      setEnvoye(true)
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  if (envoye) {
    return (
      <Modal title="Mot de passe oublié" onClose={onClose}>
        <p>
          Si ce compte existe, un lien vient d’être envoyé à son adresse email. Il est valable 1 heure.
        </p>
        <button type="button" className="btn btn--primary btn--block" onClick={onClose}>
          Fermer
        </button>
      </Modal>
    )
  }

  return (
    <Modal
      title="Mot de passe oublié"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={enCours || !identifiant.trim()}
          onClick={demander}
        >
          Recevoir un lien
        </button>
      }
    >
      <label htmlFor="oubli-identifiant">Nom Prénom ou Email</label>
      <input
        id="oubli-identifiant"
        type="text"
        value={identifiant}
        onChange={(e) => setIdentifiant(e.target.value)}
        placeholder="Julia Dho ou jd@contretemps.fr"
      />
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}
