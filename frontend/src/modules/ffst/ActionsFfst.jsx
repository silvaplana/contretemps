import { useState } from 'react'
import Modal from '../../components/Modal.jsx'
import * as api from './api.js'

// Colonne « Actions FFST » du tableau des adhérents (spec/modules/ffst.md §5,
// maquette https://claude.ai/artifact/4tizDZ6Br2WxGL5MYwSQfy), mêmes boutons
// que Sambo Admin : Inconnu → « Faire la demande Pratiquant », « Faire la
// demande Autre rôle » (et le genre s'il manque) ; Brouillon → « Supprimer la
// demande ». Chaque bouton pilote le site de la FFST, une demande à la fois.

const PRATIQUANT = '005-PRATIQUANT'
let fonctionsLues = null // les fonctions de la FFST, lues une fois

export default function ActionsFfst({ ecoleId, eleve, ligne, relire }) {
  const [genre, setGenre] = useState('')
  const [enCours, setEnCours] = useState(null) // null | 'Envoi en cours…' | 'Suppression en cours…'
  const [erreur, setErreur] = useState(null)
  const [avertissement, setAvertissement] = useState(null)
  const [choixRole, setChoixRole] = useState(null) // null | { fonctions, fonction }

  if (!ligne || (ligne.status !== 'Inconnu' && ligne.status !== 'Brouillon')) return null

  async function agir(libelle, action) {
    setEnCours(libelle)
    setErreur(null)
    setAvertissement(null)
    try {
      const resultat = await action()
      if (resultat?.warnings?.length) setAvertissement(resultat.warnings.join(' '))
      await relire()
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnCours(null)
    }
  }

  const demander = (fonction) =>
    agir('Envoi en cours…', () => api.demander(ecoleId, eleve.id, { fonction, gender: genre || null }))

  async function ouvrirChoixRole() {
    try {
      fonctionsLues = fonctionsLues ?? (await api.fonctions(ecoleId)).filter((f) => f !== PRATIQUANT)
      setChoixRole({ fonctions: fonctionsLues, fonction: fonctionsLues[0] })
    } catch (e) {
      setErreur(e.message)
    }
  }

  // Les boutons sont dans une ligne qui ouvre la fiche : ne pas l'ouvrir.
  const stop = (e) => e.stopPropagation()

  return (
    <div className="ffst-actions" onClick={stop}>
      {enCours ? (
        <p className="ffst-actions__attente">
          ⏳ {enCours} Le site de la FFST est piloté automatiquement : ça peut prendre jusqu’à 30 secondes, merci de
          patienter.
        </p>
      ) : ligne.status === 'Brouillon' ? (
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() => agir('Suppression en cours…', () => api.retirer(ecoleId, eleve.id))}
        >
          Supprimer la demande
        </button>
      ) : (
        <>
          {!ligne.gender_known && (
            <label className="ffst-actions__genre">
              Genre absent de HelloAsso :{' '}
              <select className="field-input" value={genre} onChange={(e) => setGenre(e.target.value)}>
                <option value="">Choisir</option>
                <option value="H">Homme</option>
                <option value="F">Femme</option>
              </select>
            </label>
          )}
          <div className="ffst-actions__boutons">
            <button type="button" className="btn btn--secondary" onClick={() => demander(PRATIQUANT)}>
              Faire la demande Pratiquant
            </button>
            <button type="button" className="btn btn--secondary" onClick={ouvrirChoixRole}>
              Faire la demande Autre rôle
            </button>
          </div>
        </>
      )}
      {erreur && (
        <p className="ffst-actions__erreur" role="alert">
          {erreur}
        </p>
      )}
      {avertissement && <p className="ffst-actions__avertissement">{avertissement}</p>}
      {choixRole && (
        <Modal
          title={`Demande de licence pour ${eleve.prenom} ${eleve.nom}`}
          onClose={() => setChoixRole(null)}
          footer={
            <>
              <button type="button" className="btn btn--secondary" onClick={() => setChoixRole(null)}>
                Annuler
              </button>
              <button
                type="button"
                className="btn btn--primary"
                onClick={() => {
                  const fonction = choixRole.fonction
                  setChoixRole(null)
                  demander(fonction)
                }}
              >
                Faire la demande
              </button>
            </>
          }
        >
          <div className="form-fields" onClick={stop}>
            <label htmlFor="ffst-fonction">Rôle à la FFST</label>
            <select
              id="ffst-fonction"
              className="field-input"
              value={choixRole.fonction}
              onChange={(e) => setChoixRole({ ...choixRole, fonction: e.target.value })}
            >
              {choixRole.fonctions.map((f) => (
                <option key={f} value={f}>
                  {f}
                </option>
              ))}
            </select>
            <p className="muted">La commune de naissance est cherchée à partir de la ville de l’adhérent.</p>
          </div>
        </Modal>
      )}
    </div>
  )
}
