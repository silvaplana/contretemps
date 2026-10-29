// Puce « Caisse » de Comptes (spec/modules/financier.md §8.5) : le seul
// compte saisi à la main, une ligne par mouvement d'espèces ; un retrait au
// distributeur est un virement interne depuis une opération bancaire.
import { useEffect, useState } from 'react'
import Modal from '../../../components/Modal.jsx'
import * as api from '../api.js'
import { nomCompte } from './PlanComptable.jsx'
import './compta.css'

const { euros, dateFr } = api

export default function Caisse({ retraits }) {
  const [caisse, setCaisse] = useState(null)
  const [erreur, setErreur] = useState('')
  const [ajout, setAjout] = useState(false)

  function charger() {
    api
      .caisse()
      .then(setCaisse)
      .catch((err) => setErreur(err.message))
  }
  useEffect(charger, [])

  async function supprimer(ligne) {
    if (!window.confirm(`Retirer la ligne « ${ligne.label} » ?`)) return
    try {
      setCaisse(await api.supprimerLigneCaisse(ligne.id))
    } catch (err) {
      setErreur(err.message)
    }
  }

  if (erreur) return <p className="login-screen__erreur">{erreur}</p>
  if (!caisse) return <p className="muted">Chargement…</p>

  return (
    <section className="fin-cp" aria-label="Caisse">
      <div className="fin-cp-carte">
        <div className="fin-cp-ligne">
          <span className="fin-cp-l">Solde de la caisse</span>
          <span className="fin-cp-m">{euros(caisse.balance)}</span>
          <span className="fin-cp-s">{caisse.asOf ? `au ${dateFr(caisse.asOf)} · espèces` : 'aucun mouvement'}</span>
        </div>
      </div>
      <p className="muted">Une ligne par mouvement d’espèces. Un retrait au distributeur est un virement interne depuis la banque.</p>
      {caisse.lines.length > 0 && (
        <div className="fin-cp-carte">
          {caisse.lines.map((l) => (
            <button key={l.id} type="button" className="fin-cp-ligne" onClick={() => supprimer(l)} title="Retirer la ligne">
              <span className="fin-cp-l">{l.label}</span>
              <span className={l.amount > 0 ? 'fin-cp-m in' : 'fin-cp-m'}>
                {l.amount > 0 ? '+' : ''}
                {euros(l.amount)}
              </span>
              <span className="fin-cp-s">
                {dateFr(l.date)}
                {l.account && ` · ${nomCompte(l.account)}`}
                {l.transferOperationId && ' · Virement interne depuis la banque'}
              </span>
            </button>
          ))}
        </div>
      )}
      <button type="button" className="btn btn--primary" onClick={() => setAjout(true)}>
        Ajouter un mouvement
      </button>
      {ajout && (
        <NouvelleLigne
          retraits={retraits}
          onClose={() => setAjout(false)}
          onAjoutee={(c) => {
            setCaisse(c)
            setAjout(false)
          }}
        />
      )}
    </section>
  )
}

function NouvelleLigne({ retraits, onClose, onAjoutee }) {
  const [plan, setPlan] = useState(null)
  const [form, setForm] = useState({ date: new Date().toISOString().slice(0, 10), label: '', amount: '', sens: 'entree', accountId: '', retrait: '' })
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api.planComptable().then(setPlan).catch((err) => setErreur(err.message))
  }, [])
  const champ = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  async function enregistrer() {
    const montant = Math.abs(Number(form.amount) || 0)
    const retrait = form.retrait ? retraits.find((r) => String(r.id) === form.retrait) : null
    try {
      onAjoutee(
        await api.ajouterLigneCaisse({
          date: form.date,
          label: form.label,
          amount: retrait ? Math.abs(retrait.amount) : form.sens === 'entree' ? montant : -montant,
          accountId: retrait || !form.accountId ? null : Number(form.accountId),
          transferOperationId: retrait ? retrait.id : null,
        }),
      )
    } catch (err) {
      setErreur(err.message)
    }
  }

  const comptes = (plan?.accounts ?? []).filter((c) => c.active && (form.sens === 'entree' ? c.nature === 'recette' : c.nature === 'depense'))
  return (
    <Modal
      title="Mouvement de caisse"
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary" onClick={enregistrer}>
          Enregistrer
        </button>
      }
    >
      <div className="fin-cp">
        {retraits?.length > 0 && (
          <label className="fin-cp-champ">
            <span>Retrait au distributeur (virement interne)</span>
            <select className="field-input" value={form.retrait} onChange={champ('retrait')}>
              <option value="">Non, un mouvement d’espèces</option>
              {retraits.map((r) => (
                <option key={r.id} value={r.id}>
                  {dateFr(r.date)} · {r.label} · {euros(Math.abs(r.amount))}
                </option>
              ))}
            </select>
          </label>
        )}
        <label className="fin-cp-champ">
          <span>Date</span>
          <input className="field-input" type="date" value={form.date} onChange={champ('date')} />
        </label>
        <label className="fin-cp-champ">
          <span>Libellé</span>
          <input className="field-input" value={form.label} onChange={champ('label')} placeholder="Entrées du gala en espèces" />
        </label>
        {!form.retrait && (
          <>
            <div className="fin-cp-niveau" role="group" aria-label="Sens">
              {[
                ['entree', 'Entrée'],
                ['sortie', 'Sortie'],
              ].map(([id, label]) => (
                <button key={id} type="button" className={form.sens === id ? 'is-active' : ''} onClick={() => setForm((f) => ({ ...f, sens: id, accountId: '' }))}>
                  {label}
                </button>
              ))}
            </div>
            <label className="fin-cp-champ">
              <span>Montant</span>
              <input className="field-input" type="number" step="0.01" inputMode="decimal" value={form.amount} onChange={champ('amount')} />
            </label>
            <label className="fin-cp-champ">
              <span>Compte</span>
              <select className="field-input" value={form.accountId} onChange={champ('accountId')}>
                <option value="">Compte à choisir</option>
                {comptes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {nomCompte(c)}
                  </option>
                ))}
              </select>
            </label>
          </>
        )}
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}
