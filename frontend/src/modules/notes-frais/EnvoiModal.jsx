import { useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Modal from '../../components/Modal.jsx'
import { ChampsRib, ribVide } from './commun.jsx'

const MOIS = new Intl.DateTimeFormat('fr-FR', { month: 'long', year: 'numeric' })

// Titre proposé (spec §4.4) : la catégorie commune, sinon le mois.
function titreParDefaut(depenses) {
  const categories = new Set(depenses.map((d) => d.categorie?.libelle ?? ''))
  if (categories.size === 1 && depenses[0].categorie) return depenses[0].categorie.libelle
  const mois = new Set(depenses.map((d) => d.date.slice(0, 7)))
  const reference = mois.size === 1 ? new Date(`${depenses[0].date}T12:00:00`) : new Date()
  const texte = MOIS.format(reference)
  return `Frais de ${texte}`
}

// Envoi (spec §4.4) : la note est créée et transmise d'un coup.
export default function EnvoiModal({ depenses, rib, tresoriers, onClose, onEnvoyee }) {
  const [titre, setTitre] = useState(() => titreParDefaut(depenses))
  const [don, setDon] = useState(false)
  const [saisieRib, setSaisieRib] = useState(ribVide(rib))
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const total = depenses.reduce((s, d) => s + d.montant_centimes, 0)

  async function envoyer() {
    setErreur('')
    setEnCours(true)
    try {
      await api.envoyer({
        depenseIds: depenses.map((d) => d.id),
        titre,
        don,
        rib: !rib && !don ? saisieRib : null,
      })
      onEnvoyee()
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <Modal
      title="Envoyer aux trésoriers"
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary btn--block" disabled={enCours} onClick={envoyer}>
          Envoyer · {api.euros(total)}
        </button>
      }
    >
      <label htmlFor="nf-titre">Titre de la note</label>
      <input id="nf-titre" value={titre} onChange={(e) => setTitre(e.target.value)} maxLength={120} />
      <p>
        {depenses.length} dépense{depenses.length > 1 ? 's' : ''}, total <strong>{api.euros(total)}</strong>
      </p>

      {!don &&
        (rib ? (
          <p className="muted">
            Remboursement sur le compte {rib.titulaire ? `de ${rib.titulaire} ` : ''}
            <span className="nf-nowrap">{masquerIban(rib.iban)}</span> (modifiable dans Profil › Mon RIB).
          </p>
        ) : (
          <>
            <p className="muted">Votre RIB, pour le remboursement (il sera gardé dans votre Profil) :</p>
            <ChampsRib rib={saisieRib} onChange={setSaisieRib} />
          </>
        ))}

      <label className="nf-case">
        <input type="checkbox" checked={don} onChange={(e) => setDon(e.target.checked)} />
        <span>Je renonce au remboursement (don à l’association)</span>
      </label>
      {don && (
        <p className="muted">
          Une fois validée, la note sera terminée sans virement : elle compte comme un don à l’association (abandon de
          frais, utile pour un reçu fiscal).
        </p>
      )}
      {tresoriers === 0 && (
        <p className="badge badge--warning">Aucun trésorier n’est encore nommé : votre note attendra qu’il y en ait un.</p>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

export function masquerIban(iban) {
  if (!iban) return ''
  return `${iban.slice(0, 4)} •••• ${iban.slice(-4)}`
}
