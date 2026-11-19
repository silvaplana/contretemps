import { useEffect, useRef, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { BadgeEtat, naturesProposees, Pieces as Vignettes } from './commun.jsx'
import { ChoixTransactionModal } from './Rapprocher.jsx'

// Fiche d'une vente (financier.md §8.12, maquette validée par Seb le 19/11) :
// de qui ou quoi, date, une ou plusieurs lignes (compte de produits et
// montant), la pièce facultative. `note` null = saisie à la main. Rangée dans
// Docs › Financier › VENTES › le nom du compte de la première ligne.
// Encaissement (étape 2) : le crédit proposé, « Rattacher à cette transaction
// bancaire », « Autre transaction… », « Pas encore encaissée », « Encaissée en espèces ».
export default function VenteModal({ note, onClose, onFait }) {
  const modifiable = note === null || ['envoyee', 'validee'].includes(note.statut)
  const aValider = note === null || note.statut === 'envoyee'
  const [qui, setQui] = useState(note?.fournisseur ?? '')
  const [jour, setJour] = useState(note?.depenses[0]?.date ?? api.aujourdhui())
  const [lignes, setLignes] = useState(() =>
    note?.depenses.length
      ? note.depenses.map((d) => ({ categorieId: d.categorie?.id ?? '', montant: api.versTexteMontant(d.montant_centimes || null) }))
      : [{ categorieId: '', montant: '' }],
  )
  const [comptes, setComptes] = useState([])
  const [joint, setJoint] = useState(null)
  const camera = useRef(null)
  const galerie = useRef(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [credits, setCredits] = useState(null) // « Autre transaction… » : les crédits sans vente

  useEffect(() => {
    api
      .categories({ ventes: true })
      .then(setComptes)
      .catch((err) => setErreur(err.message))
  }, [])

  const total = lignes.reduce((somme, l) => somme + (api.versCentimes(l.montant) || 0), 0)

  function changerLigne(rang, champ, valeur) {
    setLignes(lignes.map((l, i) => (i === rang ? { ...l, [champ]: valeur } : l)))
  }

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

  function lignesSaisies() {
    return lignes.map((l) => {
      const centimes = api.versCentimes(l.montant)
      if (!centimes) throw new Error('Indiquez le montant de chaque ligne, par exemple 480,00.')
      return { categorie_id: l.categorieId ? Number(l.categorieId) : null, montant_centimes: centimes }
    })
  }

  async function enregistrer() {
    const saisies = lignesSaisies()
    if (note === null) {
      await api.etablir('vente', joint, { fournisseur: qui.trim(), date: jour, lignes: JSON.stringify(saisies), valider: true })
      return
    }
    if (joint) await api.ajouterPage(note.id, joint)
    await api.corriger(note.id, { fournisseur: qui.trim(), date: jour, lignes: saisies })
    if (aValider) await api.valider(note.id)
  }

  const footer = modifiable ? (
    <div className="nf-boutons">
      {note !== null && aValider && !note.plus_tard && (
        <button type="button" className="btn btn--secondary" disabled={enCours} onClick={() => agir(() => api.plusTard(note.id))}>
          Plus tard
        </button>
      )}
      <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => agir(enregistrer)}>
        {aValider ? 'Valider : À encaisser' : 'Enregistrer'}
      </button>
    </div>
  ) : null

  return (
    <Modal title={note ? 'Vente' : 'Nouvelle vente'} onClose={onClose} footer={footer}>
      {note && (
        <div className="nf-entete-note">
          <span>{note.fournisseur || 'De qui ?'}</span>
          <BadgeEtat note={note} />
        </div>
      )}
      {note && note.statut === 'envoyee' && (
        // Une pièce lue comme une recette peut être une dépense : la nature se change ici.
        <div className="filter-chips nf-natures" role="group" aria-label="Nature de la pièce">
          {naturesProposees(false).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={value === 'vente' ? 'filter-chip filter-chip-active' : 'filter-chip'}
              aria-pressed={value === 'vente'}
              disabled={enCours}
              onClick={() => value !== 'vente' && agir(() => api.corriger(note.id, { nature: value }))}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {note?.numero_piece && <p className="muted">Pièce n° {note.numero_piece}</p>}
      {note?.depenses[0]?.lue_par_ia && modifiable && (
        <p className="badge badge--warning nf-a-verifier">Rempli d’après la pièce, à vérifier</p>
      )}
      {note && <Vignettes pieces={note.depenses.flatMap((d) => d.pieces)} />}
      <label htmlFor="nf-vente-qui">De qui ou quoi</label>
      <input
        id="nf-vente-qui"
        value={qui}
        onChange={(e) => setQui(e.target.value)}
        maxLength={120}
        placeholder="Gala, mairie, famille Martin…"
        disabled={!modifiable}
      />
      <label htmlFor="nf-vente-date">Date</label>
      <input id="nf-vente-date" type="date" value={jour} max={api.aujourdhui()} onChange={(e) => setJour(e.target.value)} disabled={!modifiable} />
      <span className="nf-label">Compte et montant</span>
      {lignes.map((l, rang) => (
        <div key={rang} className="nf-vente-ligne">
          <select
            aria-label={`Compte de la ligne ${rang + 1}`}
            value={l.categorieId}
            onChange={(e) => changerLigne(rang, 'categorieId', e.target.value)}
            disabled={!modifiable}
          >
            <option value="">—</option>
            {comptes.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code ? `${c.code} ${c.libelle}` : c.libelle}
              </option>
            ))}
          </select>
          <input
            aria-label={`Montant de la ligne ${rang + 1}`}
            inputMode="decimal"
            value={l.montant}
            onChange={(e) => changerLigne(rang, 'montant', e.target.value)}
            placeholder="0,00"
            disabled={!modifiable}
          />
          {lignes.length > 1 && modifiable && rang > 0 ? (
            <button
              type="button"
              className="btn btn--secondary"
              aria-label={`Retirer la ligne ${rang + 1}`}
              onClick={() => setLignes(lignes.filter((_, i) => i !== rang))}
            >
              <Icon name="x" size={18} />
            </button>
          ) : (
            <span />
          )}
        </div>
      ))}
      {modifiable && (
        <button type="button" className="btn btn--link" onClick={() => setLignes([...lignes, { categorieId: '', montant: '' }])}>
          Ajouter une ligne
        </button>
      )}
      {lignes.length > 1 && (
        <p className="nf-total">
          Total : <strong>{api.euros(total)}</strong>
        </p>
      )}
      {modifiable && (
        <>
          <span className="nf-label">Pièce</span>
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
        <Encaissement
          note={note}
          enCours={enCours}
          onRattacher={(op) => agir(() => api.payee(note.id, op.id))}
          onAutre={() => {
            const depuis = new Date(new Date(jour).getTime() - 60 * 86400000).toISOString().slice(0, 10)
            api
              .rapprochement(depuis, '')
              .then((d) => setCredits(d.credits_sans_vente))
              .catch((err) => setErreur(err.message))
          }}
          onPasEncore={() => (aValider ? agir(enregistrer) : onClose())}
          onEspeces={() => agir(() => api.especes(note.id))}
          onDetacher={() => agir(() => api.detacher(note.id))}
        />
      )}
      {credits && (
        <ChoixTransactionModal
          piece={{ qui: qui || 'Vente', nature: 'Vente', nature_code: 'vente', date: jour, montant_centimes: total }}
          transactions={credits}
          onClose={() => setCredits(null)}
          onChoisie={(t) => {
            setCredits(null)
            agir(() => api.payee(note.id, t.id, [], true))
          }}
        />
      )}
      {note?.rangement && <p className="muted nf-rangement">Rangée dans Docs › {note.rangement}</p>}
      {note && refusable(note) && (
        <button type="button" className="btn btn--link nf-supprimer" disabled={enCours} onClick={() => agir(() => api.supprimerNote(note.id))}>
          Annuler cette pièce : tout défaire
        </button>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Le bloc Encaissement de la maquette (financier.md §8.12) : rien n'est rattaché sans un toucher ;
// un écart avec la banque est signalé, jamais corrigé.
function Encaissement({ note, enCours, onRattacher, onAutre, onPasEncore, onEspeces, onDetacher }) {
  const ecart = (op) => op.montant_centimes - note.total_centimes
  const texteEcart = (centimes) =>
    centimes ? <p className="badge badge--warning">Écart de {api.euros(Math.abs(centimes))} avec la pièce : à vérifier</p> : null
  if (note.statut === 'remboursee') {
    return (
      <>
        <span className="nf-label">Encaissement</span>
        {note.operation ? (
          <p className="nf-ligne nf-paiement-vu">
            <span className="nf-ligne__corps">
              <span className="nf-ligne__titre">{note.operation.libelle}</span>
              <span className="muted">
                {api.dateCourte(note.operation.date)}
                {note.operation.compte ? ` · ${note.operation.compte}` : ''} · +{api.euros(note.operation.montant_centimes)}
              </span>
            </span>
          </p>
        ) : (
          <p>Encaissée en espèces (caisse).</p>
        )}
        {texteEcart(note.ecart_centimes)}
        <EcrituresVente note={note} />
        {(note.detachable || note.especes) && (
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
      <span className="nf-label">Encaissement</span>
      {op ? (
        <div className="nf-ligne nf-paiement-vu nf-encaissement">
          <span className="nf-ligne__corps">
            <span className="muted">Transaction bancaire proposée{note.paiement_propose ? ' (même montant, date proche)' : ''}</span>
            <span className="nf-ligne__titre">{op.libelle}</span>
            <span className="muted">
              {api.dateCourte(op.date)}
              {op.compte ? ` · ${op.compte}` : ''} · +{api.euros(op.montant_centimes)}
            </span>
            {texteEcart(ecart(op))}
          </span>
          <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => onRattacher(op)}>
            Rattacher à cette transaction bancaire
          </button>
        </div>
      ) : (
        <p className="muted">Aucun crédit de {api.euros(note.total_centimes)} trouvé sur les comptes pour l’instant.</p>
      )}
      <button type="button" className="btn btn--link" disabled={enCours} onClick={onAutre}>
        Autre transaction…
      </button>
      <button type="button" className="btn btn--link" disabled={enCours} onClick={onPasEncore}>
        Pas encore encaissée
      </button>
      <button type="button" className="btn btn--link" disabled={enCours} onClick={onEspeces}>
        Encaissée en espèces
      </button>
    </>
  )
}

// 512 (ou 530 Caisse) au débit, chaque ligne de la vente au crédit, journal VE.
function EcrituresVente({ note }) {
  const tresorerie = note.operation ? `${note.operation.compte_plan || '512'} ${note.operation.compte || 'Banque'}` : '530 Caisse'
  return (
    <div className="nf-revue__ecritures">
      <table>
        <thead>
          <tr>
            <th>Écritures (journal VE)</th>
            <th>Débit</th>
            <th>Crédit</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>{tresorerie}</td>
            <td>{api.euros(note.total_centimes)}</td>
            <td />
          </tr>
          {note.depenses.map((d) => (
            <tr key={d.id}>
              <td>{d.categorie ? `${d.categorie.code ? `${d.categorie.code} ` : ''}${d.categorie.libelle}` : 'Compte à choisir'}</td>
              <td />
              <td>{api.euros(d.montant_centimes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function refusable(note) {
  return !(note.statut === 'remboursee' && note.operation_id)
}
