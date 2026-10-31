import { Fragment, useCallback, useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import * as sessionApi from '../../api/session.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import LignesBanque from '../finances/compta/LignesBanque.jsx'
import PlanComptable from '../finances/compta/PlanComptable.jsx'
import { telechargerFichier } from '../../utils/telechargement.js'
import { BadgeEtat, ChampsRib, Compte, NATURES, PaiementVu, Pieces as Vignettes, PreuveVirement, qui, raisonProposee, ribVide } from './commun.jsx'
import { DetailDepenses } from './MesNotesDeFrais.jsx'
import { masquerIban } from './EnvoiModal.jsx'
import Virements from './Virements.jsx'
import Saisie from './Saisie.jsx'

// Financier › Pièces (spec/modules/financier.md §8.3 et §8.3 bis) : notes de
// frais, honoraires et achats sont une seule structure « dépense », avec une
// nature ; chaque puce en est un filtre. À rattacher et Ventes sont des
// lignes de banque (compte du plan à confirmer, financier.md §8.3 et §8.4).
// Un seul bouton principal, « + ».
const PUCES = [
  { value: 'virements', label: 'Virements' },
  { value: 'frais', label: 'Notes de frais' },
  { value: 'honoraires', label: 'Honoraires' },
  { value: 'achat', label: 'Achats' },
  { value: 'a_rattacher', label: 'À rattacher', banque: true },
  { value: 'ventes', label: 'Ventes', banque: true },
]

const SUR_ORDINATEUR = typeof window !== 'undefined' && window.matchMedia?.('(pointer: fine)').matches

export default function Pieces({ aFaire, onCompteurs, onChange, onPour }) {
  const [puce, setPuce] = useState(() => {
    const derniere = sessionApi.lireEcran('financier-pieces')
    return PUCES.some((p) => p.value === derniere) ? derniere : 'virements'
  })
  useEffect(() => {
    sessionApi.sauvegarderEcran('financier-pieces', puce)
  }, [puce])
  // « + » = Saisir une dépense (Saisie.jsx) ; « Saisir sans photo » demande
  // d'abord la nature, puis ouvre la saisie de cette puce (`plus`).
  const [saisie, setSaisie] = useState(false)
  const [deposes, setDeposes] = useState(null)
  const [natureAChoisir, setNatureAChoisir] = useState(false)
  const [plus, setPlus] = useState(false)
  const [revue, setRevue] = useState(null) // { notes, rang }
  const [version, setVersion] = useState(0) // relire la puce après une saisie
  const [survol, setSurvol] = useState(false)

  const banque = PUCES.find((p) => p.value === puce)?.banque
  const glisser = SUR_ORDINATEUR

  function finDeRevue() {
    setRevue(null)
    setVersion((v) => v + 1)
    onChange()
  }

  return (
    <section
      aria-label="Pièces"
      className={survol ? 'nf-pieces nf-depot nf-depot--survol' : 'nf-pieces nf-depot'}
      onDragOver={
        glisser
          ? (e) => {
              e.preventDefault()
              setSurvol(true)
            }
          : undefined
      }
      onDragLeave={glisser ? () => setSurvol(false) : undefined}
      onDrop={
        glisser
          ? (e) => {
              e.preventDefault()
              setSurvol(false)
              setDeposes([...e.dataTransfer.files])
            }
          : undefined
      }
    >
      <div className="filter-chips" role="group" aria-label="Pièces">
        {PUCES.map((p) => (
          <button
            key={p.value}
            type="button"
            className={p.value === puce ? 'filter-chip filter-chip-active' : 'filter-chip'}
            aria-pressed={p.value === puce}
            onClick={() => setPuce(p.value)}
          >
            {p.label}
            <Compte n={aFaire[p.value]} banque={p.value === 'virements' || p.value === 'a_rattacher'} />
          </button>
        ))}
      </div>
      {glisser && !banque && puce !== 'virements' && (
        <p className="muted">Glissez ici des factures depuis l’ordinateur : une par fichier.</p>
      )}
      {banque ? (
        <LignesBanque key={puce} filtre={puce} onChange={onChange} />
      ) : puce === 'virements' ? (
        <Virements key={version} onChange={onChange} />
      ) : (
        <ListeNature
          key={`${puce}-${version}`}
          nature={puce}
          onCompteurs={onCompteurs}
          plus={plus}
          onPlusFerme={() => setPlus(false)}
          onPour={onPour}
        />
      )}
      <div className="nf-barre">
        <span className="nf-barre__vide" />
        <button type="button" className="nf-barre__plus" aria-label="Saisir une dépense" onClick={() => setSaisie(true)}>
          <Icon name="plus" size={26} />
        </button>
      </div>
      <Saisie
        ouverte={saisie}
        deposes={deposes}
        onFermer={() => setSaisie(false)}
        onALaMain={() => {
          setSaisie(false)
          setNatureAChoisir(true)
        }}
        onRevue={(notes) => {
          setSaisie(false)
          setRevue({ notes, rang: 0 })
        }}
        onChange={onChange}
      />
      {revue && (
        <NoteModal
          key={revue.notes[revue.rang].id}
          note={revue.notes[revue.rang]}
          nature={revue.notes[revue.rang].nature}
          revue={{ rang: revue.rang + 1, total: revue.notes.length }}
          onClose={finDeRevue}
          onFait={() => (revue.rang + 1 < revue.notes.length ? setRevue({ ...revue, rang: revue.rang + 1 }) : finDeRevue())}
        />
      )}
      {natureAChoisir && (
        <Modal title="Quelle pièce ?" onClose={() => setNatureAChoisir(false)}>
          <div className="nf-choix">
            {Object.entries(NATURES).map(([value, label]) => (
              <button
                key={value}
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  setNatureAChoisir(false)
                  setPuce(value)
                  setPlus(true)
                }}
              >
                {label}
              </button>
            ))}
          </div>
        </Modal>
      )}
    </section>
  )
}

// Une puce Notes de frais, Honoraires ou Achats : à valider en tête, puis le
// reste. Les photos et fichiers passent par « + » (Saisie.jsx) ; ici,
// `plus` = saisir sans photo dans cette nature.
function ListeNature({ nature, onCompteurs, plus, onPlusFerme, onPour }) {
  const [notes, setNotes] = useState(null)
  const [ouverte, setOuverte] = useState(null) // note | 'nouvelle'
  const [periode, setPeriode] = useState({ debut: '', fin: '' })
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api
      .tresorerie(nature)
      .then((d) => {
        setNotes(d.notes)
        onCompteurs(d.compteurs)
        setErreur('')
      })
      .catch((err) => setErreur(err.message))
  }, [nature, onCompteurs])
  useEffect(charger, [charger])

  // « Saisir sans photo » dans cette nature : la fiche vide.
  const modale = ouverte ?? (plus && nature !== 'frais' ? 'nouvelle' : null)

  let visibles = notes ?? []
  if (periode.debut || periode.fin) {
    visibles = visibles.filter((n) => {
      const jour = n.depenses[0]?.date ?? n.envoyee_le.slice(0, 10)
      return (!periode.debut || jour >= periode.debut) && (!periode.fin || jour <= periode.fin)
    })
  }

  return (
    <div className="nf-depot">
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!notes && !erreur && <p className="muted">Chargement…</p>}
      {notes && visibles.length === 0 && <p className="muted">Rien pour l’instant.</p>}

      <div className="nf-liste">
        {visibles.map((n) => (
          <button key={n.id} type="button" className="nf-ligne" onClick={() => setOuverte(n)}>
            <span className="nf-ligne__corps">
              <span className="nf-ligne__titre">{qui(n)}</span>
              <span className="muted">
                {n.nature === 'achat' ? '' : `${n.titre} · `}
                {api.dateCourte(n.depenses[0]?.date ?? n.envoyee_le)}
                {n.depenses.length > 1 ? ` · ${n.depenses.length} dépenses` : ''}
                {n.paiement_propose ? ' · vu sur le compte' : ''}
              </span>
            </span>
            <span className="nf-ligne__droite">
              <span className="nf-ligne__montant">{n.total_centimes ? api.euros(n.total_centimes) : 'Montant ?'}</span>
              <BadgeEtat note={n} />
            </span>
          </button>
        ))}
      </div>

      <div className="nf-periode">
        <label>
          Du
          <input
            type="date"
            className="field-input"
            value={periode.debut}
            onChange={(e) => setPeriode({ ...periode, debut: e.target.value })}
          />
        </label>
        <label>
          au
          <input
            type="date"
            className="field-input"
            value={periode.fin}
            onChange={(e) => setPeriode({ ...periode, fin: e.target.value })}
          />
        </label>
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() =>
            telechargerFichier(api.urlExport(periode.debut, periode.fin, nature), `${nature}.xlsx`).catch((err) =>
              setErreur(err.message),
            )
          }
        >
          <Icon name="download" size={18} /> Excel
        </button>
      </div>

      {plus && nature === 'frais' && (
        <ChoixPersonneModal
          onClose={onPlusFerme}
          onChoisie={(personne) => {
            onPlusFerme()
            onPour(personne, 'depense')
          }}
        />
      )}

      {modale && (
        <NoteModal
          note={modale === 'nouvelle' ? null : modale}
          nature={nature}
          onClose={() => {
            setOuverte(null)
            onPlusFerme()
          }}
          onFait={() => {
            setOuverte(null)
            onPlusFerme()
            charger()
          }}
        />
      )}
    </div>
  )
}

// Détail d'une pièce. Note de frais envoyée par la personne : Valider /
// Refuser (elle corrige elle-même). Pièce établie depuis « + » (photo lue,
// nature proposée) : nature, personne et montant à vérifier ou corriger, puis
// Valider ; `note` null = saisie sans photo ; `revue` = rang dans le lot.
function NoteModal({ note, nature, onClose, onFait, revue }) {
  const corrigeable =
    note === null || ((note.nature !== 'frais' || note.etablie) && ['envoyee', 'validee'].includes(note.statut))
  const natureModifiable = note !== null && corrigeable && note.statut === 'envoyee'
  const depense = note?.depenses[0]
  const [pour, setPour] = useState(note?.personne ?? null)
  const [choixPour, setChoixPour] = useState(false)
  const [fournisseur, setFournisseur] = useState(note?.fournisseur ?? '')
  const [jour, setJour] = useState(depense?.date ?? api.aujourdhui())
  const [montant, setMontant] = useState(api.versTexteMontant(depense?.montant_centimes || null))
  const [description, setDescription] = useState(depense?.description ?? '')
  const [categorieId, setCategorieId] = useState(depense?.categorie?.id ?? '')
  const [categories, setCategories] = useState([])
  const [plan, setPlan] = useState(false)
  const [refus, setRefus] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [genre, setGenre] = useState(note?.nature ?? nature)

  // Catégories = comptes de charges du plan comptable (financier.md §8.3
  // ter) ; le crayon ouvre le plan, la liste est relue en le fermant.
  const chargerCategories = useCallback(() => {
    api
      .categories()
      .then(setCategories)
      .catch((err) => setErreur(err.message))
  }, [])

  useEffect(() => {
    if (corrigeable) chargerCategories()
  }, [corrigeable, chargerCategories])

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

  function champs() {
    const centimes = api.versCentimes(montant)
    if (!centimes) throw new Error('Indiquez le montant, par exemple 480,00.')
    if (genre !== 'achat' && !pour) throw new Error('Choisissez pour qui est cette pièce.')
    return {
      ...(note && genre !== note.nature ? { nature: genre } : {}),
      date: jour,
      montant_centimes: centimes,
      description: description.trim(),
      ...(categorieId ? { categorie_id: Number(categorieId) } : {}),
      ...(genre !== 'achat' ? { person_id: pour.person_id } : { fournisseur: fournisseur.trim() }),
    }
  }

  async function enregistrer(valider) {
    const corps = champs()
    if (note === null) {
      await api.etablir(genre, null, { ...corps, valider: true })
      return
    }
    await api.corriger(note.id, corps)
    if (valider) await api.valider(note.id)
  }

  // Le plan comptable prend la place de la fiche le temps de le modifier
  // (la saisie en cours est gardée).
  if (plan) {
    const fermer = () => {
      setPlan(false)
      chargerCategories()
    }
    return (
      <Modal title="Plan comptable" onClose={fermer}>
        <PlanComptable onClose={fermer} />
      </Modal>
    )
  }

  const aValider = note === null || note.statut === 'envoyee'
  const footer =
    note !== null && !corrigeable && note.statut !== 'envoyee' ? null : refus !== null ? (
      <div className="nf-boutons">
        <button type="button" className="btn btn--secondary" onClick={() => setRefus(null)}>
          Annuler
        </button>
        <button
          type="button"
          className="btn btn--danger"
          disabled={enCours || !refus.trim()}
          onClick={() => agir(() => api.refuser(note.id, refus.trim()))}
        >
          Refuser
        </button>
      </div>
    ) : (
      <div className="nf-boutons">
        {note !== null && aValider && (
          <button type="button" className="btn btn--danger" disabled={enCours} onClick={() => setRefus('')}>
            Refuser…
          </button>
        )}
        <button
          type="button"
          className="btn btn--primary"
          disabled={enCours}
          onClick={() =>
            agir(() => (corrigeable ? enregistrer(aValider) : api.valider(note.id)))
          }
        >
          {aValider ? (note?.operation ? 'Valider : Payé' : 'Valider : À payer') : 'Enregistrer'}
        </button>
      </div>
    )

  return (
    <Modal
      title={
        revue
          ? `Pièce ${revue.rang} sur ${revue.total}`
          : note
            ? note.nature === 'achat'
              ? 'Achat'
              : note.titre
            : genre === 'achat'
              ? 'Nouvel achat'
              : genre === 'frais'
                ? 'Nouvelle note de frais'
                : 'Nouveaux honoraires'
      }
      onClose={onClose}
      footer={footer}
    >
      {note && (
        <div className="nf-entete-note">
          <span>
            {qui(note)}
            {note.nature !== 'achat' && note.personne?.role ? <span className="muted"> ({note.personne.role})</span> : null}
          </span>
          <BadgeEtat note={note} />
        </div>
      )}
      {natureModifiable && (
        <div className="filter-chips nf-natures" role="group" aria-label="Nature de la pièce">
          {Object.entries(NATURES).map(([value, label]) => (
            <button
              key={value}
              type="button"
              className={value === genre ? 'filter-chip filter-chip-active' : 'filter-chip'}
              aria-pressed={value === genre}
              onClick={() => setGenre(value)}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      {natureModifiable && genre === note.nature && raisonProposee(note) && (
        <p className="muted nf-raison">Proposé d’après la pièce : {raisonProposee(note)}</p>
      )}
      {note && <PaiementVu note={note} onConfirme={(op) => agir(() => api.payee(note.id, op.id))} />}
      {note && (
        <PreuveVirement
          note={note}
          onPaye={() =>
            agir(async () => {
              if (note.paiement_propose) return api.payee(note.id, note.paiement_propose.id)
              // La banque n'a pas encore la ligne : Envoyé, elle la verra.
              if (note.statut === 'envoyee') await enregistrer(true)
              await api.virementFait(note.id)
            })
          }
        />
      )}
      {note && depense?.lue_par_ia && corrigeable && (
        <p className="badge badge--warning nf-a-verifier">Rempli d’après le ticket, à vérifier</p>
      )}
      {corrigeable ? (
        <>
          {note && <Vignettes pieces={note.depenses.flatMap((d) => d.pieces)} />}
          {genre !== 'achat' ? (
            <>
              <label htmlFor="nf-pour">Pour qui ?</label>
              <button id="nf-pour" type="button" className="btn btn--secondary nf-pour" onClick={() => setChoixPour(true)}>
                <Icon name="search" size={18} />
                {pour ? pour.nom : note?.fournisseur ? `${note.fournisseur} ?` : 'Choisir'}
              </button>
              {choixPour && (
                <ChoixPersonneModal
                  initial={!pour && note?.fournisseur ? note.fournisseur : ''}
                  onClose={() => setChoixPour(false)}
                  onChoisie={(p) => {
                    setPour(p)
                    setChoixPour(false)
                  }}
                />
              )}
            </>
          ) : (
            <>
              <label htmlFor="nf-fournisseur">Fournisseur</label>
              <input id="nf-fournisseur" value={fournisseur} onChange={(e) => setFournisseur(e.target.value)} maxLength={120} />
            </>
          )}
          <label htmlFor="nf-date">Date</label>
          <input id="nf-date" type="date" value={jour} max={api.aujourdhui()} onChange={(e) => setJour(e.target.value)} />
          <label htmlFor="nf-montant">Montant (€)</label>
          <input id="nf-montant" inputMode="decimal" value={montant} onChange={(e) => setMontant(e.target.value)} placeholder="0,00" />
          <div className="nf-label-crayon">
            <label htmlFor="nf-categorie">Catégorie</label>
            <button type="button" className="btn btn--secondary" aria-label="Modifier les catégories" title="Modifier les catégories" onClick={() => setPlan(true)}>
              <Icon name="edit" size={18} />
            </button>
          </div>
          <select id="nf-categorie" value={categorieId} onChange={(e) => setCategorieId(e.target.value)}>
            <option value="">—</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.code ? `${c.code} ${c.libelle}` : c.libelle}
              </option>
            ))}
          </select>
          <label htmlFor="nf-description">Description</label>
          <input id="nf-description" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={200} />
        </>
      ) : (
        <>
          <p className="muted">
            Envoyée le {api.dateCourte(note.envoyee_le)}
            {note.traitee_par ? ` · traitée par ${note.traitee_par}` : ''}
          </p>
          <DetailDepenses depenses={note.depenses} />
          <p className="nf-total">
            Total : <strong>{api.euros(note.total_centimes)}</strong>
          </p>
        </>
      )}
      {note?.don ? (
        <p className="badge badge--success">Don à l’association : pas de remboursement</p>
      ) : note?.rib ? (
        <p className="nf-iban">
          RIB : {note.rib.titulaire ? `${note.rib.titulaire} · ` : ''}
          {note.statut === 'envoyee' ? masquerIban(note.rib.iban) : note.rib.iban}
          {note.rib.bic ? ` · ${note.rib.bic}` : ''}
        </p>
      ) : null}
      {note?.motif_refus && <p className="login-screen__erreur">Motif du refus : {note.motif_refus}</p>}
      {note && note.depenses.some((d) => d.pieces.length) && (
        <button
          type="button"
          className="btn btn--secondary"
          onClick={() =>
            telechargerFichier(api.urlJustificatifs(note.id), 'justificatifs.zip').catch((err) => setErreur(err.message))
          }
        >
          <Icon name="download" size={18} /> Télécharger les justificatifs
        </button>
      )}
      {note?.operation && (
        <div className="nf-ligne nf-paiement-vu">
          <span className="nf-ligne__corps">
            <span className="nf-ligne__titre">{note.statut === 'envoyee' ? 'Payée selon la banque' : 'Payée'}</span>
            <span className="muted">
              {note.operation.libelle} · {api.euros(note.operation.montant_centimes)} le {api.dateCourte(note.operation.date)}
            </span>
          </span>
          {note.detachable && (
            <button type="button" className="btn btn--secondary" disabled={enCours} onClick={() => agir(() => api.detacher(note.id))}>
              {note.statut === 'envoyee' ? 'Pas cette ligne' : 'Détacher'}
            </button>
          )}
        </div>
      )}
      {note && (note.nature !== 'frais' || note.etablie) && note.statut === 'envoyee' && refus === null && (
        <button
          type="button"
          className="btn btn--link nf-supprimer"
          disabled={enCours}
          onClick={() => agir(() => api.supprimerNote(note.id))}
        >
          Supprimer cette pièce
        </button>
      )}
      {refus !== null && (
        <>
          <label htmlFor="nf-motif">Motif du refus</label>
          <textarea id="nf-motif" rows={3} value={refus} onChange={(e) => setRefus(e.target.value)} autoFocus />
        </>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Choix de la personne pour qui le trésorier saisit : les membres de
// l'école, puis les personnes extérieures (notes-de-frais.md §7 quater), avec une
// recherche par nom ; en bas, « + Quelqu'un d'extérieur ».
export function ChoixPersonneModal({ onClose, onChoisie, initial = '' }) {
  const [personnes, setPersonnes] = useState(null)
  const [recherche, setRecherche] = useState(initial)
  const [nouvel, setNouvel] = useState(null) // { nom, email, rib }
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api
      .personnes()
      .then(setPersonnes)
      .catch((err) => setErreur(err.message))
  }, [])

  const cle = recherche.trim().toLocaleLowerCase('fr')
  const trouvees = (personnes ?? []).filter((p) => p.nom.toLocaleLowerCase('fr').includes(cle))
  const premierExterieur = trouvees.find((p) => p.role === 'extérieur')

  if (nouvel) {
    return (
      <Modal
        title="Quelqu’un d’extérieur"
        onClose={onClose}
        footer={
          <div className="nf-boutons">
            <button type="button" className="btn btn--secondary" onClick={() => setNouvel(null)}>
              Annuler
            </button>
            <button
              type="button"
              className="btn btn--primary"
              disabled={!nouvel.nom.trim()}
              onClick={async () => {
                setErreur('')
                try {
                  onChoisie(await api.ajouterExterieur({ ...nouvel, rib: nouvel.rib.iban.trim() ? nouvel.rib : null }))
                } catch (err) {
                  setErreur(err.message)
                }
              }}
            >
              Ajouter
            </button>
          </div>
        }
      >
        <FicheExterieur fiche={nouvel} onChange={setNouvel} />
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
      </Modal>
    )
  }

  return (
    <Modal title="Pour qui ?" onClose={onClose}>
      <input
        type="search"
        className="field-input"
        placeholder="Rechercher un nom"
        value={recherche}
        onChange={(e) => setRecherche(e.target.value)}
      />
      {!personnes && !erreur && <p className="muted">Chargement…</p>}
      <div className="nf-liste">
        {trouvees.map((p) => (
          <Fragment key={p.person_id}>
            {p === premierExterieur && <p className="nf-vir-h">Extérieurs</p>}
            <button type="button" className="nf-ligne nf-ligne--note" onClick={() => onChoisie(p)}>
              <span className="nf-ligne__corps">
                <span className="nf-ligne__titre">{p.nom}</span>
                {p.role && p.role !== 'extérieur' && <span className="muted">{p.role}</span>}
              </span>
            </button>
          </Fragment>
        ))}
      </div>
      {personnes && (
        <button
          type="button"
          className="btn btn--secondary nf-ajout-exterieur"
          onClick={() => setNouvel({ nom: recherche.trim(), email: '', telephone: '', rib: ribVide(null) })}
        >
          + Quelqu’un d’extérieur
        </button>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Nom, mail et RIB d'une personne extérieure : ajout depuis « Pour qui ? »,
// correction depuis Financier › ⋯ › Extérieurs.
export function FicheExterieur({ fiche, onChange }) {
  return (
    <>
      <label htmlFor="nf-ext-nom">Nom</label>
      <input id="nf-ext-nom" value={fiche.nom} onChange={(e) => onChange({ ...fiche, nom: e.target.value })} autoComplete="off" />
      <label htmlFor="nf-ext-email">Mail (facultatif, pour le prévenir)</label>
      <input
        id="nf-ext-email"
        type="email"
        value={fiche.email}
        onChange={(e) => onChange({ ...fiche, email: e.target.value })}
        autoComplete="off"
      />
      <label htmlFor="nf-ext-telephone">Téléphone (facultatif)</label>
      <input
        id="nf-ext-telephone"
        type="tel"
        value={fiche.telephone}
        onChange={(e) => onChange({ ...fiche, telephone: e.target.value })}
        autoComplete="off"
      />
      <ChampsRib rib={fiche.rib} onChange={(rib) => onChange({ ...fiche, rib })} />
    </>
  )
}
