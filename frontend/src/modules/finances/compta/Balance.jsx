// Comptes ⋯ › « Balance » (spec/modules/financier.md §8.6) : la Balance
// recalculée à chaque ouverture, avec la période dite en clair. Saison par
// défaut : la plus ancienne commencée et pas encore clôturée (choix du
// serveur) ; Du / Au resserrent la période. Un compte touché montre ses
// écritures, comme au Grand livre ; une pièce touchée ouvre sa fiche.
import { useEffect, useState } from 'react'
import { telechargerFichier } from '../../../utils/telechargement.js'
import * as api from '../api.js'
import { requestFichePiece } from '../navigation.js'
import './compta.css'

const BALANCE_EVENT = 'finances-balance'

// Entrée « Balance » du menu ⋯ (voir Financier.jsx).
export function requestBalance() {
  window.dispatchEvent(new Event(BALANCE_EVENT))
}

export const BALANCE_EVENTS = { balance: BALANCE_EVENT }

const CLASSES = {
  1: 'Classe 1 · Fonds associatifs',
  2: 'Classe 2 · Immobilisations',
  3: 'Classe 3 · Stocks',
  4: 'Classe 4 · Tiers',
  5: 'Classe 5 · Financiers',
  6: 'Classe 6 · Charges',
  7: 'Classe 7 · Produits',
}
const FILTRES = [
  { id: 'tous', label: 'Tous les comptes' },
  { id: 'bilan', label: 'Bilan (classes 1 à 5)' },
  { id: 'resultat', label: 'Résultat (classes 6 et 7)' },
]
const MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']

// « 1er septembre 2025 »
function dateLongue(iso) {
  const [a, m, j] = iso.split('-').map(Number)
  return `${j === 1 ? '1er' : j} ${MOIS[m - 1]} ${a}`
}

const cents = (v) => Math.round(v * 100)
const eur = (c) => (c ? api.euros(c / 100) : '')

// [débit, crédit, solde débiteur, solde créditeur] en centimes.
function sommes(comptes) {
  return comptes.reduce(
    (t, c) => {
      const d = cents(c.debit)
      const cr = cents(c.credit)
      return [t[0] + d, t[1] + cr, t[2] + Math.max(d - cr, 0), t[3] + Math.max(cr - d, 0)]
    },
    [0, 0, 0, 0],
  )
}

function LigneTotal({ libelle, t, className }) {
  return (
    <tr className={className}>
      <td></td>
      <td>{libelle}</td>
      {t.map((v, i) => (
        <td key={i} className="fin-balance__n">{eur(v)}</td>
      ))}
    </tr>
  )
}

export default function Balance({ onClose }) {
  const [data, setData] = useState(null)
  const [demande, setDemande] = useState({}) // { seasonId, start, end }
  const [filtre, setFiltre] = useState('tous')
  const [ouverts, setOuverts] = useState(() => new Set())
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    let actif = true
    api
      .balance(demande)
      .then((d) => {
        if (actif) {
          setData(d)
          setErreur('')
        }
      })
      .catch((err) => actif && setErreur(err.message))
    return () => {
      actif = false
    }
  }, [demande])

  const saison = data?.seasons.find((s) => s.id === data.seasonId)

  function basculer(numero) {
    setOuverts((o) => {
      const n = new Set(o)
      if (n.has(numero)) n.delete(numero)
      else n.add(numero)
      return n
    })
  }

  function telecharger() {
    telechargerFichier(api.urlBalancePdf(data.seasonId, data.start, data.end), `Balance ${data.seasonName}.pdf`).catch((err) =>
      setErreur(err.message),
    )
  }

  const classe = (c) => Number(c.number[0])
  const gardes = (data?.accounts ?? []).filter(
    (c) => filtre === 'tous' || (filtre === 'bilan' ? classe(c) <= 5 : classe(c) >= 6),
  )
  const totalDebit = (data?.accounts ?? []).reduce((s, c) => s + cents(c.debit), 0)
  const totalCredit = (data?.accounts ?? []).reduce((s, c) => s + cents(c.credit), 0)

  return (
    <div className="fin-cp fin-balance">
      <button type="button" className="btn btn--link fin-releves__retour" onClick={onClose}>
        ← Comptes
      </button>
      <div className="fin-balance__titre">
        <h3>Balance {data?.seasonName ?? ''}</h3>
        {data && (
          <p className="fin-balance__periode">
            Période : du {dateLongue(data.start)} au {dateLongue(data.end)}
          </p>
        )}
        <p className="muted">
          Recalculée chaque fois qu’on ouvre cet écran, avec tout ce qui est enregistré
          {data && data.knownUntil < data.end ? ` ; transactions bancaires connues jusqu’au ${dateLongue(data.knownUntil)}` : ''}.
        </p>
      </div>

      {data && (
        <div className="fin-balance__filtres">
          <label>
            Saison
            <select
              className="field-input"
              value={data.seasonId}
              onChange={(e) => setDemande({ seasonId: Number(e.target.value) })}
            >
              {data.seasons.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Du
            <input
              type="date"
              className="field-input"
              value={data.start}
              min={saison?.start}
              max={data.end}
              onChange={(e) => e.target.value && setDemande({ seasonId: data.seasonId, start: e.target.value, end: data.end })}
            />
          </label>
          <label>
            Au
            <input
              type="date"
              className="field-input"
              value={data.end}
              min={data.start}
              max={saison?.end}
              onChange={(e) => e.target.value && setDemande({ seasonId: data.seasonId, start: data.start, end: e.target.value })}
            />
          </label>
          <button type="button" className="btn btn--primary" onClick={telecharger}>
            Télécharger le PDF
          </button>
        </div>
      )}

      {erreur && <p className="login-screen__erreur">{erreur}</p>}

      {data && (
        <>
          <div className="filter-chips" role="group" aria-label="Comptes affichés">
            {FILTRES.map((f) => (
              <button
                key={f.id}
                type="button"
                className={`filter-chip${filtre === f.id ? ' filter-chip-active' : ''}`}
                aria-pressed={filtre === f.id}
                onClick={() => setFiltre(f.id)}
              >
                {f.label}
              </button>
            ))}
          </div>

          {gardes.length === 0 ? (
            <p className="muted">Aucune écriture sur cette période.</p>
          ) : (
            <div className="fin-balance__table">
              <table>
                <thead>
                  <tr>
                    <th rowSpan={2}>Compte</th>
                    <th rowSpan={2}>Libellé</th>
                    <th colSpan={2} className="fin-balance__n">Total période</th>
                    <th colSpan={2} className="fin-balance__n">Solde</th>
                  </tr>
                  <tr>
                    <th className="fin-balance__n">Débit</th>
                    <th className="fin-balance__n">Crédit</th>
                    <th className="fin-balance__n">Débit</th>
                    <th className="fin-balance__n">Crédit</th>
                  </tr>
                </thead>
                <tbody>
                  {[...new Set(gardes.map(classe))].map((k) => {
                    const groupe = gardes.filter((c) => classe(c) === k)
                    return [
                      <tr key={`c${k}`} className="fin-balance__classe">
                        <td colSpan={6}>{CLASSES[k] ?? `Classe ${k}`}</td>
                      </tr>,
                      ...groupe.flatMap((c) => {
                        const [d, cr, sd, sc] = sommes([c])
                        const ouvert = ouverts.has(c.number)
                        const lignes = [
                          <tr
                            key={c.number}
                            className={`fin-balance__compte${ouvert ? ' fin-balance__compte--ouvert' : ''}`}
                            tabIndex={0}
                            aria-expanded={ouvert}
                            onClick={() => basculer(c.number)}
                            onKeyDown={(e) => e.key === 'Enter' && basculer(c.number)}
                          >
                            <td>
                              <span className="fin-balance__chev">›</span> {c.number}
                            </td>
                            <td>{c.label}</td>
                            <td className="fin-balance__n">{eur(d)}</td>
                            <td className="fin-balance__n">{eur(cr)}</td>
                            <td className="fin-balance__n">{eur(sd)}</td>
                            <td className="fin-balance__n">{eur(sc)}</td>
                          </tr>,
                        ]
                        if (ouvert) {
                          lignes.push(
                            <tr key={`${c.number}-detail`} className="fin-balance__detail">
                              <td colSpan={6}>
                                <table>
                                  <thead>
                                    <tr>
                                      <th>Date</th>
                                      <th>Pièce</th>
                                      <th>Libellé</th>
                                      <th className="fin-balance__n">Débit</th>
                                      <th className="fin-balance__n">Crédit</th>
                                      <th>Lettre</th>
                                    </tr>
                                  </thead>
                                  <tbody>
                                    {c.lines.map((l, i) => (
                                      <tr key={i}>
                                        <td>{api.dateFr(l.date)}</td>
                                        <td>
                                          {l.pieceId ? (
                                            <button type="button" className="btn btn--link fin-balance__piece" onClick={() => requestFichePiece(l.pieceId)}>
                                              {l.piece}
                                            </button>
                                          ) : (
                                            l.piece || l.journal
                                          )}
                                        </td>
                                        <td>{l.label}</td>
                                        <td className="fin-balance__n">{eur(cents(l.debit))}</td>
                                        <td className="fin-balance__n">{eur(cents(l.credit))}</td>
                                        <td>{l.letter}</td>
                                      </tr>
                                    ))}
                                  </tbody>
                                </table>
                              </td>
                            </tr>,
                          )
                        }
                        return lignes
                      }),
                      <LigneTotal key={`t${k}`} libelle={`Total classe ${k}`} t={sommes(groupe)} className="fin-balance__st" />,
                    ]
                  })}
                  {filtre !== 'resultat' && (
                    <LigneTotal libelle="Total des comptes de Bilan" t={sommes(gardes.filter((c) => classe(c) <= 5))} className="fin-balance__total" />
                  )}
                  {filtre !== 'bilan' && (
                    <LigneTotal libelle="Total des comptes de Résultat" t={sommes(gardes.filter((c) => classe(c) >= 6))} className="fin-balance__total" />
                  )}
                  {filtre === 'tous' && <LigneTotal libelle="Total de la Balance" t={sommes(gardes)} className="fin-balance__total" />}
                </tbody>
              </table>
            </div>
          )}

          {gardes.length > 0 && totalDebit === totalCredit && (
            <p className="fin-balance__equilibre">✓ Équilibrée : total des débits = total des crédits</p>
          )}
          {totalDebit !== totalCredit && (
            <p className="fin-cp-alerte">
              Pas équilibrée : {api.euros(totalDebit / 100)} au débit, {api.euros(totalCredit / 100)} au crédit.
            </p>
          )}
        </>
      )}
    </div>
  )
}
