import { useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Modal from '../../components/Modal.jsx'
import { ribVide } from './commun.jsx'
import { FicheExterieur } from './Pieces.jsx'

// Financier › ⋯ › Extérieurs (spec notes-de-frais.md §7 quater) : les personnes
// payées sans être membres ; corriger leur mail ou leur IBAN, ou les retirer
// de « Pour qui ? » (leurs notes gardent leur nom).
export default function Exterieurs({ onClose }) {
  const [liste, setListe] = useState(null)
  const [fiche, setFiche] = useState(null) // { id, nom, email, rib }
  const [erreur, setErreur] = useState('')

  function charger() {
    api
      .exterieurs()
      .then(setListe)
      .catch((err) => setErreur(err.message))
  }
  useEffect(charger, [])

  async function agir(action) {
    setErreur('')
    try {
      await action()
      setFiche(null)
      charger()
    } catch (err) {
      setErreur(err.message)
    }
  }

  if (fiche) {
    return (
      <Modal
        title={fiche.nom || 'Extérieur'}
        onClose={() => setFiche(null)}
        footer={
          <div className="nf-boutons">
            <button type="button" className="btn btn--secondary" onClick={() => agir(() => api.retirerExterieur(fiche.id))}>
              Retirer de la liste
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={!fiche.nom.trim()}
              onClick={() =>
                agir(() =>
                  api.modifierExterieur(fiche.id, {
                    nom: fiche.nom,
                    email: fiche.email,
                    rib: fiche.rib.iban.trim() ? fiche.rib : { iban: null },
                  }),
                )
              }
            >
              Enregistrer
            </button>
          </div>
        }
      >
        <FicheExterieur fiche={fiche} onChange={setFiche} />
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
      </Modal>
    )
  }

  return (
    <Modal title="Extérieurs" onClose={onClose}>
      <p className="muted">Les personnes payées sans être membres. On les ajoute depuis « Pour qui ? ».</p>
      {!liste && !erreur && <p className="muted">Chargement…</p>}
      {liste?.length === 0 && <p className="muted">Personne pour l’instant.</p>}
      <div className="nf-liste">
        {(liste ?? []).map((e) => (
          <button
            key={e.id}
            type="button"
            className="nf-ligne nf-ligne--note"
            onClick={() => setFiche({ id: e.id, nom: e.nom, email: e.email ?? '', rib: ribVide(e.rib) })}
          >
            <span className="nf-ligne__corps">
              <span className="nf-ligne__titre">{e.nom}</span>
              <span className="muted">
                {e.email || 'Pas de mail'} · {e.rib ? 'IBAN connu' : 'IBAN à demander'}
              </span>
            </span>
          </button>
        ))}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}
