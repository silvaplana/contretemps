// Puces À rattacher et Ventes de Financier › Pièces (spec/modules/
// financier.md §8.3), EXEMPLE : proposition de la ligne de banque,
// confirmation du trésorier. Tout vit en mémoire (exemple/donnees.js). Les
// puces Notes de frais, Honoraires, Achats et Virements sont réelles
// (notes-frais/Pieces.jsx).
import { useState } from 'react'
import BandeExemple from './BandeExemple.jsx'
import { DOSSIERS, PIECES, PLAN, dateFr, eur } from './donnees.js'

const compteLabel = (num) => {
  const c = PLAN.find((x) => x.num === num)
  return c ? `${c.num} ${c.label}` : 'Compte à choisir'
}

export default function PiecesExemple({ dossier }) {
  const [pieces, setPieces] = useState(PIECES)
  const [message, setMessage] = useState('')

  function changer(id, etat, ligne) {
    setPieces((p) => p.map((x) => (x.id === id ? { ...x, etat, ligne: ligne ?? x.ligne } : x)))
    setMessage(
      etat === 'rattachee'
        ? 'Pièce rattachée à la ligne de banque (exemple : rien n’est enregistré).'
        : etat === 'non_payee'
          ? 'Pièce gardée dans son dossier : elle passe dans Virements, À payer, et compte dans « Fournisseurs à payer ».'
          : 'Pièce rattachée à une ligne de caisse.',
    )
  }

  const visibles = dossier === 'a_rattacher' ? pieces.filter((p) => p.etat === 'a_rattacher') : pieces.filter((p) => p.dossier === dossier)

  return (
    <section className="fin-ex" aria-label="Pièces">
      <BandeExemple />
      {message && <p className="history-report">{message}</p>}
      {visibles.length === 0 && <p className="muted">Rien dans ce dossier.</p>}
      {visibles.map((p) => (
        <Piece key={p.id} piece={p} onChanger={changer} />
      ))}
    </section>
  )
}

function Piece({ piece, onChanger }) {
  const [cheques, setCheques] = useState(false)
  const prop = piece.proposition
  return (
    <div className="fin-ex-carte">
      <div className="fin-ex-piece">
        {piece.url ? (
          <img className="fin-ex-photo" src={piece.url} alt="" />
        ) : (
          <div className="fin-ex-photo">{piece.photo}</div>
        )}
        <div>
          <b>{piece.titre}</b>
          <span className="muted">
            {piece.detail}
            {piece.dossier && ` · ${DOSSIERS.find((d) => d.id === piece.dossier)?.label}`}
            {piece.compte && ` · ${compteLabel(piece.compte)}`}
          </span>
          {piece.etat === 'a_rattacher' && !piece.lecture && (
            <div className={prop ? 'fin-ex-proposition' : 'fin-ex-proposition fin-ex-proposition--aucune'}>
              {prop ? (
                <>
                  <b>
                    {prop.libelle} · {prop.montant > 0 ? '+' : ''}
                    {eur(prop.montant)}
                  </b>{' '}
                  le {dateFr(prop.date)} · {prop.pourquoi}
                </>
              ) : (
                <b>Aucune ligne de banque ne correspond pour l’instant</b>
              )}
            </div>
          )}
          {piece.etat === 'rattachee' && <span className="badge badge--success">Rattachée : {piece.ligne}</span>}
          {piece.etat === 'non_payee' && <span className="badge badge--warning">À payer</span>}
          {piece.etat === 'especes' && <span className="badge badge--success">{piece.ligne}</span>}
        </div>
      </div>
      {piece.cheques && (
        <>
          <button type="button" className="btn btn--link" onClick={() => setCheques((v) => !v)}>
            {cheques ? 'Masquer les chèques' : `Voir les ${piece.cheques.length - 1 + 20} chèques`}
          </button>
          {cheques && (
            <table className="fin-ex-table">
              <tbody>
                {piece.cheques.map((c) => (
                  <tr key={c.nom}>
                    <td>{c.nom}</td>
                    <td className="muted">{c.famille ? `${c.famille} · Cours` : ''}</td>
                    <td className="r">{eur(c.montant)}</td>
                  </tr>
                ))}
                <tr className="tot">
                  <td colSpan={2}>Total, égal au ticket de dépôt</td>
                  <td className="r">{eur(3795)}</td>
                </tr>
              </tbody>
            </table>
          )}
        </>
      )}
      {piece.etat === 'a_rattacher' && !piece.lecture && (
        <div className="fin-ex-boutons">
          {prop ? (
            <>
              <button type="button" className="btn btn--primary" onClick={() => onChanger(piece.id, 'rattachee', `${prop.libelle} le ${dateFr(prop.date)}`)}>
                Confirmer
              </button>
              <button type="button" className="btn btn--secondary" onClick={() => onChanger(piece.id, 'rattachee', 'ligne choisie à la main')}>
                Autre ligne
              </button>
            </>
          ) : (
            <>
              <button type="button" className="btn btn--secondary" onClick={() => onChanger(piece.id, 'non_payee')}>
                Pas encore payée
              </button>
              <button type="button" className="btn btn--secondary" onClick={() => onChanger(piece.id, 'especes', 'Caisse')}>
                Payée en espèces
              </button>
            </>
          )}
        </div>
      )}
    </div>
  )
}
