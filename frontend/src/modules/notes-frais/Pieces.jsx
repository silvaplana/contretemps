import { useCallback, useEffect, useRef, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import * as sessionApi from '../../api/session.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import PiecesExemple from '../finances/exemple/Pieces.jsx'
import { telechargerFichier } from '../../utils/telechargement.js'
import { BadgeEtat, Compte, PaiementVu, Pieces as Vignettes, qui } from './commun.jsx'
import { DetailDepenses } from './MesNotesDeFrais.jsx'
import { masquerIban } from './EnvoiModal.jsx'
import Virements from './Virements.jsx'

// Financier › Pièces (spec/modules/financier.md §8.3 et §8.3 bis) : notes de
// frais, honoraires et achats sont une seule structure « dépense », avec une
// nature ; chaque puce en est un filtre. À rattacher et Ventes sont encore
// des écrans d'exemple. Un seul bouton principal, « + ».
const PUCES = [
  { value: 'virements', label: 'Virements' },
  { value: 'frais', label: 'Notes de frais' },
  { value: 'honoraires', label: 'Honoraires' },
  { value: 'achat', label: 'Achats' },
  { value: 'a_rattacher', label: 'À rattacher', exemple: true },
  { value: 'ventes', label: 'Ventes', exemple: true },
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
  const [plus, setPlus] = useState(false)
  const [natureAChoisir, setNatureAChoisir] = useState(false)

  const exemple = PUCES.find((p) => p.value === puce)?.exemple

  return (
    <section aria-label="Pièces" className="nf-pieces">
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
            <Compte n={aFaire[p.value]} />
          </button>
        ))}
      </div>
      {exemple ? (
        <PiecesExemple dossier={puce} />
      ) : puce === 'virements' ? (
        <Virements onChange={onChange} />
      ) : (
        <ListeNature
          key={puce}
          nature={puce}
          onCompteurs={onCompteurs}
          plus={plus}
          onPlusFerme={() => setPlus(false)}
          onPour={onPour}
        />
      )}
      {!exemple && (
        <div className="nf-barre">
          <span className="nf-barre__vide" />
          <button
            type="button"
            className="nf-barre__plus"
            aria-label="Ajouter une pièce"
            onClick={() => (puce === 'virements' ? setNatureAChoisir(true) : setPlus(true))}
          >
            <Icon name="plus" size={26} />
          </button>
        </div>
      )}
      {natureAChoisir && (
        <Modal title="Quelle pièce ?" onClose={() => setNatureAChoisir(false)}>
          <div className="nf-choix">
            {PUCES.filter((p) => !p.exemple && p.value !== 'virements').map((p) => (
              <button
                key={p.value}
                type="button"
                className="btn btn--secondary"
                onClick={() => {
                  setNatureAChoisir(false)
                  setPuce(p.value)
                  setPlus(true)
                }}
              >
                {p.label === 'Achats' ? 'Achat' : p.label === 'Notes de frais' ? 'Note de frais' : p.label}
              </button>
            ))}
          </div>
        </Modal>
      )}
    </section>
  )
}

// Une puce Notes de frais, Honoraires ou Achats : à valider en tête, puis le
// reste ; rafale, import de fichiers, glisser-déposer sur ordinateur.
function ListeNature({ nature, onCompteurs, plus, onPlusFerme, onPour }) {
  const [notes, setNotes] = useState(null)
  const [enLecture, setEnLecture] = useState([]) // { cle, nom }
  const [ouverte, setOuverte] = useState(null) // note | 'nouvelle'
  const [rafale, setRafale] = useState(false)
  const [periode, setPeriode] = useState({ debut: '', fin: '' })
  const [survol, setSurvol] = useState(false)
  const [erreur, setErreur] = useState('')
  const camera = useRef(null)
  const galerie = useRef(null)
  const derniere = useRef(null) // promesse de la dernière pièce de la rafale
  const page = useRef(false)

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

  // « + » : une note de frais se fait au nom de la personne (« Pour qui ? ») ;
  // honoraires et achats : photo, fichier, ou saisie.
  const choix = plus
  const setChoix = () => onPlusFerme()

  // Une photo ou un fichier = une pièce, créée tout de suite et lue par le
  // serveur ; la liste montre « Lecture en cours… » en attendant.
  function etablir(fichier) {
    const cle = `${Date.now()}-${Math.random()}`
    setEnLecture((l) => [...l, { cle, nom: fichier.name }])
    const promesse = api
      .etablir(nature, fichier)
      .then((note) => {
        setNotes((l) => [note, ...(l ?? [])])
        return note
      })
      .catch((err) => {
        setErreur(err.message)
        return null
      })
      .finally(() => {
        setEnLecture((l) => l.filter((x) => x.cle !== cle))
        charger()
      })
    return promesse
  }

  function photo(fichier) {
    if (!fichier) return
    if (page.current && derniere.current) {
      // Encore une page de la même pièce : attend qu'elle existe.
      page.current = false
      derniere.current = derniere.current.then(async (note) => {
        if (!note) return null
        try {
          await api.ajouterPage(note.id, fichier)
        } catch (err) {
          setErreur(err.message)
        }
        charger()
        return note
      })
      return
    }
    derniere.current = etablir(fichier)
  }

  function importer(liste) {
    const fichiers = [...liste].filter((f) => f.type.startsWith('image/') || f.type === 'application/pdf')
    // Une à une : la lecture de chaque pièce a son coût, pas de rafale au serveur.
    fichiers.reduce((suite, f) => suite.then(() => etablir(f)), Promise.resolve())
  }

  let visibles = notes ?? []
  if (periode.debut || periode.fin) {
    visibles = visibles.filter((n) => {
      const jour = n.depenses[0]?.date ?? n.envoyee_le.slice(0, 10)
      return (!periode.debut || jour >= periode.debut) && (!periode.fin || jour <= periode.fin)
    })
  }
  const glisser = SUR_ORDINATEUR && nature !== 'frais'

  return (
    <div
      className={survol ? 'nf-depot nf-depot--survol' : 'nf-depot'}
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
              importer(e.dataTransfer.files)
            }
          : undefined
      }
    >
      {glisser && <p className="muted">Glissez ici des factures depuis l’ordinateur : une par fichier.</p>}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!notes && !erreur && <p className="muted">Chargement…</p>}
      {notes && visibles.length === 0 && enLecture.length === 0 && <p className="muted">Rien pour l’instant.</p>}

      <div className="nf-liste">
        {enLecture.map((x) => (
          <div key={x.cle} className="nf-ligne">
            <span className="nf-ligne__corps">
              <span className="nf-ligne__titre">Lecture en cours…</span>
              <span className="muted">{x.nom}</span>
            </span>
          </div>
        ))}
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

      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => {
          photo(e.target.files[0])
          e.target.value = ''
          setRafale(true)
        }}
      />
      <input
        ref={galerie}
        type="file"
        accept="image/*,application/pdf"
        multiple
        hidden
        onChange={(e) => {
          importer(e.target.files)
          e.target.value = ''
        }}
      />

      {choix && nature === 'frais' && (
        <ChoixPersonneModal
          onClose={() => setChoix(false)}
          onChoisie={(personne) => {
            setChoix(false)
            onPour(personne, 'depense')
          }}
        />
      )}
      {choix && nature !== 'frais' && (
        <Modal title={nature === 'achat' ? 'Nouvel achat' : 'Nouveaux honoraires'} onClose={() => setChoix(false)}>
          <div className="nf-choix">
            <button
              type="button"
              className="btn btn--primary"
              onClick={() => {
                setChoix(false)
                camera.current?.click()
              }}
            >
              <Icon name="camera" size={18} /> Photo du ticket
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => {
                setChoix(false)
                galerie.current?.click()
              }}
            >
              <Icon name="image" size={18} /> Choisir un fichier
            </button>
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => {
                setChoix(false)
                setOuverte('nouvelle')
              }}
            >
              <Icon name="edit" size={18} /> Saisir sans photo
            </button>
          </div>
          <p className="muted">
            Avec l’appareil photo, enchaînez les pièces : chacune est lue et rangée, vous vérifiez ensuite dans la liste.
          </p>
        </Modal>
      )}

      {rafale && (
        <div className="nf-rafale" role="group" aria-label="Rafale de photos">
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => {
              page.current = false
              camera.current?.click()
            }}
          >
            <Icon name="camera" size={18} /> Pièce suivante
          </button>
          <button
            type="button"
            className="btn btn--secondary"
            onClick={() => {
              page.current = true
              camera.current?.click()
            }}
          >
            Encore une page de celle-ci
          </button>
          <button type="button" className="btn btn--link" onClick={() => setRafale(false)}>
            Terminé
          </button>
        </div>
      )}

      {ouverte && (
        <NoteModal
          note={ouverte === 'nouvelle' ? null : ouverte}
          nature={nature}
          onClose={() => setOuverte(null)}
          onFait={() => {
            setOuverte(null)
            charger()
          }}
        />
      )}
    </div>
  )
}

// Détail d'une pièce. Note de frais : Valider / Refuser (la personne corrige
// elle-même). Honoraires et achat : ce que la lecture a rempli, à vérifier ou
// corriger, puis Valider ; `note` null = saisie sans photo.
function NoteModal({ note, nature, onClose, onFait }) {
  const corrigeable = note === null || (note.nature !== 'frais' && ['envoyee', 'validee'].includes(note.statut))
  const depense = note?.depenses[0]
  const [personnes, setPersonnes] = useState(null)
  const [personId, setPersonId] = useState(note?.personne?.person_id ?? '')
  const [fournisseur, setFournisseur] = useState(note?.fournisseur ?? '')
  const [jour, setJour] = useState(depense?.date ?? api.aujourdhui())
  const [montant, setMontant] = useState(api.versTexteMontant(depense?.montant_centimes || null))
  const [description, setDescription] = useState(depense?.description ?? '')
  const [refus, setRefus] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const genre = note?.nature ?? nature

  useEffect(() => {
    if (genre !== 'honoraires' || !corrigeable) return
    api
      .personnes()
      .then(setPersonnes)
      .catch((err) => setErreur(err.message))
  }, [genre, corrigeable])

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
    if (genre === 'honoraires' && !personId) throw new Error('Choisissez pour qui sont ces honoraires.')
    return {
      date: jour,
      montant_centimes: centimes,
      description: description.trim(),
      ...(genre === 'honoraires' ? { person_id: Number(personId) } : { fournisseur: fournisseur.trim() }),
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
          {aValider ? 'Valider' : 'Enregistrer'}
        </button>
      </div>
    )

  return (
    <Modal title={note ? (note.nature === 'achat' ? 'Achat' : note.titre) : genre === 'achat' ? 'Nouvel achat' : 'Nouveaux honoraires'} onClose={onClose} footer={footer}>
      {note && (
        <div className="nf-entete-note">
          <span>
            {qui(note)}
            {note.nature !== 'achat' && note.personne?.role ? <span className="muted"> ({note.personne.role})</span> : null}
          </span>
          <BadgeEtat note={note} />
        </div>
      )}
      {note && <PaiementVu note={note} onConfirme={(op) => agir(() => api.payee(note.id, op.id))} />}
      {note && depense?.lue_par_ia && corrigeable && (
        <p className="badge badge--warning nf-a-verifier">Rempli d’après le ticket, à vérifier</p>
      )}
      {corrigeable ? (
        <>
          {note && <Vignettes pieces={note.depenses.flatMap((d) => d.pieces)} />}
          {genre === 'honoraires' ? (
            <>
              <label htmlFor="nf-pour">Pour qui ?</label>
              <select id="nf-pour" value={personId} onChange={(e) => setPersonId(e.target.value)}>
                <option value="">—</option>
                {(personnes ?? []).map((p) => (
                  <option key={p.person_id} value={p.person_id}>
                    {p.nom}
                  </option>
                ))}
              </select>
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
      {note && note.nature !== 'frais' && note.statut === 'envoyee' && refus === null && (
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

// Choix de la personne pour qui le trésorier saisit : toutes les personnes
// de l'école, avec une recherche par nom.
export function ChoixPersonneModal({ onClose, onChoisie }) {
  const [personnes, setPersonnes] = useState(null)
  const [recherche, setRecherche] = useState('')
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    api
      .personnes()
      .then(setPersonnes)
      .catch((err) => setErreur(err.message))
  }, [])

  const cle = recherche.trim().toLocaleLowerCase('fr')
  const trouvees = (personnes ?? []).filter((p) => p.nom.toLocaleLowerCase('fr').includes(cle))

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
          <button key={p.person_id} type="button" className="nf-ligne nf-ligne--note" onClick={() => onChoisie(p)}>
            <span className="nf-ligne__corps">
              <span className="nf-ligne__titre">{p.nom}</span>
              {p.role && <span className="muted">{p.role}</span>}
            </span>
          </button>
        ))}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}
