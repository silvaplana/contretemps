import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import { telechargerFichier } from '../../utils/telechargement.js'
import Modal from '../../components/Modal.jsx'
import { ChoixPersonneModal } from './Pieces.jsx'
import { Vignette } from './commun.jsx'

// L'avis de virement gardé sur une transaction bancaire sans facture (§7 octies) : sa vignette.
function VignetteAvis({ transaction }) {
  return (
    <Vignette
      piece={{ id: `avis-${transaction.id}`, nom: transaction.avis.nom, type_mime: transaction.avis.type_mime, preuve: true, legende: 'Avis', charger: () => api.urlAvis(transaction.id) }}
    />
  )
}

// Ce que dit la transaction proposée quand elle a été justifiée sans facture ou porte un avis (Seb, 10/11 : l'appli demande, ne rattache pas seule).
export function texteSansFacture(sansFacture) {
  if (!sansFacture) return null
  const justifiee = sansFacture.raison ? `justifiée sans facture (« ${sansFacture.raison} »)` : ''
  const avis = sansFacture.avis ? 'porte un avis de virement' : ''
  return `Transaction bancaire ${[justifiee, avis].filter(Boolean).join(' et ')} : c’est elle ?`
}

// Puce Rapprocher de Financier › Pièces (notes-de-frais.md §7 septies, Seb
// 9/11) : le rapprochement par lots, comme un comptable. Les paires que
// l'appli propose entre une facture et une transaction bancaire (« Rattacher à
// cette transaction » lettre les deux), puis les factures sans paiement, puis les
// transactions bancaires de débit sans facture (à justifier sans facture ou dont
// on demande le justificatif, §7 octies). Rien n'est lettré sans un toucher.
export default function Rapprocher({ onChange, onOuvrir }) {
  const [periode, setPeriode] = useState(() => ({ debut: debutDeSaison(), fin: '' }))
  const [etat, setEtat] = useState(null)
  const [enCours, setEnCours] = useState(null)
  const [erreur, setErreur] = useState('')
  const [justifier, setJustifier] = useState(null) // transaction bancaire dont on dit pourquoi il n'y a pas de facture
  const [demander, setDemander] = useState(null) // transaction bancaire dont on demande le justificatif

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

  // Une action sur une transaction bancaire (justifier, retirer, demander), puis recharger.
  async function agir(id, action) {
    setEnCours(`t${id}`)
    try {
      await action()
      charger()
      onChange?.()
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(null)
    }
  }

  const [choisir, setChoisir] = useState(null) // facture pour laquelle on choisit la transaction à la main

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
        L’appli suggère les paires (même montant, même nom) ; pour chacune, vous rattachez la facture à sa transaction bancaire
        d’un toucher, ce qui les lettre. Le compte d’une transaction bancaire vient de la facture.
      </p>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!etat && !erreur && <p className="muted">Chargement…</p>}
      {etat && (
        <>
          <h3 className="nf-rapprocher__titre">
            Suggestions de rattachement <span className="muted">· {etat.paires.length}</span>
          </h3>
          {etat.paires.length === 0 && <p className="muted">Aucune : aucune transaction bancaire ne ressemble à une facture en attente.</p>}
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
                  {p.paire.operation.sans_facture && <span className="badge badge--warning">{texteSansFacture(p.paire.operation.sans_facture)}</span>}
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
                    Rattacher à cette transaction bancaire
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
              <div key={p.id} className="nf-ligne nf-ligne--actions">
                <button type="button" className="nf-ligne__corps nf-ligne__ouvrir" onClick={() => ouvrir(p)}>
                  <span className="nf-ligne__titre">{p.qui}</span>
                  <span className="muted">
                    {p.nature} du {api.dateCourte(p.date)}
                  </span>
                </button>
                <span className="nf-ligne__droite">
                  <span className="nf-ligne__montant">{api.euros(p.montant_centimes)}</span>
                  <span className={`badge ${p.etat === 'À rapprocher' || p.etat === 'À valider' ? 'badge--warning' : ''}`}>{p.etat}</span>
                  {p.etat !== 'Don' && etat.lignes_sans_piece.length > 0 && (
                    <button type="button" className="btn btn--link" disabled={enCours !== null} onClick={() => setChoisir(p)}>
                      Rattacher à une transaction bancaire…
                    </button>
                  )}
                </span>
              </div>
            ))}
          </div>

          <h3 className="nf-rapprocher__titre">
            Transactions bancaires sans facture <span className="muted">· {etat.lignes_sans_piece.length}</span>
          </h3>
          {etat.lignes_sans_piece.length === 0 && <p className="muted">Aucune : chaque transaction bancaire de débit de la période a sa pièce.</p>}
          {etat.lignes_sans_piece.length > 0 && (
            <p className="muted">Frais bancaires, honoraires, SACEM… : le libellé suffit souvent : « Justifier sans facture » le dit. Sinon, « Demander le justificatif » prévient la personne qui a payé. Un avis de virement reçu sans facture reste ici, sur sa transaction (Docs › Financier › VIREMENTS SANS FACTURE), jusqu’à la facture. Leur compte se choisit dans Comptes, filtre « Sans compte ».</p>
          )}
          <div className="nf-liste">
            {etat.lignes_sans_piece.map((l) => (
              <div key={l.id} className="nf-ligne">
                {l.avis && <VignetteAvis transaction={l} />}
                <span className="nf-ligne__corps">
                  <span className="nf-ligne__titre">{l.libelle}</span>
                  <span className="muted">
                    {api.dateCourte(l.date)}
                    {l.compte ? ` · ${l.compte}` : ''}
                    {l.avis ? ' · avis de virement reçu, facture attendue' : ''}
                  </span>
                  {l.demande && (
                    <span className="badge badge--warning">
                      justificatif demandé à {l.demande.personne} le {api.dateCourte(l.demande.le)}
                    </span>
                  )}
                </span>
                <span className="nf-ligne__droite nf-rapprocher__actions">
                  <span className="nf-ligne__montant">{api.euros(-l.montant_centimes)}</span>
                  <button type="button" className="btn btn--link" disabled={enCours !== null} onClick={() => setJustifier({ transaction: l, raison: '' })}>
                    Justifier sans facture
                  </button>
                  <button type="button" className="btn btn--link" disabled={enCours !== null} onClick={() => setDemander(l)}>
                    {l.demande ? 'Redemander le justificatif' : 'Demander le justificatif'}
                  </button>
                </span>
              </div>
            ))}
          </div>

          {etat.justifiees.length > 0 && (
            <>
              <h3 className="nf-rapprocher__titre">
                Transactions bancaires justifiées sans facture <span className="muted">· {etat.justifiees.length}</span>
              </h3>
              <div className="nf-liste">
                {etat.justifiees.map((l) => (
                  <div key={l.id} className="nf-ligne">
                    {l.avis && <VignetteAvis transaction={l} />}
                    <span className="nf-ligne__corps">
                      <span className="nf-ligne__titre">{l.libelle}</span>
                      <span className="muted">
                        {api.dateCourte(l.date)}
                        {l.compte ? ` · ${l.compte}` : ''} · {l.raison}
                      </span>
                    </span>
                    <span className="nf-ligne__droite nf-rapprocher__actions">
                      <span className="nf-ligne__montant">{api.euros(-l.montant_centimes)}</span>
                      <button type="button" className="btn btn--link" disabled={enCours !== null} onClick={() => agir(l.id, () => api.retirerJustification(l.id))}>
                        Retirer
                      </button>
                    </span>
                  </div>
                ))}
              </div>
            </>
          )}

          <p className="muted">
            {etat.rattachees.length} pièce{etat.rattachees.length > 1 ? 's' : ''} rattachée{etat.rattachees.length > 1 ? 's' : ''} à leur transaction
            bancaire sur la période.
          </p>
        </>
      )}

      {choisir && (
        <ChoixTransactionModal
          piece={choisir}
          transactions={etat.lignes_sans_piece}
          onClose={() => setChoisir(null)}
          onChoisie={(transaction) => {
            const piece = choisir
            setChoisir(null)
            setEnCours(piece.id)
            api
              .payee(piece.id, transaction.id, [], true)
              .then(() => {
                charger()
                onChange?.()
              })
              .catch((err) => setErreur(err.message))
              .finally(() => setEnCours(null))
          }}
        />
      )}
      {justifier && (
        <Modal
          title="Justifier sans facture"
          onClose={() => setJustifier(null)}
          footer={
            <div className="nf-boutons">
              <button type="button" className="btn btn--secondary" onClick={() => setJustifier(null)}>
                Annuler
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={!justifier.raison.trim()}
                onClick={() => {
                  const { transaction, raison } = justifier
                  setJustifier(null)
                  agir(transaction.id, () => api.justifierSansFacture(transaction.id, raison))
                }}
              >
                Justifier sans facture
              </button>
            </div>
          }
        >
          <p>
            {justifier.transaction.libelle} · {api.dateCourte(justifier.transaction.date)} · {api.euros(-justifier.transaction.montant_centimes)}
          </p>
          <label className="field">
            <span className="field-label">Pourquoi il n’y a pas de facture</span>
            <input
              type="text"
              className="field-input"
              placeholder="Frais bancaires, prélèvement SACEM…"
              value={justifier.raison}
              maxLength={200}
              autoFocus
              onChange={(e) => setJustifier({ ...justifier, raison: e.target.value })}
            />
          </label>
        </Modal>
      )}
      {demander && (
        <ChoixPersonneModal
          onClose={() => setDemander(null)}
          onChoisie={(personne) => {
            const transaction = demander
            setDemander(null)
            agir(transaction.id, () => api.demanderJustificatif(transaction.id, personne.person_id))
          }}
        />
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
// Lettrage à la main (Seb, 10/11) : la facture et la liste des transactions
// bancaires sans facture de la période, les montants les plus proches en
// premier ; un toucher rattache, l'écart éventuel reste à régler dans la fiche.
function ChoixTransactionModal({ piece, transactions, onClose, onChoisie }) {
  const [filtre, setFiltre] = useState('')
  const mot = filtre.trim().toLowerCase()
  const liste = transactions
    .filter((t) => !mot || t.libelle.toLowerCase().includes(mot))
    .slice()
    .sort((a, b) => Math.abs(-a.montant_centimes - piece.montant_centimes) - Math.abs(-b.montant_centimes - piece.montant_centimes))
  return (
    <Modal title="Rattacher à une transaction bancaire" onClose={onClose}>
      <p>
        {piece.qui} · {piece.nature} du {api.dateCourte(piece.date)} · {api.euros(piece.montant_centimes)}
      </p>
      <input
        type="search"
        className="field-input"
        placeholder="Chercher dans les libellés"
        value={filtre}
        onChange={(e) => setFiltre(e.target.value)}
      />
      <div className="nf-liste">
        {liste.map((t) => {
          const diff = -t.montant_centimes - piece.montant_centimes
          return (
            <button key={t.id} type="button" className="nf-ligne" onClick={() => onChoisie(t)}>
              <span className="nf-ligne__corps">
                <span className="nf-ligne__titre">{t.libelle}</span>
                <span className="muted">
                  {api.dateCourte(t.date)} · {t.compte}
                  {diff !== 0 && ` · écart ${ecart(diff)}`}
                </span>
              </span>
              <span className="nf-ligne__montant">{api.euros(-t.montant_centimes)}</span>
            </button>
          )
        })}
        {liste.length === 0 && <p className="muted">Aucune transaction bancaire sans facture ne correspond.</p>}
      </div>
    </Modal>
  )
}

function debutDeSaison() {
  const jour = new Date()
  const annee = jour.getMonth() >= 8 ? jour.getFullYear() : jour.getFullYear() - 1
  return `${annee}-09-01`
}

function ecart(centimes) {
  return `${centimes > 0 ? '+' : ''}${api.euros(centimes)}`
}
