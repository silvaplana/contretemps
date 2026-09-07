import { useState } from 'react'
import { ROLE_LABEL } from '../data/roles.js'
import Modal from './Modal.jsx'

// Modale de confirmation par code, affichée quand un profil famille bascule
// vers un rôle de rang supérieur (voir spec/SPEC.md §2.2). Maquette : tout
// code non vide est accepté, la vraie vérification est pour le backend.
export default function CodeConfirmModal({ profil, onConfirm, onClose }) {
  const [code, setCode] = useState('')

  return (
    <Modal
      title={`Code ${ROLE_LABEL[profil.type]}`}
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!code}
          onClick={() => onConfirm(code)}
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
        placeholder="Code d’accès"
      />
    </Modal>
  )
}
