import { useState } from 'react'
import * as api from './api.js'

// Fiche d'un compte, ouverte par « Voir le compte » sous son nom quand une
// seule pastille est choisie (Comptes.jsx ; Seb, 28 octobre) : nom
// modifiable, IBAN (s'il est relié à la banque) ou numéro lu sur les
// relevés, nature, banque, période couverte par les relevés.
const NATURES = { checking: 'Compte courant', savings: 'Livret' }

const dateFr = (iso) => new Date(`${iso}T00:00:00`).toLocaleDateString('fr-FR')

// IBAN par groupes de 4, comme sur un RIB.
const ibanLisible = (iban) => iban.replace(/(.{4})/g, '$1 ').trim()

export default function FicheCompte({ compte, onChanged, onClose }) {
  const [message, setMessage] = useState('')

  async function renommer(nom) {
    if (!nom.trim() || nom.trim() === compte.name) return
    try {
      await api.renommerCompte(compte.id, nom.trim())
      onChanged()
    } catch (e) {
      setMessage(e.message)
    }
  }

  const releves = compte.coverage ?? []
  return (
    <section className="fin-fiche" aria-label={`Compte ${compte.name}`}>
      <label className="fin-fiche__ligne">
        <span>Nom</span>
        <input
          key={compte.name}
          className="fin-banque__input"
          defaultValue={compte.name}
          maxLength={80}
          onBlur={(e) => renommer(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && e.currentTarget.blur()}
        />
      </label>
      <p className="fin-fiche__ligne">
        <span>{compte.iban ? 'IBAN' : 'Numéro'}</span>
        <strong>{compte.iban ? ibanLisible(compte.iban) : compte.number}</strong>
      </p>
      <p className="fin-fiche__ligne">
        <span>Nature</span>
        <strong>{NATURES[compte.kind] ?? compte.kind}</strong>
      </p>
      <p className="fin-fiche__ligne">
        <span>Banque</span>
        <strong>{compte.bank ? `${compte.bank} · reliée` : 'non reliée'}</strong>
      </p>
      <p className="fin-fiche__ligne">
        <span>Relevés</span>
        <strong>
          {releves.length === 0
            ? 'aucun'
            : releves.map((p) => `du ${dateFr(p.from)} au ${dateFr(p.to)} (${p.statements})`).join(' · ')}
        </strong>
      </p>
      {message && <p className="login-screen__erreur">{message}</p>}
      <button type="button" className="btn btn--secondary" onClick={onClose}>
        Fermer
      </button>
    </section>
  )
}
