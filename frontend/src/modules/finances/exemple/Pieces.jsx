// Sous-onglet Pièces (spec/modules/financier.md §8.3), EXEMPLE : le
// classeur des justificatifs, par dossier de l'association ; photo en
// rafale ; proposition de la ligne de banque, confirmation du trésorier.
// Tout vit en mémoire (exemple/donnees.js).
import { useEffect, useRef, useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import BandeExemple from './BandeExemple.jsx'
import Virements from './Virements.jsx'
import { DOSSIERS, PIECES, PLAN, VIREMENTS, dateFr, eur } from './donnees.js'

const PHOTO_EVENT = 'finances-photo-pieces'

// Entrée « Photographier des pièces » du menu ⋯ (voir Financier.jsx).
export function requestPhotoPieces() {
  window.dispatchEvent(new Event(PHOTO_EVENT))
}

const compteLabel = (num) => {
  const c = PLAN.find((x) => x.num === num)
  return c ? `${c.num} ${c.label}` : 'Compte à choisir'
}

export default function Pieces() {
  const [dossier, setDossier] = useState('a_rattacher')
  const [pieces, setPieces] = useState(PIECES)
  const [message, setMessage] = useState('')
  const camera = useRef(null)

  useEffect(() => {
    const open = () => camera.current?.click()
    window.addEventListener(PHOTO_EVENT, open)
    return () => window.removeEventListener(PHOTO_EVENT, open)
  }, [])

  // Une photo = une pièce « à rattacher », lue en arrière-plan (simulé ici).
  function photos(files) {
    const nouvelles = [...files].map((f, i) => ({
      id: `photo-${Date.now()}-${i}`,
      dossier: null,
      titre: 'Lecture de la pièce…',
      detail: f.name,
      url: URL.createObjectURL(f),
      compte: null,
      etat: 'a_rattacher',
      lecture: true,
      proposition: null,
    }))
    setPieces((p) => [...nouvelles, ...p])
    setDossier('a_rattacher')
    setTimeout(() => {
      setPieces((p) =>
        p.map((x) =>
          nouvelles.some((n) => n.id === x.id)
            ? { ...x, lecture: false, titre: 'Pièce lue (exemple)', detail: 'Fournisseur, date et montant seront lus ici ; dossier et compte proposés.' }
            : x,
        ),
      )
    }, 1500)
  }

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

  const aRattacher = pieces.filter((p) => p.etat === 'a_rattacher')
  const visibles = dossier === 'a_rattacher' ? aRattacher : pieces.filter((p) => p.dossier === dossier)

  return (
    <section className="fin-ex" aria-label="Pièces">
      <BandeExemple />
      <div className="filter-chips" role="group" aria-label="Dossiers">
        {DOSSIERS.map((d) => (
          <button
            key={d.id}
            type="button"
            className={d.id === dossier ? 'filter-chip filter-chip-active' : 'filter-chip'}
            aria-pressed={d.id === dossier}
            onClick={() => setDossier(d.id)}
          >
            {d.label}
            {d.id === 'a_rattacher' && aRattacher.length > 0 && ` (${aRattacher.length})`}
            {d.id === 'virements' && ` (${VIREMENTS.filter((v) => v.etat !== 'paye').length})`}
          </button>
        ))}
      </div>
      {dossier !== 'virements' && (
        <button type="button" className="btn btn--primary" onClick={() => camera.current?.click()}>
          <Icon name="camera" size={18} /> Photographier des pièces
        </button>
      )}
      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        hidden
        onChange={(e) => {
          photos(e.target.files)
          e.target.value = ''
        }}
      />
      {dossier !== 'virements' && (
        <p className="muted">
          Une pièce par photo, sans rien saisir. L’appli lit la pièce, la range dans son dossier et propose la ligne de
          banque : vous confirmez. Les notes de frais validées et les virements HelloAsso arrivent déjà rattachés.
        </p>
      )}
      {dossier === 'virements' ? (
        <Virements />
      ) : (
        <>
          {message && <p className="history-report">{message}</p>}
          {visibles.length === 0 && <p className="muted">Rien dans ce dossier.</p>}
          {visibles.map((p) => (
            <Piece key={p.id} piece={p} onChanger={changer} />
          ))}
        </>
      )}
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
