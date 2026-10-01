import { useState } from 'react'
import { ROLE_LABEL } from '../data/roles.js'
import Modal from './Modal.jsx'

// Modale de confirmation par mot de passe, affichée quand un profil famille
// bascule vers un rôle de rang supérieur (voir spec/SPEC.md §2.2 : ex. un
// enfant sur le téléphone d'un parent admin). `onConfirm` (async, voir
// Header.jsx) fait vérifier le mot de passe par le serveur (auth.js :
// basculer) — reste ouverte avec un message d'erreur s'il est faux.
export default function CodeConfirmModal({ profil, onConfirm, onClose }) {
  const [code, setCode] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')

  async function confirmer() {
    setErreur('')
    setEnCours(true)
    try {
      await onConfirm(code)
    } catch (err) {
      setErreur(err.message || 'Mot de passe incorrect')
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Modal
      title="Mot de passe"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!code || enCours}
          onClick={confirmer}
        >
          Confirmer
        </button>
      }
    >
      <p className="muted">
        Passer à {profil.prenom} {profil.nom} ({ROLE_LABEL[profil.type]}) est une montée en
        privilège : votre mot de passe est redemandé.
      </p>
      <input
        type="password"
        autoFocus
        value={code}
        onChange={(e) => setCode(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && code && !enCours && confirmer()}
        autoComplete="current-password"
        placeholder="Mot de passe"
      />
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}
