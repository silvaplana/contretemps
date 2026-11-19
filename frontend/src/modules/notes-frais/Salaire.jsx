import { useRef, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { BadgeEtat, Pieces as Vignettes } from './commun.jsx'
import { ChoixTransactionModal } from './Rapprocher.jsx'

// Fiche d'un bulletin de salaire (financier.md §8.11) : le salarié, la date,
// le salaire brut et les cotisations lus sur le bulletin. L'appli en tire
// les écritures comme EBP : 641 le brut, 645 la part de l'employeur, 431 les
// cotisations dues à l'URSSAF ; le net payé est rattaché au virement, et le
// prélèvement de l'URSSAF solde 431. `note` null = saisie à la main.
export default function SalaireModal({ note, onClose, onFait }) {
  const modifiable = note === null || ['envoyee', 'validee'].includes(note.statut)
  const aValider = note === null || note.statut === 'envoyee'
  const montantDe = (code) => note?.depenses.find((d) => d.categorie?.code === code)?.montant_centimes ?? null
  const cotisations = montantDe('431') == null ? null : -montantDe('431')
  const [qui, setQui] = useState(note?.fournisseur ?? '')
  const [jour, setJour] = useState(note?.depenses[0]?.date ?? api.aujourdhui())
  const [brut, setBrut] = useState(api.versTexteMontant(note?.depenses[0]?.montant_centimes ?? null))
  const [employeur, setEmployeur] = useState(api.versTexteMontant(montantDe('645')))
  const [salarie, setSalarie] = useState(
    api.versTexteMontant(cotisations == null ? null : cotisations - (montantDe('645') ?? 0)),
  )
  const [joint, setJoint] = useState(null)
  const camera = useRef(null)
  const galerie = useRef(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [debits, setDebits] = useState(null) // « Autre transaction… »

  const c = { brut: api.versCentimes(brut) || 0, salarie: api.versCentimes(salarie) || 0, employeur: api.versCentimes(employeur) || 0 }
  const net = c.brut - c.salarie
  const cout = c.brut + c.employeur

  async function agir(action) {
    setErreur('')
    setEnCours(true)
    try {
      await action()
      onFait()
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  function paieSaisie() {
    if (!c.brut) throw new Error('Indiquez le salaire brut, par exemple 1800,00.')
    return c
  }

  async function enregistrer() {
    const paie = paieSaisie()
    if (note === null) {
      await api.etablir('salaire', joint, { fournisseur: qui.trim(), date: jour, paie: JSON.stringify(paie), valider: true })
      return
    }
    if (joint) await api.ajouterPage(note.id, joint)
    await api.corriger(note.id, { fournisseur: qui.trim(), date: jour, paie })
    if (aValider) await api.valider(note.id)
  }

  const footer = modifiable ? (
    <div className="nf-boutons">
      <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => agir(enregistrer)}>
        {aValider ? 'Valider : À payer' : 'Enregistrer'}
      </button>
    </div>
  ) : null

  const champ = (id, label, valeur, changer) => (
    <>
      <label htmlFor={id}>{label}</label>
      <input id={id} inputMode="decimal" value={valeur} onChange={(e) => changer(e.target.value)} placeholder="0,00" disabled={!modifiable} />
    </>
  )

  return (
    <Modal title={note ? 'Bulletin de salaire' : 'Nouveau bulletin de salaire'} onClose={onClose} footer={footer}>
      {note && (
        <div className="nf-entete-note">
          <span>{note.fournisseur || 'Salarié ?'}</span>
          <BadgeEtat note={note} />
        </div>
      )}
      {note?.numero_piece && <p className="muted">Pièce n° {note.numero_piece}</p>}
      {note && <Vignettes pieces={note.depenses.flatMap((d) => d.pieces)} />}
      <label htmlFor="nf-salaire-qui">Salarié</label>
      <input id="nf-salaire-qui" value={qui} onChange={(e) => setQui(e.target.value)} maxLength={120} placeholder="Nom du salarié" disabled={!modifiable} />
      <label htmlFor="nf-salaire-date">Date du bulletin</label>
      <input id="nf-salaire-date" type="date" value={jour} max={api.aujourdhui()} onChange={(e) => setJour(e.target.value)} disabled={!modifiable} />
      {champ('nf-salaire-brut', 'Salaire brut', brut, setBrut)}
      {champ('nf-salaire-salarie', 'Cotisations du salarié', salarie, setSalarie)}
      {champ('nf-salaire-employeur', 'Cotisations de l’employeur', employeur, setEmployeur)}
      {c.brut > 0 && (
        <p className="nf-total">
          Net payé : <strong>{api.euros(net)}</strong> · Coût pour l’association : <strong>{api.euros(cout)}</strong>
        </p>
      )}
      {c.brut > 0 && <EcrituresPaie c={c} net={net} />}
      {modifiable && (
        <>
          <span className="nf-label">Bulletin</span>
          {joint ? (
            <p className="nf-joindre">
              <span className="nf-joindre__nom">{joint.name}</span>
              <button type="button" className="btn btn--secondary" onClick={() => setJoint(null)}>
                Retirer
              </button>
            </p>
          ) : (
            <div className="nf-joindre">
              <button type="button" className="btn btn--secondary" onClick={() => camera.current?.click()}>
                <Icon name="camera" size={18} /> Prendre une photo
              </button>
              <button type="button" className="btn btn--secondary" onClick={() => galerie.current?.click()}>
                <Icon name="image" size={18} /> Joindre un fichier
              </button>
            </div>
          )}
          {note === null && !joint && <p className="muted">Facultatif. Sans fichier, rien n’est créé dans Docs.</p>}
          <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={(e) => setJoint(e.target.files?.[0] ?? null)} />
          <input ref={galerie} type="file" accept="image/*,application/pdf" hidden onChange={(e) => setJoint(e.target.files?.[0] ?? null)} />
        </>
      )}
      {note && note.statut !== 'refusee' && (
        <Paiement
          note={note}
          enCours={enCours}
          onRattacher={(op) => agir(() => api.payee(note.id, op.id))}
          onAutre={() => {
            const depuis = new Date(new Date(jour).getTime() - 60 * 86400000).toISOString().slice(0, 10)
            api
              .rapprochement(depuis, '')
              .then((d) => setDebits(d.lignes_sans_piece))
              .catch((err) => setErreur(err.message))
          }}
          onDetacher={() => agir(() => api.detacher(note.id))}
        />
      )}
      {debits && (
        <ChoixTransactionModal
          piece={{ qui: qui || 'Salaire', nature: 'Bulletin de salaire', nature_code: 'salaire', date: jour, montant_centimes: net }}
          transactions={debits}
          onClose={() => setDebits(null)}
          onChoisie={(t) => {
            setDebits(null)
            agir(() => api.payee(note.id, t.id, [], true))
          }}
        />
      )}
      {note?.rangement && <p className="muted nf-rangement">Rangé dans Docs › {note.rangement}</p>}
      {note && !(note.statut === 'remboursee' && note.operation_id) && (
        <button type="button" className="btn btn--link nf-supprimer" disabled={enCours} onClick={() => agir(() => api.supprimerNote(note.id))}>
          Annuler cette pièce : tout défaire
        </button>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Le virement du net : proposé (même montant, date proche), jamais rattaché sans un toucher.
function Paiement({ note, enCours, onRattacher, onAutre, onDetacher }) {
  if (note.statut === 'remboursee') {
    return (
      <>
        <span className="nf-label">Paiement du net</span>
        {note.operation && (
          <p className="nf-ligne nf-paiement-vu">
            <span className="nf-ligne__corps">
              <span className="nf-ligne__titre">{note.operation.libelle}</span>
              <span className="muted">
                {api.dateCourte(note.operation.date)}
                {note.operation.compte ? ` · ${note.operation.compte}` : ''} · −{api.euros(-note.operation.montant_centimes)}
              </span>
            </span>
          </p>
        )}
        {note.detachable && (
          <button type="button" className="btn btn--link" disabled={enCours} onClick={onDetacher}>
            Détacher
          </button>
        )}
      </>
    )
  }
  const op = note.paiement_propose ?? note.paiements_possibles?.[0]?.operation
  return (
    <>
      <span className="nf-label">Paiement du net</span>
      {op ? (
        <div className="nf-ligne nf-paiement-vu nf-encaissement">
          <span className="nf-ligne__corps">
            <span className="muted">Transaction bancaire proposée</span>
            <span className="nf-ligne__titre">{op.libelle}</span>
            <span className="muted">
              {api.dateCourte(op.date)}
              {op.compte ? ` · ${op.compte}` : ''} · −{api.euros(Math.abs(op.montant_centimes))}
            </span>
          </span>
          <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => onRattacher(op)}>
            Rattacher à cette transaction bancaire
          </button>
        </div>
      ) : (
        <p className="muted">Aucun virement de {api.euros(note.total_centimes)} trouvé sur les comptes pour l’instant.</p>
      )}
      <button type="button" className="btn btn--link" disabled={enCours} onClick={onAutre}>
        Autre transaction…
      </button>
    </>
  )
}

// Les écritures du bulletin, comme EBP : 641 et 645 au débit, 431 au crédit (dû à l'URSSAF), la banque au crédit du net.
function EcrituresPaie({ c, net }) {
  const lignes = [
    ['641 Salaires', c.brut, 0],
    ['645 Charges sociales', c.employeur, 0],
    ['431 URSSAF à payer', 0, c.salarie + c.employeur],
    ['512 Banque', 0, net],
  ].filter(([, d, cr]) => d || cr)
  return (
    <div className="nf-revue__ecritures">
      <table>
        <thead>
          <tr>
            <th>Écritures</th>
            <th>Débit</th>
            <th>Crédit</th>
          </tr>
        </thead>
        <tbody>
          {lignes.map(([compte, debit, credit]) => (
            <tr key={compte}>
              <td>{compte}</td>
              <td>{debit ? api.euros(debit) : ''}</td>
              <td>{credit ? api.euros(credit) : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted">Le prélèvement de l’URSSAF, classé dans 431, solde ce qui lui est dû.</p>
    </div>
  )
}
