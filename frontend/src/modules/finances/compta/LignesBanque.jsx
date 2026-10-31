// Puces « À rattacher » et « Ventes » de Financier › Pièces (spec/modules/
// financier.md §8.3) : les lignes de banque sans compte confirmé (dépenses et
// recettes), ou les recettes ; un appui ouvre la fiche de l'opération.
import { useCallback, useEffect, useState } from 'react'
import * as api from '../api.js'
import FicheOperation from './FicheOperation.jsx'
import { nomCompte } from './PlanComptable.jsx'
import './compta.css'

const { euros, dateFr } = api

export default function LignesBanque({ filtre, onChange }) {
  const [ledger, setLedger] = useState(null)
  const [erreur, setErreur] = useState('')
  const [fiche, setFiche] = useState(null)

  const charger = useCallback(() => {
    api
      .historique()
      .then(setLedger)
      .catch((err) => setErreur(err.message))
  }, [])
  useEffect(charger, [charger])

  if (erreur) return <p className="login-screen__erreur">{erreur}</p>
  if (!ledger) return <p className="muted">Chargement…</p>

  const lignes = ledger.rows.filter((r) => !r.transfer && (filtre === 'ventes' ? r.amount > 0 : !r.account))
  return (
    <section className="fin-cp" aria-label={filtre === 'ventes' ? 'Ventes' : 'À rattacher'}>
      <p className="muted">
        {filtre === 'ventes'
          ? 'Les recettes vues sur les comptes, avec leur compte du plan. Un virement HelloAsso ou une remise de chèques se ventile sur plusieurs comptes.'
          : 'Les lignes de banque sans compte du plan : un appui, le compte proposé, Confirmer.'}
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
