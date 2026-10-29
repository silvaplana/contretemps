// Fiche d'une opération bancaire (spec/modules/financier.md §8.4) : compte
// du plan proposé, à confirmer, ventilation sur plusieurs comptes, pièce.
import { useEffect, useState } from 'react'
import Modal from '../../../components/Modal.jsx'
import * as api from '../api.js'
import { nomCompte } from './PlanComptable.jsx'
import './compta.css'

const { euros, dateFr } = api

export default function FicheOperation({ operationId, onClose, onChange }) {
  const [fiche, setFiche] = useState(null)
  const [plan, setPlan] = useState(null)
  const [lignes, setLignes] = useState([]) // [{ accountId, amount }]
  const [ecritures, setEcritures] = useState(null) // Complet : lignes générées (§8.7)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    Promise.all([api.operation(operationId), api.planComptable()])
      .then(([f, p]) => {
        setFiche(f)
        setPlan(p)
        if (f.level === 'complet' && f.lines.length) api.ecritures(operationId).then((e) => setEcritures(e.entries)).catch(() => {})
        setLignes(
          f.lines.length
            ? f.lines.map((l) => ({ accountId: String(l.accountId), amount: l.amount }))
            : [{ accountId: f.proposal ? String(f.proposal.id) : '', amount: f.amount }],
        )
      })
      .catch((err) => setErreur(err.message))
  }, [operationId])

  async function enregistrer() {
    const retenues = lignes.filter((l) => l.accountId)
    try {
      await api.ventiler(operationId, retenues.map((l) => ({ accountId: Number(l.accountId), amount: Number(l.amount) })))
      onChange()
      onClose()
    } catch (err) {
      setErreur(err.message)
    }
  }

  if (erreur && !fiche) return <Modal title="Opération" onClose={onClose}><p className="login-screen__erreur">{erreur}</p></Modal>
  if (!fiche || !plan) return <Modal title="Opération" onClose={onClose}><p className="muted">Chargement…</p></Modal>

  const comptes = plan.accounts.filter((c) => c.active)
  const natures = plan.natures.filter((n) => (fiche.level === 'complet' ? true : n.id === 'depense' || n.id === 'recette'))
  const proposeChoisi = fiche.proposal && lignes.length === 1 && lignes[0].accountId === String(fiche.proposal.id) && !fiche.lines.length
  const total = lignes.reduce((s, l) => s + (Number(l.amount) || 0), 0)
  const ecart = Math.round((total - fiche.amount) * 100) / 100
  const changerLigne = (i, k, v) => setLignes((ls) => ls.map((l, j) => (j === i ? { ...l, [k]: v } : l)))

  return (
    <Modal
      title={fiche.label}
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary" onClick={enregistrer} disabled={fiche.transfer || (lignes.length > 1 && ecart !== 0)}>
          {proposeChoisi ? 'Confirmer' : 'Enregistrer'}
        </button>
      }
    >
      <div className="fin-cp">
        <p className="muted">
          {dateFr(fiche.date)} · {fiche.amount > 0 ? '+' : ''}
          {euros(fiche.amount)} · {fiche.bankAccount.name}
          {fiche.details ? ` · ${fiche.details.split('\n')[0]}` : ''}
        </p>
        {fiche.transfer ? (
          <p className="muted">Virement entre vos comptes : ni une recette ni une dépense, pas de compte du plan.</p>
        ) : (
          <>
            {lignes.map((ligne, i) => (
              <div key={i} className="fin-cp-champ">
                <span>{lignes.length > 1 ? `Compte ${i + 1}` : 'Compte'}</span>
                <select className="field-input" value={ligne.accountId} onChange={(e) => changerLigne(i, 'accountId', e.target.value)}>
                  <option value="">Compte à choisir</option>
                  {natures.map((n) => (
                    <optgroup key={n.id} label={n.label}>
                      {comptes
                        .filter((c) => c.nature === n.id)
                        .map((c) => (
                          <option key={c.id} value={c.id}>
                            {nomCompte(c)}
                          </option>
                        ))}
                    </optgroup>
                  ))}
                </select>
                {lignes.length > 1 && (
                  <input
                    className="field-input"
                    type="number"
                    step="0.01"
                    inputMode="decimal"
                    value={ligne.amount}
                    onChange={(e) => changerLigne(i, 'amount', e.target.value)}
                    aria-label="Montant"
                  />
                )}
              </div>
            ))}
            {proposeChoisi && (
              <p className="fin-cp-proposition">
                Proposé : {fiche.proposal.reason}. <span className="badge badge--warning">À confirmer</span>
              </p>
            )}
            {!fiche.proposal && !fiche.lines.length && !lignes[0]?.accountId && (
              <p className="fin-cp-proposition fin-cp-proposition--aucune">Aucune proposition : première fois que ce libellé apparaît.</p>
            )}
            {fiche.lines.length > 0 && (
              <p className="muted">Confirmé le {dateFr(fiche.lines[0].confirmedAt.slice(0, 10))}.</p>
            )}
            {lignes.length > 1 && (
              <p className={ecart === 0 ? 'muted' : 'login-screen__erreur'}>
                {ecart === 0 ? 'La ventilation fait le montant de la banque.' : `Écart avec la banque : ${euros(ecart)}`}
              </p>
            )}
            <div className="fin-cp-boutons">
              <button type="button" className="btn btn--secondary" onClick={() => setLignes((ls) => [...ls, { accountId: '', amount: 0 }])}>
                Ventiler sur un autre compte
              </button>
              {lignes.length > 1 && (
                <button type="button" className="btn btn--secondary" onClick={() => setLignes((ls) => [{ ...ls[0], amount: fiche.amount }])}>
                  Un seul compte
                </button>
              )}
            </div>
            {ecritures?.length > 0 && (
              <div className="fin-cp-champ">
                <span>Écritures</span>
                <table className="fin-cp-table">
                  <tbody>
                    {ecritures.map((e, i) => (
                      <tr key={i}>
                        <td>
                          {dateFr(e.date)} {e.journal}
                          {e.letter ? ` · ${e.letter}` : ''}
                        </td>
                        <td>{e.account}</td>
                        <td className="r">{e.debit ? euros(e.debit) : ''}</td>
                        <td className="r">{e.credit ? euros(e.credit) : ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <div className="fin-cp-champ">
              <span>Pièce</span>
              {fiche.piece ? (
                <p className="muted">
                  <span className="badge badge--success">{fiche.piece.kind}</span> {fiche.piece.title} — dans Financier › Pièces.
                </p>
              ) : (
                <p className="muted">Sans pièce. Une dépense établie dans Financier › Pièces se rattache à cette ligne quand elle est vue sur le compte.</p>
              )}
            </div>
          </>
        )}
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}
