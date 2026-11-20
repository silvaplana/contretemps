// Bilan › Préparer, étape 6 › Budget prévisionnel de la saison suivante
// (spec/modules/financier.md §8.10, Seb 20/11) : une ligne par compte de
// charges et de produits, le réalisé de la saison en face, le prévu tapé et
// gardé tout de suite. Totaux et résultat prévu calculés ; « Reprendre le
// réalisé » pré-remplit ; « Produire le document » télécharge l'Excel de l'AG.
// L'appli ne décide d'aucun chiffre.
import { useEffect, useState } from 'react'
import { telechargerFichier } from '../../../utils/telechargement.js'
import * as api from '../api.js'
import './compta.css'

const { euros } = api

function texte(v) {
  return v == null ? '' : String(v)
}

export default function BudgetPrevisionnel({ season, onClose }) {
  const [b, setB] = useState(null)
  const [saisie, setSaisie] = useState({}) // { numéro: texte tapé }
  const [erreur, setErreur] = useState('')

  function recevoir(d) {
    setB(d)
    setSaisie(Object.fromEntries([...d.charges.lines, ...d.produits.lines].map((l) => [l.number, texte(l.planned)])))
    setErreur('')
  }

  useEffect(() => {
    api.budget(season.id).then(recevoir).catch((err) => setErreur(err.message))
  }, [season.id])

  function garder(numero) {
    const brut = (saisie[numero] ?? '').replace(',', '.').trim()
    const avant = [...b.charges.lines, ...b.produits.lines].find((l) => l.number === numero)
    if (texte(avant?.planned) === brut) return
    api
      .enregistrerBudget(season.id, { [numero]: brut === '' ? null : Number(brut) })
      .then(recevoir)
      .catch((err) => setErreur(err.message))
  }

  function reprendre() {
    api.reprendreRealise(season.id).then(recevoir).catch((err) => setErreur(err.message))
  }

  function produire() {
    const nom = `Budget prévisionnel ${b.nextName}.xlsx`
    telechargerFichier(api.urlDocumentSaison(season.id, 'budget', nom), nom).catch((err) => setErreur(err.message))
  }

  if (!b) return erreur ? <p className="login-screen__erreur">{erreur}</p> : <p className="muted">Chargement…</p>

  const lignes = (cote) =>
    cote.lines.map((l) => (
      <tr key={l.number}>
        <td>
          {l.number} {l.label}
        </td>
        <td className="fin-balance__n">{euros(l.realised)}</td>
        <td className="fin-balance__n">
          <input
            type="text"
            inputMode="decimal"
            className="field-input fin-budget__prevu"
            aria-label={`Prévu ${b.nextName} : ${l.number} ${l.label}`}
            value={saisie[l.number] ?? ''}
            onChange={(e) => setSaisie((s) => ({ ...s, [l.number]: e.target.value }))}
            onBlur={() => garder(l.number)}
          />
        </td>
      </tr>
    ))

  return (
    <div className="fin-cp fin-balance">
      <button type="button" className="btn btn--link fin-releves__retour" onClick={onClose}>
        ← Étapes du bilan
      </button>
      <div className="fin-balance__titre">
        <h3>Budget prévisionnel {b.nextName}</h3>
        <p className="muted">Une ligne par compte, avec le réalisé de {b.seasonName} en face. Vous tapez ce que l’association prévoit ; chaque montant est gardé tout de suite.</p>
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <div className="fin-balance__table">
        <table>
          <thead>
            <tr>
              <th>Compte</th>
              <th className="fin-balance__n">Réalisé {b.seasonName}</th>
              <th className="fin-balance__n">Prévu {b.nextName}</th>
            </tr>
          </thead>
          <tbody>
            <tr className="fin-balance__classe">
              <td colSpan={3}>Charges</td>
            </tr>
            {lignes(b.charges)}
            <tr className="fin-balance__total">
              <td>Total des charges</td>
              <td className="fin-balance__n">{euros(b.charges.realised)}</td>
              <td className="fin-balance__n">{euros(b.charges.planned)}</td>
            </tr>
            <tr className="fin-balance__classe">
              <td colSpan={3}>Produits</td>
            </tr>
            {lignes(b.produits)}
            <tr className="fin-balance__total">
              <td>Total des produits</td>
              <td className="fin-balance__n">{euros(b.produits.realised)}</td>
              <td className="fin-balance__n">{euros(b.produits.planned)}</td>
            </tr>
            <tr className="fin-balance__total">
              <td>Résultat</td>
              <td className="fin-balance__n">{euros(b.realisedResult)}</td>
              <td className="fin-balance__n">{euros(b.result)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="muted">« Reprendre le réalisé » remplit chaque ligne avec le chiffre de {b.seasonName}, à corriger ensuite.</p>
      <div className="fin-cp-a">
        <button type="button" className="btn btn--secondary" onClick={reprendre}>
          Reprendre le réalisé
        </button>
        <button type="button" className="btn btn--primary" onClick={produire} disabled={!b.filled}>
          Produire le document
        </button>
      </div>
    </div>
  )
}
