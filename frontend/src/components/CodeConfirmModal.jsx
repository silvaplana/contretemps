import { useState } from 'react'
import { ROLE_LABEL } from '../data/roles.js'
import Modal from './Modal.jsx'

// Modale de confirmation par code, affichée quand un profil famille bascule
// vers un rôle de rang supérieur (voir spec/SPEC.md §2.2). `onConfirm`
// (async, voir Header.jsx) vérifie le VRAI code d'accès côté backend
// (auth.js: confirmerBascule) — reste ouverte avec un message d'erreur si
// le code est faux, plutôt que de fermer en silence (maquette d'avant :
// n'importe quel code non vide était accepté).
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
      setErreur(err.message || 'Code incorrect')
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Modal
      title={`Code ${ROLE_LABEL[profil.type]}`}
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
        privilège : le code d’accès est redemandé.
      </p>
      <input
        type="password"
        autoFocus
        value={code}
        onChange={(e) => setCode(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && code && !enCours && confirmer()}
        placeholder="Code d’accès"
      />
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}
