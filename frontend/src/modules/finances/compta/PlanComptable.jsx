// Comptes ⋯ › « Plan comptable » (spec/modules/financier.md §8.2) : les
// comptes de l'organisation par nature, ajout, renommage, mots-clés,
// événement (« gala »), et le niveau Simple / Complet (§8.1).
import { useEffect, useState } from 'react'
import Modal from '../../../components/Modal.jsx'
import * as api from '../api.js'
import './compta.css'

const { dateFr } = api

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

  const [memo, setMemo] = useState(null) // null | le commentaire en cours de saisie

  async function memoriser() {
    try {
      await api.memoriserPlan(memo)
      setMemo(null)
      charger()
    } catch (err) {
      setErreur(err.message)
    }
  }

  if (erreur) return <p className="login-screen__erreur">{erreur}</p>
  if (!plan) return <p className="muted">Chargement…</p>
  const natures = plan.level === 'complet' ? plan.natures : plan.natures.filter((n) => n.id === 'depense' || n.id === 'recette')
  // Natures libres (Seb, 10/11), chacune reliée aux classes des comptes qui la portent.
  const libres = [...new Set(plan.accounts.map((c) => c.natureLabel).filter(Boolean))].sort((a, b) => a.localeCompare(b))
  // Le plan par classe (premier chiffre du numéro), puis par nature dans la classe (Seb, 10/11).
  const nomNature = (c) => c.natureLabel || natures.find((n) => n.id === c.nature)?.label || c.nature
  const visibles = plan.accounts.filter((c) => c.natureLabel || natures.some((n) => n.id === c.nature))
  const classes = [...(plan.classes ?? []), { id: '', label: 'Autres numéros' }]
    .map((k) => {
      const comptes = visibles
        .filter((c) => (k.id ? c.number.startsWith(k.id) : !(plan.classes ?? []).some((x) => c.number.startsWith(x.id))))
        .sort((a, b) => a.number.localeCompare(b.number))
      const parNature = [...new Set(comptes.map(nomNature))].map((n) => ({ nom: n, comptes: comptes.filter((c) => nomNature(c) === n) }))
      return { ...k, comptes, parNature }
    })
    .filter((k) => k.comptes.length)

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
        pour une transaction bancaire ; un compte marqué « gala » entre dans le bloc du gala de la Synthèse.
      </p>
      <div className="fin-cp-champ">
        <span>Copies du plan</span>
        <p className="muted">
          Chaque copie garde le plan tel qu’il est à ce moment-là ; « Repartir à zéro sur cette saison » (Bilan › Clôture) en remet une.
        </p>
        {plan.snapshots.length === 0 ? (
          <p className="muted">Aucune copie pour l’instant.</p>
        ) : (
          <ul className="fin-cp-journal">
            {plan.snapshots.map((s) => (
              <li key={s.id}>
                <span className="fin-cp-num">{dateFr(s.takenAt.slice(0, 10))}</span>
                <span>{s.comment}</span>
              </li>
            ))}
          </ul>
        )}
        <button type="button" className="btn btn--secondary" onClick={() => setMemo(plan.snapshotSuggestion)}>
          Mémoriser le plan comptable
        </button>
      </div>
      {classes.map((classe) => (
        <div key={classe.id || 'autres'} className="fin-cp-carte">
          <h3>{classe.id ? `Classe ${classe.id} · ${classe.label}` : classe.label}</h3>
          {classe.parNature.map((groupe) => (
            <div key={groupe.nom} className="fin-cp-nature">
              <h4>{groupe.nom}</h4>
              {groupe.comptes.map((c) => (
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
      {memo !== null && (
        <Modal
          title="Mémoriser le plan comptable"
          onClose={() => setMemo(null)}
          footer={
            <>
              <button type="button" className="btn btn--secondary" onClick={() => setMemo(null)}>
                Annuler
              </button>
              <button type="button" className="btn btn--primary" onClick={memoriser}>
                Mémoriser
              </button>
            </>
          }
        >
          <label className="field">
            Où en est-on ? (pré-rempli avec ce qui a changé depuis la copie précédente)
            <input type="text" value={memo} onChange={(e) => setMemo(e.target.value)} maxLength={200} autoFocus />
          </label>
        </Modal>
      )}
      {edition && (
        <FicheCompte
          compte={edition === 'nouveau' ? null : edition}
          natures={plan.natures}
          libres={libres.map((l) => ({
            label: l,
            nature: plan.accounts.find((c) => c.natureLabel === l).nature,
            classes: [...new Set(plan.accounts.filter((c) => c.natureLabel === l).map((c) => c.number[0]))],
          }))}
          classes={plan.classes ?? []}
          officielles={(plan.officialNatures ?? []).filter((o) => !libres.includes(o.label))}
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

// Une nature libre qui porte le nom d'une rubrique officielle (« 21 … ») garde son numéro de rubrique.
function rubriquesDejaLibres(libres) {
  return libres.map((l) => ({ ...l, prefix: /^\d+ /.test(l.label) ? l.label.split(' ')[0] : null }))
}

// Nature libre : ce qu'elle compte dans le résultat (le calcul suit la nature de base).
const COMPTE_COMME = [
  { id: 'depense', label: 'Une dépense' },
  { id: 'recette', label: 'Une recette' },
  { id: 'attente', label: 'Hors résultat (Balance et Grand livre seulement)' },
]

// La nature de calcul que donne une classe : 6 dépense, 7 recette, sinon hors résultat.
const natureDeClasse = (k) => (k === '6' ? 'depense' : k === '7' ? 'recette' : 'attente')

function FicheCompte({ compte, natures, libres, officielles, classes, onClose, onChange }) {
  const [form, setForm] = useState({
    number: compte?.number ?? '',
    label: compte?.label ?? '',
    nature: compte?.nature ?? 'depense',
    natureLabel: compte?.natureLabel ?? '',
    event: compte?.event ?? '',
    keywords: (compte?.keywords ?? []).join(', '),
    active: compte?.active ?? true,
  })
  const [erreur, setErreur] = useState('')
  // Le choix du menu Nature : une nature de base, une nature libre existante (« libre:Nom »), ou « nouvelle ».
  const [choixNature, setChoixNature] = useState(compte?.natureLabel ? `libre:${compte.natureLabel}` : (compte?.nature ?? 'depense'))
  const libre = choixNature === 'nouvelle' || choixNature.startsWith('libre:') || choixNature.startsWith('officiel:')
  const [natureTouchee, setNatureTouchee] = useState(Boolean(compte))
  function choisirNature(valeur) {
    setChoixNature(valeur)
    if (valeur.startsWith('officiel:')) {
      const o = officielles.find((x) => `officiel:${x.prefix}` === valeur)
      setForm((f) => ({ ...f, natureLabel: o.label, nature: o.nature }))
    } else if (valeur === 'nouvelle') setForm((f) => ({ ...f, natureLabel: '', nature: natureDeClasse(f.number[0]) }))
    else if (valeur.startsWith('libre:')) {
      const l = libres.find((x) => `libre:${x.label}` === valeur)
      setForm((f) => ({ ...f, natureLabel: l.label, nature: l.nature }))
    } else setForm((f) => ({ ...f, natureLabel: '', nature: valeur }))
  }
  // Nouveau compte hors 6 et 7 : la rubrique officielle se propose d'après le
  // numéro tapé (2154 → 21 Immobilisations corporelles) ; 6 et 7 restent Dépenses / Recettes.
  function changerNumero(e) {
    const number = e.target.value
    setForm((f) => ({ ...f, number }))
    if (natureTouchee) return
    const o = [...officielles, ...rubriquesDejaLibres(libres)]
      .filter((x) => x.nature === 'attente' && x.prefix && number.startsWith(x.prefix))
      .sort((a, b) => b.prefix.length - a.prefix.length)[0]
    const l = o && libres.find((x) => x.label === o.label)
    if (l) choisirNature(`libre:${l.label}`)
    else if (o) choisirNature(`officiel:${o.prefix}`)
  }
  // La classe du compte (premier chiffre du numéro) : le menu Nature ne montre que les natures de cette classe.
  const classeDuCompte = classes.find((k) => form.number.startsWith(k.id))
  const groupesDeClasses = classes
    .filter((k) => !classeDuCompte || k.id === classeDuCompte.id)
    .map((k) => ({
      ...k,
      officielles: officielles.filter((o) => o.prefix.startsWith(k.id)),
      libres: libres.filter((l) => l.classes.includes(k.id)),
    }))
    .filter((k) => k.officielles.length || k.libres.length)
  const champ = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'checkbox' ? e.target.checked : e.target.value }))

  async function enregistrer() {
    const donnees = {
      ...form,
      natureLabel: libre ? form.natureLabel.trim() : '',
      event: form.event.trim() || null,
      keywords: form.keywords.split(',').map((m) => m.trim()).filter(Boolean),
    }
    if (choixNature === 'nouvelle' && !classeDuCompte) {
      setErreur('Tapez d’abord le numéro du compte : son premier chiffre donne la classe de la nature.')
      return
    }
    if (libre && !donnees.natureLabel) {
      setErreur('Donnez un nom à la nature.')
      return
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
          <input className="field-input" inputMode="numeric" value={form.number} onChange={changerNumero} />
        </label>
        <label className="fin-cp-champ">
          <span>Libellé</span>
          <input className="field-input" value={form.label} onChange={champ('label')} />
        </label>
        <label className="fin-cp-champ">
          <span>Nature</span>
          <select
            className="field-input"
            value={choixNature}
            onChange={(e) => {
              setNatureTouchee(true)
              choisirNature(e.target.value)
            }}
          >
            {natures.map((n) => (
              <option key={n.id} value={n.id}>
                {n.label}
              </option>
            ))}
            {groupesDeClasses.map((k) => (
              <optgroup key={k.id} label={`Classe ${k.id} · ${k.label}`}>
                {k.officielles.map((o) => (
                  <option key={o.prefix} value={`officiel:${o.prefix}`}>
                    {o.label}
                  </option>
                ))}
                {k.libres.map((l) => (
                  <option key={l.label} value={`libre:${l.label}`}>
                    {l.label}
                  </option>
                ))}
              </optgroup>
            ))}
            {choixNature.startsWith('libre:') && !groupesDeClasses.some((k) => k.libres.some((l) => `libre:${l.label}` === choixNature)) && (
              <option value={choixNature}>{choixNature.slice(6)}</option>
            )}
            <option value="nouvelle">Créer une nature{classeDuCompte ? ` dans la classe ${classeDuCompte.id}` : ''}…</option>
          </select>
        </label>
        {choixNature === 'nouvelle' && (
          <label className="fin-cp-champ">
            <span>
              Nom de la nature
              {classeDuCompte ? ` (classe ${classeDuCompte.id} · ${classeDuCompte.label})` : ' (tapez d’abord le numéro du compte)'}
            </span>
            <input className="field-input" value={form.natureLabel} onChange={champ('natureLabel')} placeholder="Matériel de sonorisation" autoFocus />
          </label>
        )}
        {libre && (
          <label className="fin-cp-champ">
            <span>Pour le résultat, ce compte est</span>
            <select className="field-input" value={form.nature} onChange={champ('nature')}>
              {COMPTE_COMME.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
        )}
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
