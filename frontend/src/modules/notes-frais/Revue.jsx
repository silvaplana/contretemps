import { useState } from 'react'
import * as api from '../../api/notesFrais.js'
import { NATURES, qui } from './commun.jsx'
import { texteSansFacture } from './Rapprocher.jsx'

// Revue d'un import (notes-de-frais.md §7 quinquies, Seb 6/11) : une ligne
// par pièce avec ce que l'appli propose (nature, qui, rangement dans Docs,
// ligne du compte) et trois choix : Valider, Autre… (la fiche), Plus tard.
// Sans ligne trouvée, « Déjà payée » (§7 septies, Seb 9/11) : la facture
// s'enregistre sans chercher, le paiement se retrouve dans Rapprocher.
// Sur ordinateur, un tableau ; sur téléphone, les mêmes lignes en cartes.
export default function Revue({ notes: initiales, batchId, onOuvrir, onFermer, onChange }) {
  const [notes, setNotes] = useState(initiales)
  const [faites, setFaites] = useState({}) // id -> { genre: 'ok' | 'tard' | 'non', texte }
  const [enCours, setEnCours] = useState(null) // id ou 'toutes'
  const [erreurs, setErreurs] = useState({})

  const restantes = notes.filter((n) => !faites[n.id])
  const sures = restantes.filter(sure)

  function remplacer(note) {
    setNotes((l) => l.map((n) => (n.id === note.id ? note : n)))
  }

  async function agir(note, action, genre, texte) {
    setEnCours(note.id)
    setErreurs((e) => ({ ...e, [note.id]: '' }))
    try {
      const apres = await action()
      if (apres) remplacer(apres)
      setFaites((f) => ({ ...f, [note.id]: { genre, texte: typeof texte === 'function' ? texte(apres ?? note) : texte } }))
      onChange()
    } catch (err) {
      setErreurs((e) => ({ ...e, [note.id]: err.message }))
    } finally {
      setEnCours(null)
    }
  }

  // Valider : Payé si la banque a déjà la ligne, « C'est ce paiement » si une
  // ligne est proposée avec écart, sinon À payer.
  function valider(note) {
    const possible = proposee(note)
    const action = () =>
      note.operation || !possible ? api.valider(note.id) : api.payee(note.id, possible.operation.id, possible.aussi?.map((a) => a.id) ?? [])
    return agir(note, action, 'ok', (n) => `${n.statut === 'remboursee' ? 'Validée : Payé' : 'Validée : À payer'}${n.rangement ? ` · rangée dans ${n.rangement}` : ''}`)
  }

  // Nom lu à une lettre près d'une personne de l'école : l'appli propose, la
  // trésorière confirme ; la pièce reste à décider (Valider, Autre…, Plus tard).
  async function confirmerPersonne(note) {
    setEnCours(note.id)
    setErreurs((e) => ({ ...e, [note.id]: '' }))
    try {
      remplacer(await api.accepterPersonne(note.id))
      onChange()
    } catch (err) {
      setErreurs((e) => ({ ...e, [note.id]: err.message }))
    } finally {
      setEnCours(null)
    }
  }

  function dejaPayee(note) {
    return agir(note, () => api.dejaPayee(note.id), 'ok', (n) => `Validée : déjà payée, à rapprocher${n.rangement ? ` · rangée dans ${n.rangement}` : ''}`)
  }

  async function validerSures() {
    setEnCours('toutes')
    for (const note of sures) await valider(note)
    setEnCours(null)
  }

  // La fiche (« Autre… ») a changé ou défait la pièce : on la relit.
  async function relire(note) {
    try {
      const { notes: liste } = await api.tresorerie(note.nature === 'frais' ? 'frais' : note.nature)
      const apres = liste.find((n) => n.id === note.id)
      if (!apres) setFaites((f) => ({ ...f, [note.id]: { genre: 'non', texte: 'Annulée' } }))
      else if (apres.statut === 'envoyee' && !apres.plus_tard) remplacer(apres)
      else {
        remplacer(apres)
        setFaites((f) => ({ ...f, [note.id]: { genre: apres.statut === 'refusee' ? 'non' : apres.plus_tard ? 'tard' : 'ok', texte: decision(apres) } }))
      }
    } catch {
      /* la liste se relira à la fermeture */
    }
    onChange()
  }

  return (
    <section className="nf-revue" aria-label="Revue de l’import">
      <h3 className="nf-revue__titre">Revue de l’import</h3>
      <p className="muted">
        {restantes.length
          ? `${notes.length} pièce${notes.length > 1 ? 's' : ''}, ${notes.length - restantes.length} décidée${notes.length - restantes.length > 1 ? 's' : ''}. L’appli est sûre pour ${sures.length} : même nom, même montant sur le compte.`
          : 'Toutes les pièces sont décidées. Ce qui est « plus tard » ou refusé attend dans À trancher.'}
      </p>
      <div className="nf-revue__barre">
        <button type="button" className="btn btn--primary" disabled={!sures.length || enCours !== null} onClick={validerSures}>
          Valider les pièces sûres ({sures.length})
        </button>
        <button type="button" className="btn btn--secondary" onClick={onFermer}>
          {restantes.length ? 'Fermer : le reste attend dans sa puce' : 'Fermer'}
        </button>
      </div>
      <div className="nf-revue__liste">
        {notes.map((n) => {
          const faite = faites[n.id]
          const possible = proposee(n)
          return (
            <article key={n.id} className={faite ? 'nf-revue__piece nf-revue__piece--faite' : 'nf-revue__piece'}>
              <header className="nf-revue__entete">
                <span className="nf-revue__fichier">{n.depenses[0]?.pieces[0]?.nom || n.titre}</span>
                <span className="nf-revue__montant">{n.total_centimes ? api.euros(n.total_centimes) : 'Montant ?'}</span>
                <span className="muted">
                  {api.dateCourte(n.depenses[0]?.date ?? n.envoyee_le)}
                  {n.depenses[0]?.date_approximative ? ' · date à vérifier' : ''}
                </span>
              </header>
              {n.doublon_de ? (
                <p className="nf-revue__doublon">Même fichier que la pièce n° {n.doublon_de}, déjà enregistrée : refusez celle-ci si c’est un doublon.</p>
              ) : null}
              {!faite && n.personne_proposee ? (
                <p className="nf-revue__proposition">
                  Le nom lu ressemble à <strong>{n.personne_proposee.nom}</strong>. Est-ce bien {n.personne_proposee.role === 'prof' ? 'elle qui a facturé' : 'elle qui a payé'} ?{' '}
                  <button type="button" className="btn btn--secondary" disabled={enCours !== null} onClick={() => confirmerPersonne(n)}>
                    Oui, c’est {n.personne_proposee.nom}
                  </button>
                </p>
              ) : null}
              <dl className="nf-revue__bloc">
                <dt>Nature</dt>
                <dd>{NATURES[n.nature]}</dd>
                <dt>Qui</dt>
                <dd>{qui(n)}{n.nature !== 'achat' && n.personne?.role ? <span className="muted"> ({n.personne.role})</span> : null}</dd>
                <dt>Rangement</dt>
                <dd className="muted">{n.rangement ? `Docs › ${n.rangement}` : 'Choisissez pour qui d’abord'}</dd>
              </dl>
              <dl className="nf-revue__bloc">
                <dt>Transaction bancaire</dt>
                <dd>
                  {n.operation ? (
                    <>
                      {api.dateCourte(n.operation.date)} · {n.operation.libelle} · {api.euros(-n.operation.montant_centimes)}{' '}
                      <span className="badge badge--success">même nom, même montant</span>
                    </>
                  ) : possible ? (
                    <>
                      {api.dateCourte(possible.operation.date)} · {possible.operation.libelle} · {api.euros(-possible.operation.montant_centimes)}{' '}
                      <span className="badge badge--warning">
                        {possible.meme_montant
                          ? 'même montant, autre nom'
                          : possible.aussi?.length
                            ? `paie aussi : ${possible.aussi.map((a) => a.titre).join(', ')}`
                            : `écart ${ecart(possible.ecart_centimes)}`}
                      </span>
                      {possible.operation.sans_facture && (
                        <span className="nf-revue__proposition">
                          {texteSansFacture(possible.operation.sans_facture)}
                          {possible.operation.sans_facture.avis ? ' Au « Rattacher », l’avis devient sa page Virement' : ' Au « Rattacher », la justification s’efface'}.
                        </span>
                      )}
                    </>
                  ) : (
                    <span className="badge">aucune ligne trouvée</span>
                  )}
                </dd>
                <dt>Deviendrait</dt>
                <dd>
                  {n.operation
                    ? 'Payé'
                    : possible
                      ? 'Payé, si c’est bien cette ligne'
                      : 'À payer, et passera par Virements ; ou « Déjà payée » : enregistrée, son paiement se retrouvera dans Rapprocher'}
                </dd>
                {faite && (
                  <>
                    <dt>Décision</dt>
                    <dd className={`nf-revue__decision nf-revue__decision--${faite.genre}`}>{faite.texte}</dd>
                  </>
                )}
              </dl>
              {!faite && (
                <div className="nf-revue__actions">
                  <button type="button" className="btn btn--primary" disabled={enCours !== null} onClick={() => valider(n)}>
                    {n.operation ? 'Valider : Payé' : possible ? 'Rattacher à la transaction bancaire' : 'Valider : À payer'}
                  </button>
                  {!n.operation && !possible && (
                    <button type="button" className="btn btn--secondary" disabled={enCours !== null} onClick={() => dejaPayee(n)}>
                      Déjà payée
                    </button>
                  )}
                  <button type="button" className="btn btn--secondary" disabled={enCours !== null} onClick={() => onOuvrir(n, () => relire(n))}>
                    Autre…
                  </button>
                  <button
                    type="button"
                    className="btn btn--secondary"
                    disabled={enCours !== null}
                    onClick={() => agir(n, () => api.plusTard(n.id), 'tard', 'Plus tard · gardée dans À trancher avec la question de l’appli')}
                  >
                    Plus tard
                  </button>
                </div>
              )}
              {erreurs[n.id] && <p className="login-screen__erreur">{erreurs[n.id]}</p>}
            </article>
          )
        })}
      </div>
      {batchId && (
        <button
          type="button"
          className="btn btn--link"
          disabled={enCours !== null}
          onClick={async () => {
            setEnCours('toutes')
            try {
              await api.annulerImport(batchId)
              onChange()
              onFermer()
            } finally {
              setEnCours(null)
            }
          }}
        >
          Annuler cet import : défaire ce qui est encore à valider
        </button>
      )}
    </section>
  )
}

// La ligne que l'appli propose sans l'avoir rattachée : même montant autre
// nom (« Vu sur le compte »), ou la première des lignes au même nom (écart).
function proposee(n) {
  if (n.paiement_propose) return { operation: n.paiement_propose, ecart_centimes: 0, aussi: [], meme_montant: true }
  return n.paiements_possibles?.[0] ?? null
}

function sure(n) {
  return Boolean(n.operation) && (n.nature === 'achat' || n.personne)
}

function ecart(centimes) {
  return `${centimes > 0 ? '+' : ''}${api.euros(centimes)}`
}

function decision(n) {
  if (n.statut === 'refusee') return 'Refusée · dans A TRAITER'
  if (n.plus_tard) return 'Plus tard · gardée dans À trancher'
  if (n.statut === 'remboursee') return `Validée : Payé${n.rangement ? ` · rangée dans ${n.rangement}` : ''}`
  if (n.a_rapprocher) return `Validée : déjà payée, à rapprocher${n.rangement ? ` · rangée dans ${n.rangement}` : ''}`
  return `Validée : À payer${n.rangement ? ` · rangée dans ${n.rangement}` : ''}`
}
