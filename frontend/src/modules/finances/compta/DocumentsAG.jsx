// Bloc « Documents de l'AG » sous un bilan (spec/modules/financier.md §8.6) :
// Synthèse Dépenses-Recettes (Excel et à l'écran), et au niveau Complet
// Balance, Grand livre, Honoraires par professeur. Tout est additionné par
// l'appli depuis les lignes de banque et de caisse ; chaque fichier produit
// est aussi rangé dans Docs › Financier › AG.
import { useEffect, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import { telechargerFichier } from '../../../utils/telechargement.js'
import * as api from '../api.js'
import './compta.css'

const { euros, dateFr } = api

export default function DocumentsAG({ reportId, seasonName }) {
  const [data, setData] = useState(null)
  const [erreur, setErreur] = useState('')
  const [voir, setVoir] = useState(false)

  useEffect(() => {
    if (reportId == null) return
    api
      .documentsAG(reportId)
      .then(setData)
      .catch((err) => setErreur(err.message))
  }, [reportId])

  if (reportId == null) return null

  function telecharger(doc) {
    telechargerFichier(api.urlDocumentAG(reportId, doc.id), `${doc.title} ${seasonName}.${doc.format}`).catch((err) => setErreur(err.message))
  }

  return (
    <div className="fin-cp">
      <h4 className="reports-subtitle">Documents de l’AG</h4>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!data && !erreur && <p className="muted">Chargement…</p>}
      {data && (
        <>
          <div className="fin-cp-carte">
            {data.documents.map((d) => (
              <div key={d.id} className="fin-cp-doc">
                <span className="fin-cp-t">{d.title}</span>
                <span className="fin-cp-a">
                  {d.id === 'synthese' && (
                    <button type="button" className="btn btn--secondary" onClick={() => setVoir((v) => !v)}>
                      <Icon name="eye" size={16} /> Voir
                    </button>
                  )}
                  <button type="button" className="btn btn--secondary" onClick={() => telecharger(d)}>
                    <Icon name="download" size={16} /> {d.format === 'pdf' ? 'PDF' : 'Excel'}
                  </button>
                </span>
                <span className="fin-cp-s">{SOUS_TITRES[d.id]}</span>
              </div>
            ))}
          </div>
          <p className="muted">
            Additionnés par l’appli depuis les lignes de banque (compte du plan confirmé) et la caisse, du{' '}
            {dateFr(data.synthese.start)} au {dateFr(data.synthese.cutoff)}. Les fichiers vont dans Docs › Financier › AG.
            {data.level === 'simple' && ' Grand livre, Balance et Honoraires par professeur : niveau Complet (Comptes › ⋯ › Plan comptable).'}
          </p>
          {data.synthese.unclassified !== 0 && (
            <p className="fin-cp-proposition fin-cp-proposition--aucune">
              {euros(data.synthese.unclassified)} de lignes sans compte, sur « à classer » : Comptes › Sans compte.
            </p>
          )}
          {voir && <Synthese s={data.synthese} />}
        </>
      )}
    </div>
  )
}

const SOUS_TITRES = {
  synthese: 'charges et produits par poste, trésorerie, fournisseurs à payer',
  balance: 'totaux débit / crédit et soldes par compte',
  'grand-livre': 'toutes les lignes, par compte, avec la pièce',
  honoraires: 'par professeur et par mois, pour la DAS-2',
}

function Groupes({ groupes }) {
  return groupes.map((g) => (
    <tbody key={g.code}>
      <tr className="grp">
        <td colSpan={2}>
          {g.code} · {g.label}
        </td>
      </tr>
      {g.lines.map((l) => (
        <tr key={l.number}>
          <td>{l.label}</td>
          <td className="r">{euros(l.amount)}</td>
        </tr>
      ))}
    </tbody>
  ))
}

function Synthese({ s }) {
  return (
    <>
      <div className="fin-cp-carte">
        <table className="fin-cp-table">
          <Groupes groupes={s.charges} />
          <tbody>
            <tr className="tot">
              <td>Total des charges</td>
              <td className="r">{euros(s.totalCharges)}</td>
            </tr>
          </tbody>
          <Groupes groupes={s.produits} />
          <tbody>
            <tr className="tot">
              <td>Total des produits</td>
              <td className="r">{euros(s.totalProduits)}</td>
            </tr>
            <tr className="tot">
              <td>{s.result < 0 ? 'Déficit' : 'Excédent'}</td>
              <td className={s.result < 0 ? 'r unpaid-amount' : 'r success-state'}>{euros(s.result)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div className="fin-cp-carte">
        <table className="fin-cp-table">
          <tbody>
            <tr className="grp">
              <td colSpan={2}>Trésorerie au {dateFr(s.cutoff)}</td>
            </tr>
            {s.treasury.map((t) => (
              <tr key={t.label}>
                <td>{t.label}</td>
                <td className="r">{euros(t.amount)}</td>
              </tr>
            ))}
            <tr className="tot">
              <td>Solde de trésorerie</td>
              <td className="r">{euros(s.treasuryTotal)}</td>
            </tr>
            <tr>
              <td>Fournisseurs à payer{s.unpaid.length > 0 && ` (${s.unpaid.map((u) => u.title).join(', ')})`}</td>
              <td className="r">{euros(s.unpaidTotal)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      {s.events.map((e) => (
        <div key={e.event} className="fin-cp-carte">
          <table className="fin-cp-table">
            <tbody>
              <tr className="grp">
                <td colSpan={2}>{e.event}</td>
              </tr>
              <tr>
                <td>Ressources</td>
                <td className="r">{euros(e.resources)}</td>
              </tr>
              <tr>
                <td>Coût</td>
                <td className="r">{euros(e.cost)}</td>
              </tr>
              <tr className="tot">
                <td>{e.profit < 0 ? 'Perte' : 'Bénéfice'}</td>
                <td className="r">{euros(e.profit)}</td>
              </tr>
            </tbody>
          </table>
        </div>
      ))}
    </>
  )
}
