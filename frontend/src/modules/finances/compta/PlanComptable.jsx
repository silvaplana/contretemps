// Comptes ⋯ › « Plan comptable » (spec/modules/financier.md §8.2) : les
// comptes de l'organisation par nature, ajout, renommage, mots-clés,
// événement (« gala »), et le niveau Simple / Complet (§8.1).
import { useEffect, useState } from 'react'
import Modal from '../../../components/Modal.jsx'
import * as api from '../api.js'
import './compta.css'

const PLAN_EVENT = 'finances-plan-comptable'

// Entrée « Plan comptable » du menu ⋯ (voir Financier.jsx).
export function requestPlanComptable() {
  window.dispatchEvent(new Event(PLAN_EVENT))
}

export const PLAN_EVENTS = { plan: PLAN_EVENT }

export function nomCompte(c) {
  return c ? `${c.number} ${c.label}` : ''
}

export default function PlanComptable({ onClose }) {
  const [plan, setPlan] = useState(null)
  const [erreur, setErreur] = useState('')
  const [edition, setEdition] = useState(null) // null | 'nouveau' | compte

  function charger() {
    api
      .planComptable()
      .then(setPlan)
      .catch((err) => setErreur(err.message))
  }
  useEffect(charger, [])

  async function choisirNiveau(level) {
    if (level === plan.level) return
    if (level === 'complet' && !window.confirm('Passer en Complet (partie double) ? On ne revient pas en Simple.')) return
    try {
      const r = await api.choisirNiveau(level)
      setPlan((p) => ({ ...p, level: r.level }))
    } catch (err) {
      setErreur(err.message)
    }
  }

  if (erreur) return <p className="login-screen__erreur">{erreur}</p>
  if (!plan) return <p className="muted">Chargement…</p>
  const natures = plan.level === 'complet' ? plan.natures : plan.natures.filter((n) => n.id === 'depense' || n.id === 'recette')

  return (
    <section className="fin-cp" aria-label="Plan comptable">
      <div className="fin-cp-champ">
        <span>Documents comptables</span>
        <div className="fin-cp-niveau" role="group" aria-label="Niveau">
          {[
            ['simple', 'Simple'],
            ['complet', 'Complet'],
          ].map(([id, label]) => (
            <button key={id} type="button" className={plan.level === id ? 'is-active' : ''} onClick={() => choisirNiveau(id)}>
              {label}
            </button>
          ))}
        </div>
        <p className="muted">
          <b>Simple</b> : Synthèse Dépenses-Recettes, trésorerie et Rapport financier, ce que l’assemblée générale vote.{' '}
          <b>Complet</b> : partie double (fournisseurs, adhérents, honoraires par prof, lettrage, clôture), Grand livre,
          Balance et Honoraires par professeur en plus.
        </p>
      </div>
      <p className="muted">
        Le libellé est le vôtre ; le numéro suit le plan comptable des associations. Les mots-clés font proposer le compte
        pour une ligne de banque ; un compte marqué « gala » entre dans le bloc du gala de la Synthèse.
      </p>
      {natures.map((nature) => (
        <div key={nature.id} className="fin-cp-carte">
          <h3>{nature.label}</h3>
          {plan.accounts
            .filter((c) => c.nature === nature.id)
            .map((c) => (
              <button key={c.id} type="button" className="fin-cp-compte" onClick={() => setEdition(c)}>
                <span className="fin-cp-num">{c.number}</span>
                <span>
                  {c.label}
                  {c.event && <span className="badge badge--warning"> {c.event}</span>}
                  {!c.active && <span className="badge"> inactif</span>}
                </span>
                <span className="fin-cp-c">{c.used ? `${c.used} ligne${c.used > 1 ? 's' : ''}` : ''}</span>
              </button>
            ))}
        </div>
      ))}
      <div className="fin-cp-boutons">
        <button type="button" className="btn btn--primary" onClick={() => setEdition('nouveau')}>
          Ajouter un compte
        </button>
        <button type="button" className="btn btn--secondary" onClick={onClose}>
          Fermer
        </button>
      </div>
      {edition && (
        <FicheCompte
          compte={edition === 'nouveau' ? null : edition}
          natures={plan.natures}
          onClose={() => setEdition(null)}
          onChange={() => {
            setEdition(null)
            charger()
          }}
        />
      )}
    </section>
  )
}

function FicheCompte({ compte, natures, onClose, onChange }) {
  const [form, setForm] = useState({
    number: compte?.number ?? '',
    label: compte?.label ?? '',
    nature: compte?.nature ?? 'depense',
    event: compte?.event ?? '',
    keywords: (compte?.keywords ?? []).join(', '),
    active: compte?.active ?? true,
  })
  const [erreur, setErreur] = useState('')
  const champ = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  async function enregistrer() {
    const donnees = {
      ...form,
      event: form.event.trim() || null,
      keywords: form.keywords.split(',').map((m) => m.trim()).filter(Boolean),
    }
    try {
      if (compte) await api.modifierCompte(compte.id, donnees)
      else await api.creerCompte(donnees)
      onChange()
    } catch (err) {
      setErreur(err.message)
    }
  }

  async function supprimer() {
    if (!window.confirm(`Retirer le compte ${compte.number} ${compte.label} ? S’il a servi, il devient inactif.`)) return
    try {
      await api.supprimerCompte(compte.id)
      onChange()
    } catch (err) {
      setErreur(err.message)
    }
  }

  return (
    <Modal
      title={compte ? 'Compte' : 'Nouveau compte'}
      onClose={onClose}
      footer={
        <>
          {compte && (
            <button type="button" className="btn btn--secondary" onClick={supprimer}>
              Retirer
            </button>
          )}
          <button type="button" className="btn btn--primary" onClick={enregistrer}>
            Enregistrer
          </button>
        </>
      }
    >
      <div className="fin-cp">
        <label className="fin-cp-champ">
          <span>Numéro (plan comptable associatif)</span>
          <input className="field-input" inputMode="numeric" value={form.number} onChange={champ('number')} />
        </label>
        <label className="fin-cp-champ">
          <span>Libellé</span>
          <input className="field-input" value={form.label} onChange={champ('label')} />
        </label>
        <label className="fin-cp-champ">
          <span>Nature</span>
          <select className="field-input" value={form.nature} onChange={champ('nature')}>
            {natures.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
          </select>
        </label>
        <label className="fin-cp-champ">
          <span>Mots-clés du libellé de banque, séparés par des virgules</span>
          <input className="field-input" value={form.keywords} onChange={champ('keywords')} placeholder="AMAZON, CASTORAMA" />
        </label>
        <label className="fin-cp-champ">
          <span>Événement (ex. gala), pour le bloc de la Synthèse</span>
          <input className="field-input" value={form.event} onChange={champ('event')} />
        </label>
        {compte && (
          <label className="checkbox-list__item">
            <input type="checkbox" checked={form.active} onChange={champ('active')} /> Compte actif
          </label>
        )}
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
      </div>
    </Modal>
  )
}
