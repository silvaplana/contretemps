// Puces « À rattacher » et « Ventes » de Financier › Pièces (spec/modules/
// financier.md §8.3) : les lignes de banque sans compte confirmé (dépenses et
// recettes), ou les recettes ; un appui ouvre la fiche de l'opération.
import { useCallback, useEffect, useState } from 'react'
import * as api from '../api.js'
import FicheOperation from './FicheOperation.jsx'
import { nomCompte } from './PlanComptable.jsx'
import './compta.css'

const { euros, dateFr } = api

// Les lignes de banque sans compte du plan, de la saison en cours seulement
// (Seb, 31/10 : les relevés des saisons passées sont importés mais ne se
// classent pas) : dépenses (À rattacher) ou recettes (Ventes).
export function lignesSansCompte(ledger, saisons) {
  const courante = saisons?.seasons?.find((s) => s.current)
  return ledger.rows.filter(
    (r) =>
      !r.transfer && !r.account && (!courante || (r.date >= courante.startDate && r.date <= courante.endDate))
  )
}

export default function LignesBanque({ filtre, onChange }) {
  const [ledger, setLedger] = useState(null)
  const [saisons, setSaisons] = useState(null)
  const [erreur, setErreur] = useState('')
  const [fiche, setFiche] = useState(null)

  const charger = useCallback(() => {
    Promise.all([api.historique(), api.saisons()])
      .then(([l, s]) => {
        setLedger(l)
        setSaisons(s)
      })
      .catch((err) => setErreur(err.message))
  }, [])
  useEffect(charger, [charger])

  if (erreur) return <p className="login-screen__erreur">{erreur}</p>
  if (!ledger) return <p className="muted">Chargement…</p>

  const lignes = lignesSansCompte(ledger, saisons).filter((r) => (filtre === 'ventes' ? r.amount > 0 : r.amount < 0))
  return (
    <section className="fin-cp" aria-label={filtre === 'ventes' ? 'Ventes' : 'À rattacher'}>
      <p className="muted">
        {filtre === 'ventes'
          ? 'Les recettes de la saison sans compte du plan. Un virement HelloAsso ou une remise de chèques se ventile sur plusieurs comptes.'
          : 'Les lignes de banque de la saison sans compte du plan : un appui, le compte proposé, Confirmer.'}
      </p>
      {lignes.length === 0 ? (
        <p className="empty-state">{filtre === 'ventes' ? 'Aucune recette' : 'Tout est classé'}</p>
      ) : (
        <div className="fin-cp-carte">
          {lignes.map((r) => (
            <button key={r.id} type="button" className="fin-cp-ligne" onClick={() => setFiche(r.id)}>
              <span className="fin-cp-l">{r.label}</span>
              <span className={r.amount > 0 ? 'fin-cp-m in' : 'fin-cp-m'}>
                {r.amount > 0 ? '+' : ''}
                {euros(r.amount)}
              </span>
              <span className="fin-cp-s">
                {dateFr(r.date)} ·{' '}
                {r.account ? (
                  nomCompte(r.account) + (r.account.split ? ' (ventilé)' : '')
                ) : r.proposal ? (
                  <>
                    {nomCompte(r.proposal)} <span className="badge badge--warning">à confirmer</span>
                  </>
                ) : (
                  'Compte à choisir'
                )}
                {r.piece && <span className="badge badge--success"> {r.piece.kind}</span>}
              </span>
            </button>
          ))}
        </div>
      )}
      {fiche && (
        <FicheOperation
          operationId={fiche}
          onClose={() => setFiche(null)}
          onChange={() => {
            charger()
            onChange?.()
          }}
        />
      )}
    </section>
  )
}
