// Bloc « Documents de l'AG » sous un bilan produit (spec/modules/
// financier.md §8.6), EXEMPLE : les documents, et la Synthèse
// Dépenses-Recettes à l'écran dans la forme du modèle de la trésorière.
import { useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import BandeExemple from './BandeExemple.jsx'
import { DOCUMENTS_AG, SYNTHESE, eur, lireNiveau } from './donnees.js'

export default function DocumentsAG() {
  const [synthese, setSynthese] = useState(false)
  const niveau = lireNiveau()
  const documents = DOCUMENTS_AG.filter((d) => niveau === 'complet' || d.niveau === 'simple')
  return (
    <div className="fin-ex">
      <h4 className="reports-subtitle">Documents de l’AG</h4>
      <BandeExemple />
      <div className="fin-ex-carte">
        {documents.map((d) => (
          <div key={d.id} className="fin-ex-doc">
            <span className="fin-ex-t">{d.titre}</span>
            <span className="fin-ex-a">
              {d.formats.map((f) => (
                <button
                  key={f}
                  type="button"
                  className="btn btn--secondary"
                  onClick={f === 'Voir' ? () => setSynthese((v) => !v) : undefined}
                >
                  {f === 'Voir' ? <Icon name="eye" size={16} /> : <Icon name="download" size={16} />} {f}
                </button>
              ))}
            </span>
            <span className="fin-ex-s">{d.sous}</span>
          </div>
        ))}
      </div>
      <p className="muted">
        Les documents vont dans Docs › Financier › AG 2025-26, avec le badge Brouillon / Validé / Officiel du bilan.
        {niveau === 'simple' && ' Grand livre, Balance et Honoraires par professeur : niveau Complet (Plan comptable).'}
      </p>
      {synthese && <Synthese />}
    </div>
  )
}

function Bloc({ groupes }) {
  return groupes.map((g) => (
    <tbody key={g.groupe}>
      <tr className="grp">
        <td colSpan={2}>{g.groupe}</td>
      </tr>
      {g.lignes.map(([label, montant]) => (
        <tr key={label}>
          <td>{label}</td>
          <td className="r">{eur(montant)}</td>
        </tr>
      ))}
    </tbody>
  ))
}

function Synthese() {
  const s = SYNTHESE
  return (
    <>
      <p className="muted">Synthèse Dépenses-Recettes 2024-25, forme du modèle Excel : charges puis produits, l’un sous l’autre sur le téléphone.</p>
      <div className="fin-ex-carte">
        <table className="fin-ex-table">
          <Bloc groupes={s.charges} />
          <tbody>
            <tr className="tot">
              <td>Total des charges</td>
              <td className="r">{eur(s.totalCharges)}</td>
            </tr>
          </tbody>
          <Bloc groupes={s.produits} />
          <tbody>
            <tr className="tot">
              <td>Total des produits</td>
              <td className="r">{eur(s.totalProduits)}</td>
            </tr>
            <tr className="tot">
              <td>{s.resultat < 0 ? 'Déficit' : 'Excédent'}</td>
              <td className="r unpaid-amount">{eur(s.resultat)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="fin-ex-carte">
        <table className="fin-ex-table">
          <tbody>
            <tr className="grp">
              <td colSpan={2}>Trésorerie au 31/08/2025</td>
            </tr>
            {s.tresorerie.map(([label, montant]) => (
              <tr key={label}>
                <td>{label}</td>
                <td className="r">{eur(montant)}</td>
              </tr>
            ))}
            <tr className="tot">
              <td>Solde de trésorerie</td>
              <td className="r">{eur(s.soldeTresorerie)}</td>
            </tr>
            <tr>
              <td>Fournisseurs à payer</td>
              <td className="r">{eur(s.fournisseursAPayer)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="fin-ex-carte">
        <table className="fin-ex-table">
          <tbody>
            <tr className="grp">
              <td colSpan={2}>Le gala</td>
            </tr>
            <tr>
              <td>Ressources du gala</td>
              <td className="r">{eur(s.gala.ressources)}</td>
            </tr>
            <tr>
              <td>Coût du gala</td>
              <td className="r">{eur(s.gala.cout)}</td>
            </tr>
            <tr className="tot">
              <td>Bénéfice du gala</td>
              <td className="r">{eur(s.gala.benefice)}</td>
            </tr>
          </tbody>
        </table>
        <p className="muted">Un bloc par événement : les comptes marqués « gala » dans le plan comptable.</p>
      </div>
    </>
  )
}
