import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import { telechargerFichier } from '../../utils/telechargement.js'

// Puce Rapprocher de Financier › Pièces (notes-de-frais.md §7 septies, Seb
// 9/11) : le rapprochement par lots, comme un comptable. Les paires que
// l'appli propose entre une facture et une transaction bancaire (« Rattacher à
// cette transaction » lettre les deux), puis les factures sans paiement, puis les
// transactions de débit sans facture. Rien n'est lettré sans un toucher.
export default function Rapprocher({ onChange, onOuvrir }) {
  const [periode, setPeriode] = useState(() => ({ debut: debutDeSaison(), fin: '' }))
  const [etat, setEtat] = useState(null)
  const [enCours, setEnCours] = useState(null)
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api
      .rapprochement(periode.debut, periode.fin)
      .then((d) => {
        setEtat(d)
        setErreur('')
      })
      .catch((err) => setErreur(err.message))
  }, [periode])
  useEffect(charger, [charger])

  async function rattacher(piece) {
    setEnCours(piece.id)
    try {
      await api.payee(piece.id, piece.paire.operation.id, piece.paire.aussi?.map((a) => a.id) ?? [])
      charger()
      onChange()
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(null)
    }
  }

  // La fiche complète d'une pièce (la liste de sa nature la porte).
  async function ouvrir(piece) {
    try {
      const { notes } = await api.tresorerie(piece.nature_code)
      const note = notes.find((n) => n.id === piece.id)
      if (note) onOuvrir(note)
    } catch (err) {
      setErreur(err.message)
    }
  }

  return (
    <div className="nf-depot nf-rapprocher">
      <p className="muted">
        Le rapprochement se fait par lots : toutes les factures et toutes les transactions bancaires de la période, d’un coup.
        L’appli suggère les paires (même montant, même nom) ; pour chacune, vous rattachez la facture à sa transaction d’un
        toucher, ce qui les lettre. Le compte d’une transaction vient de la facture.
      </p>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!etat && !erreur && <p className="muted">Chargement…</p>}
      {etat && (
        <>
          <h3 className="nf-rapprocher__titre">
            Suggestions de rattachement <span className="muted">· {etat.paires.length}</span>
          </h3>
          {etat.paires.length === 0 && <p className="muted">Aucune : aucune transaction ne ressemble à une facture en attente.</p>}
          <div className="nf-liste">
            {etat.paires.map((p) => (
              <div key={p.id} className="nf-ligne nf-rapprocher__paire">
                <span className="nf-ligne__corps">
                  <span className="nf-ligne__titre">
                    {p.qui} · {api.euros(p.montant_centimes)}
                  </span>
                  <span className="muted">
                    {p.nature} du {api.dateCourte(p.date)}
                  </span>
                  <span className="nf-rapprocher__banque">
                    Transaction du {api.dateCourte(p.paire.operation.date)} · {p.paire.operation.libelle} ·{' '}
                    {api.euros(-p.paire.operation.montant_centimes)}
                    {p.paire.operation.compte ? ` · ${p.paire.operation.compte}` : ''}
                  </span>
                  <span>
                    {p.paire.sure ? (
                      <span className="badge badge--success">même nom, même montant</span>
                    ) : p.paire.aussi?.length ? (
                      <span className="badge badge--warning">paie aussi : {p.paire.aussi.map((a) => a.titre).join(', ')}</span>
                    ) : p.paire.ecart_centimes ? (
                      <span className="badge badge--warning">écart {ecart(p.paire.ecart_centimes)}</span>
                    ) : (
                      <span className="badge badge--warning">même montant, autre nom</span>
                    )}
                  </span>
                </span>
                <span className="nf-ligne__droite nf-rapprocher__actions">
                  <button type="button" className="btn btn--primary" disabled={enCours !== null} onClick={() => rattacher(p)}>
                    Rattacher à cette transaction
                  </button>
                  <button type="button" className="btn btn--link" disabled={enCours !== null} onClick={() => ouvrir(p)}>
                    Autre…
                  </button>
                </span>
              </div>
            ))}
          </div>

          <h3 className="nf-rapprocher__titre">
            Factures sans paiement <span className="muted">· {etat.sans_paiement.length}</span>
          </h3>
          {etat.sans_paiement.length === 0 && <p className="muted">Aucune.</p>}
          <div className="nf-liste">
            {etat.sans_paiement.map((p) => (
              <button key={p.id} type="button" className="nf-ligne" onClick={() => ouvrir(p)}>
                <span className="nf-ligne__corps">
                  <span className="nf-ligne__titre">{p.qui}</span>
                  <span className="muted">
                    {p.nature} du {api.dateCourte(p.date)}
                  </span>
                </span>
                <span className="nf-ligne__droite">
                  <span className="nf-ligne__montant">{api.euros(p.montant_centimes)}</span>
                  <span className={`badge ${p.etat === 'À rapprocher' || p.etat === 'À valider' ? 'badge--warning' : ''}`}>{p.etat}</span>
                </span>
              </button>
            ))}
          </div>

          <h3 className="nf-rapprocher__titre">
            Transactions bancaires sans facture <span className="muted">· {etat.lignes_sans_piece.length}</span>
          </h3>
          {etat.lignes_sans_piece.length === 0 && <p className="muted">Aucune : chaque transaction de débit de la période a sa pièce.</p>}
          {etat.lignes_sans_piece.length > 0 && (
            <p className="muted">Frais bancaires, honoraires, SACEM… : le libellé suffit souvent. Leur compte se choisit dans Comptes, filtre « Sans compte ».</p>
          )}
          <div className="nf-liste">
            {etat.lignes_sans_piece.map((l) => (
              <div key={l.id} className="nf-ligne">
                <span className="nf-ligne__corps">
                  <span className="nf-ligne__titre">{l.libelle}</span>
                  <span className="muted">
                    {api.dateCourte(l.date)}
                    {l.compte ? ` · ${l.compte}` : ''}
                  </span>
                </span>
                <span className="nf-ligne__droite">
                  <span className="nf-ligne__montant">{api.euros(-l.montant_centimes)}</span>
                </span>
              </div>
            ))}
          </div>

          <p className="muted">
            {etat.rattachees.length} pièce{etat.rattachees.length > 1 ? 's' : ''} rattachée{etat.rattachees.length > 1 ? 's' : ''} à leur transaction
            bancaire sur la période.
          </p>
        </>
      )}

      <div className="nf-periode">
        <label>
          Du
          <input type="date" className="field-input" value={periode.debut} onChange={(e) => setPeriode({ ...periode, debut: e.target.value })} />
        </label>
        <label>
          au
          <input type="date" className="field-input" value={periode.fin} onChange={(e) => setPeriode({ ...periode, fin: e.target.value })} />
        </label>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() =>
            telechargerFichier(api.urlRapprochement(periode.debut, periode.fin), 'Rapprochement des pièces.pdf').catch((err) =>
              setErreur(err.message),
            )
          }
        >
          <Icon name="fileCheck" size={18} /> Rapprochement PDF
        </button>
      </div>
    </div>
  )
}

// Le 1er septembre de la saison en cours (les saisons de l'école vont de septembre à août).
function debutDeSaison() {
  const jour = new Date()
  const annee = jour.getMonth() >= 8 ? jour.getFullYear() : jour.getFullYear() - 1
  return `${annee}-09-01`
}

function ecart(centimes) {
  return `${centimes > 0 ? '+' : ''}${api.euros(centimes)}`
}
