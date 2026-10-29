import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import * as api from '../../api/notesFrais.js'
import Modal from '../../components/Modal.jsx'
import './notes-frais.css'

// Réglage « Qui paie » sur la ligne Financier de Fonctionnalités (spec/
// modules/financier.md §8.3 bis) : à qui on peut faire payer un virement ;
// personne de coché = les trésoriers. Fenêtre hors de la ligne (portail) :
// la ligne est l'étiquette de la case, un clic dedans la cocherait.
export default function QuiPaie() {
  const [payeurs, setPayeurs] = useState(null)
  const [ouvert, setOuvert] = useState(false)

  useEffect(() => {
    api
      .payeurs()
      .then(setPayeurs)
      .catch(() => setPayeurs(null))
  }, [])

  // Réservé aux trésoriers : sinon, rien sur la ligne.
  if (!payeurs) return null

  return (
    <>
      <span className="nf-qui-paie">
        Qui paie : {payeurs.map((p) => p.nom).join(', ') || 'les trésoriers'}{' '}
        <button
          type="button"
          className="btn btn--link"
          onClick={(e) => {
            e.preventDefault()
            setOuvert(true)
          }}
        >
          Changer
        </button>
      </span>
      {ouvert &&
        createPortal(
          <Choix
            choisis={payeurs.map((p) => p.person_id)}
            onClose={() => setOuvert(false)}
            onEnregistre={(liste) => {
              setPayeurs(liste)
              setOuvert(false)
            }}
          />,
          document.body,
        )}
    </>
  )
}

function Choix({ choisis, onClose, onEnregistre }) {
  const [personnes, setPersonnes] = useState(null)
  const [coches, setCoches] = useState(() => new Set(choisis))
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api
      .personnes()
      .then(setPersonnes)
      .catch((err) => setErreur(err.message))
  }, [])

  async function enregistrer() {
    try {
      onEnregistre(await api.definirPayeurs([...coches]))
    } catch (err) {
      setErreur(err.message)
    }
  }

  return (
    <Modal
      title="Qui paie les virements ?"
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary" onClick={enregistrer}>
          Enregistrer
        </button>
      }
    >
      <p className="muted">
        Celles et ceux qui ont l’appli de la banque. « Faire payer par… » leur envoie une notification.
      </p>
      {!personnes && !erreur && <p className="muted">Chargement…</p>}
      <div className="checkbox-list">
        {(personnes ?? []).map((p) => (
          <label key={p.person_id} className="checkbox-list__item">
            <input
              type="checkbox"
              checked={coches.has(p.person_id)}
              onChange={() =>
                setCoches((c) => {
                  const suivant = new Set(c)
                  if (suivant.has(p.person_id)) suivant.delete(p.person_id)
                  else suivant.add(p.person_id)
                  return suivant
                })
              }
            />
            {p.nom}
          </label>
        ))}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}
