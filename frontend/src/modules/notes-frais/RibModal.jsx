import { useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Modal from '../../components/Modal.jsx'
import { ChampsRib, EXPLICATION_RIB, ribVide } from './commun.jsx'

// Profil > « Mon RIB » (spec notes de frais §4.5) : facultatif, vidé en
// effaçant l'IBAN.
export default function RibModal({ onClose }) {
  const [rib, setRib] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  useEffect(() => {
    api
      .espace()
      .then((e) => setRib(ribVide(e.rib)))
      .catch((err) => setErreur(err.message))
  }, [])

  async function enregistrer() {
    setErreur('')
    setEnCours(true)
    try {
      await api.definirRib(rib.iban.trim() ? rib : { titulaire: null, iban: null, bic: null })
      onClose()
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  return (
    <Modal
      title="Mon RIB"
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary btn--block" disabled={!rib || enCours} onClick={enregistrer}>
          Enregistrer
        </button>
      }
    >
      <p className="muted">{EXPLICATION_RIB}</p>
      {rib && <ChampsRib rib={rib} onChange={setRib} />}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}
