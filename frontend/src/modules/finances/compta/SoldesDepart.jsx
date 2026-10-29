// Comptes ⋯ › « Soldes de départ » (spec/modules/financier.md §8.7, niveau
// Complet) : un solde par compte du bilan au premier jour de la saison,
// repris de la Balance de l'an dernier ; l'appli compare les 512x aux
// relevés, la différence va dans 110 Report à nouveau.
import { useEffect, useState } from 'react'
import Modal from '../../../components/Modal.jsx'
import * as api from '../api.js'
import './compta.css'

const SOLDES_EVENT = 'finances-soldes-depart'

// Entrée « Soldes de départ » du menu ⋯ (voir Financier.jsx).
export function requestSoldesDepart() {
  window.dispatchEvent(new Event(SOLDES_EVENT))
}

export const SOLDES_EVENTS = { soldes: SOLDES_EVENT }

const SOURCES = {
  saisie: 'Soldes repris par le trésorier.',
  cloture: 'Soldes reportés par la clôture de la saison précédente.',
  releves: 'Trésorerie des relevés au début de la saison ; les comptes de tiers partent de zéro.',
}

export default function SoldesDepart({ onClose }) {
  const [saisons, setSaisons] = useState([])
  const [seasonId, setSeasonId] = useState(null)
  const [data, setData] = useState(null)
  const [lignes, setLignes] = useState([])
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api
      .saisons()
      .then(({ seasons }) => {
        setSaisons(seasons)
        setSeasonId((seasons.find((s) => s.current) ?? seasons[0])?.id ?? null)
      })
      .catch((err) => setErreur(err.message))
  }, [])

  useEffect(() => {
    if (seasonId == null) return
    api
      .soldesDepart(seasonId)
      .then((d) => {
        setData(d)
        setLignes(d.accounts.map((a) => ({ ...a, balance: a.balance === 0 ? '' : String(a.balance) })))
      })
      .catch((err) => setErreur(err.message))
  }, [seasonId])

  async function reprendre() {
    try {
      const d = await api.enregistrerSoldesDepart(
        seasonId,
        lignes.map((l) => ({ number: l.number, label: l.label, balance: Number(l.balance) || 0 })),
      )
      setData(d)
      setLignes(d.accounts.map((a) => ({ ...a, balance: a.balance === 0 ? '' : String(a.balance) })))
      setErreur('')
    } catch (err) {
      setErreur(err.message)
    }
  }

  const debut = saisons.find((s) => s.id === seasonId)?.startDate
  const total = lignes.reduce((s, l) => s + (Number(l.balance) || 0), 0)

  return (
    <Modal
      title="Soldes de départ"
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary" onClick={reprendre} disabled={!data || data.closed}>
          Utiliser ces soldes au {debut ? api.dateFr(debut) : 'début de la saison'}
        </button>
      }
    >
      <div className="fin-cp">
        <label className="fin-cp-champ">
          <span>Saison</span>
          <select className="field-input" value={seasonId ?? ''} onChange={(e) => setSeasonId(Number(e.target.value))}>
            {saisons.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        {data && (
          <>
            <p className="muted">{SOURCES[data.source]} Solde positif = débiteur (banque, caisse), négatif = dû (fournisseurs, report).</p>
            <p className="muted">
              Ces soldes sont la première ligne de chaque compte au début de la saison. Ils servent pour le Grand livre et la Balance,
              la trésorerie de la Synthèse et du Rapport financier, et ce que la clôture reporte sur la saison suivante. Ils ne changent
              ni les dépenses, ni les recettes, ni le résultat.
            </p>
          </>
        )}
        {data?.closed && <p className="fin-cp-alerte">Saison clôturée : rouvrez-la (Bilan › Documents de l’AG) pour changer ses soldes.</p>}
        {lignes.map((l, i) => (
          <label key={l.number} className="fin-cp-champ fin-cp-solde">
            <span>
              {l.number} {l.label}
            </span>
            <input
              className="field-input"
              type="number"
              step="0.01"
              inputMode="decimal"
              value={l.balance}
              placeholder="0"
              onChange={(e) => setLignes((ls) => ls.map((x, j) => (j === i ? { ...x, balance: e.target.value } : x)))}
            />
          </label>
        ))}
        {data?.bankCheck.map((c) =>
          Math.round((c.statements - c.entered) * 100) === 0 ? null : (
            <p key={c.number} className="fin-cp-alerte">
              {c.number} {c.label} : les relevés donnent {api.euros(c.statements)} au début de la saison, vous avez {api.euros(c.entered)}.
            </p>
          ),
        )}
        <p className="muted">
          {Math.round(total * 100) === 0
            ? 'Les soldes s’équilibrent.'
            : `Différence de ${api.euros(-total)} : elle ira dans 110 Report à nouveau.`}
        </p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}
