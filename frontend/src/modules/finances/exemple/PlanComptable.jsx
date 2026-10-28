// Comptes ⋯ › « Plan comptable » et « Soldes de départ » (spec/modules/
// financier.md §8.2 et §8.7), EXEMPLE. Le réglage Simple / Complet est ici
// pour l'essai ; dans la version finale il vit dans Admin › École ›
// Personnalisation › Fonctionnalités, ligne Financier (§8.1).
import { useState } from 'react'
import BandeExemple from './BandeExemple.jsx'
import { NATURES, PLAN, SOLDES_DEPART, ecrireNiveau, eur, lireNiveau } from './donnees.js'

const PLAN_EVENT = 'finances-plan-comptable'
const SOLDES_EVENT = 'finances-soldes-depart'

export function requestPlanComptable() {
  window.dispatchEvent(new Event(PLAN_EVENT))
}

export function requestSoldesDepart() {
  window.dispatchEvent(new Event(SOLDES_EVENT))
}

export const PLAN_EVENTS = { plan: PLAN_EVENT, soldes: SOLDES_EVENT }

export function PlanComptable({ onClose }) {
  const [niveau, setNiveau] = useState(lireNiveau)

  function choisirNiveau(n) {
    setNiveau(n)
    ecrireNiveau(n)
  }

  const natures = niveau === 'complet' ? ['depense', 'recette', 'tiers', 'attente'] : ['depense', 'recette']
  return (
    <section className="fin-ex" aria-label="Plan comptable">
      <BandeExemple />
      <div className="fin-ex-champ">
        <span>Documents comptables (réglage de Personnalisation, ici pour l’essai)</span>
        <div className="fin-ex-niveau" role="group">
          <button type="button" className={niveau === 'simple' ? 'is-active' : ''} onClick={() => choisirNiveau('simple')}>
            Simple
          </button>
          <button type="button" className={niveau === 'complet' ? 'is-active' : ''} onClick={() => choisirNiveau('complet')}>
            Complet
          </button>
        </div>
        <p className="muted">
          <b>Simple</b> : Synthèse Dépenses-Recettes, trésorerie et Rapport financier, ce que l’assemblée générale vote.{' '}
          <b>Complet</b> : partie double (fournisseurs, adhérents, honoraires par prof, lettrage, clôture), Grand livre,
          Balance et Honoraires par professeur en plus.
        </p>
      </div>
      <p className="muted">
        Les comptes de l’école, repris de la Balance 2024-25. Le libellé est le vôtre ; le numéro suit le plan des
        associations. Un compte marqué « gala » entre dans le bloc du gala de la Synthèse.
      </p>
      {natures.map((nature) => (
        <div key={nature} className="fin-ex-carte">
          <h3>{NATURES[nature]}</h3>
          {PLAN.filter((c) => c.nature === nature).map((c) => (
            <div key={c.num} className="fin-ex-compte">
              <span className="fin-ex-num">{c.num}</span>
              <span>
                {c.label}
                {c.evenement && <span className="badge badge--warning"> gala</span>}
              </span>
              <span className="fin-ex-c">{c.solde ?? (c.nb ? `${c.nb} opérations` : '')}</span>
            </div>
          ))}
        </div>
      ))}
      <div className="fin-ex-boutons">
        <button type="button" className="btn btn--secondary">
          Ajouter un compte
        </button>
        <button type="button" className="btn btn--secondary" onClick={onClose}>
          Fermer
        </button>
      </div>
    </section>
  )
}

export function SoldesDepart({ onClose }) {
  return (
    <section className="fin-ex" aria-label="Soldes de départ">
      <BandeExemple />
      <p className="muted">
        Soldes au 01/09/2025, repris de la Balance 2024-25 de la comptable (fichier déposé dans Docs). L’appli lit le
        PDF, vous vérifiez. Une fois la saison clôturée dans l’appli, ils se calculent tout seuls.
      </p>
      <div className="fin-ex-carte">
        <table className="fin-ex-table">
          <tbody>
            {SOLDES_DEPART.map((s) => (
              <tr key={s.num}>
                <td>
                  {s.num} {s.label}
                </td>
                <td className="r">{eur(s.montant)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p>
        <span className="badge badge--success">Les soldes de banque correspondent aux relevés du 31/08/2025</span>
      </p>
      <div className="fin-ex-boutons">
        <button type="button" className="btn btn--primary" onClick={onClose}>
          Reprendre ces soldes
        </button>
        <button type="button" className="btn btn--secondary" onClick={onClose}>
          Fermer
        </button>
      </div>
    </section>
  )
}
