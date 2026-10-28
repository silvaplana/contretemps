// Puce « Caisse » de Comptes (spec/modules/financier.md §8.5), EXEMPLE : le
// seul compte saisi à la main, une ligne par mouvement d'espèces.
import BandeExemple from './BandeExemple.jsx'
import { CAISSE, PLAN, dateFr, eur } from './donnees.js'

export default function Caisse() {
  return (
    <section className="fin-ex" aria-label="Caisse">
      <BandeExemple />
      <div className="fin-ex-carte">
        <div className="fin-ex-ligne">
          <span className="fin-ex-l">Solde de la caisse</span>
          <span className="fin-ex-m">{eur(CAISSE.solde)}</span>
          <span className="fin-ex-s">au {dateFr(CAISSE.au)} · espèces</span>
        </div>
      </div>
      <p className="muted">Une ligne par mouvement d’espèces, avec sa pièce. Un retrait au distributeur est un virement interne.</p>
      <div className="fin-ex-carte">
        {CAISSE.lignes.map((l, i) => {
          const compte = PLAN.find((c) => c.num === l.compte)
          return (
            <div key={i} className="fin-ex-ligne">
              <span className="fin-ex-l">{l.libelle}</span>
              <span className={l.montant > 0 ? 'fin-ex-m in' : 'fin-ex-m'}>
                {l.montant > 0 ? '+' : ''}
                {eur(l.montant)}
              </span>
              <span className="fin-ex-s">
                {dateFr(l.date)}
                {compte && ` · ${compte.num} ${compte.label}`}
                {l.virement && ` · Virement interne ${l.virement}`}
                {l.piece && <span className="badge badge--success"> pièce</span>}
              </span>
            </div>
          )
        })}
      </div>
      <button type="button" className="btn btn--primary">
        Ajouter un mouvement
      </button>
    </section>
  )
}
