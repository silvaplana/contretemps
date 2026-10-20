import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import * as sessionApi from '../../api/session.js'
import Icon from '../../components/Icon.jsx'
import MenuEntete from '../../components/MenuEntete.jsx'
import Modal from '../../components/Modal.jsx'
import SegmentedTabs from '../../components/SegmentedTabs.jsx'
import Bilan, { requestNewReport } from '../finances/Bilan.jsx'
import Comptes, { requestStatementImport } from '../finances/Comptes.jsx'
import { telechargerFichier } from '../../utils/telechargement.js'
import { BadgeStatut } from './commun.jsx'
import { masquerIban } from './EnvoiModal.jsx'
import MesNotesDeFrais, { DetailDepenses } from './MesNotesDeFrais.jsx'
import './notes-frais.css'

const SOUS_ONGLETS = [
  { value: 'comptes', label: 'Comptes' },
  { value: 'notes', label: 'Notes de frais' },
  { value: 'bilan', label: 'Bilan' },
]

// Onglet Financier, trésoriers et Super User seulement (spec/modules/
// notes-de-frais.md §7) : Comptes et Bilan (spec/modules/financier.md),
// Notes de frais.
export default function Financier() {
  // Repart du dernier sous-onglet affiché sur cet appareil.
  const [sousOnglet, setSousOnglet] = useState(() => {
    const dernier = sessionApi.lireEcran('financier')
    return SOUS_ONGLETS.some((o) => o.value === dernier) ? dernier : 'notes'
  })
  useEffect(() => {
    sessionApi.sauvegarderEcran('financier', sousOnglet)
  }, [sousOnglet])
  // Saisie pour quelqu'un (menu ⋯) : d'abord choisir la personne, puis les
  // mêmes écrans que Profil › « Mes notes de frais », à son nom.
  const [choix, setChoix] = useState(null) // null | 'depense' | 'note'
  const [pour, setPour] = useState(null) // { personne, action }
  useEffect(() => () => api.agirPour(null), [])

  if (pour) {
    return (
      <MesNotesDeFrais
        key={pour.personne.person_id}
        pour={pour.personne}
        nouvelleDepense={pour.action === 'depense'}
        onBack={() => {
          api.agirPour(null)
          setPour(null)
        }}
      />
    )
  }

  return (
    <div className="screen nf-screen">
      <MenuEntete
        label="Actions du Financier"
        actions={
          sousOnglet === 'comptes'
            ? [{ label: 'Importer des relevés', icon: 'paperclip', onClick: requestStatementImport }]
            : sousOnglet === 'bilan'
              ? [{ label: 'Nouveau bilan', icon: 'plus', onClick: requestNewReport }]
              : [
                { label: 'Créer une dépense pour quelqu’un', icon: 'plus', onClick: () => setChoix('depense') },
                { label: 'Envoyer une note pour quelqu’un', icon: 'send', onClick: () => setChoix('note') },
              ]
        }
      />
      {choix && (
        <ChoixPersonneModal
          onClose={() => setChoix(null)}
          onChoisie={(personne) => {
            api.agirPour(personne.person_id)
            setPour({ personne, action: choix })
            setChoix(null)
          }}
        />
      )}
      <SegmentedTabs
        options={SOUS_ONGLETS}
        value={sousOnglet}
        onChange={setSousOnglet}
        className="admin-screen__tabs"
      />
      {sousOnglet === 'comptes' ? (
        <Comptes />
      ) : sousOnglet === 'bilan' ? (
        <Bilan />
      ) : (
        <NotesATraiter />
      )}
    </div>
  )
}

// Notes à valider, à rembourser, terminées.
function NotesATraiter() {
  const [filtre, setFiltre] = useState('a_valider')
  const [donnees, setDonnees] = useState(null)
  const [ouverte, setOuverte] = useState(null)
  const [cochees, setCochees] = useState(() => new Set())
  const [periode, setPeriode] = useState({ debut: '', fin: '' })
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api
      .tresorerie(filtre)
      .then((d) => {
        setDonnees(d)
        setErreur('')
      })
      .catch((err) => setErreur(err.message))
  }, [filtre])
  useEffect(charger, [charger])

  const compteurs = donnees?.compteurs ?? {}
  const options = [
    { value: 'a_valider', label: `À valider${compteurs.a_valider ? ` (${compteurs.a_valider})` : ''}` },
    { value: 'a_rembourser', label: `À rembourser${compteurs.a_rembourser ? ` (${compteurs.a_rembourser})` : ''}` },
    { value: 'terminees', label: `Terminées${compteurs.terminees ? ` (${compteurs.terminees})` : ''}` },
  ]

  let notes = donnees?.notes ?? []
  if (filtre === 'terminees') {
    notes = notes.filter((n) => {
      const jour = n.envoyee_le.slice(0, 10)
      return (!periode.debut || jour >= periode.debut) && (!periode.fin || jour <= periode.fin)
    })
  }
  const total = notes.reduce((s, n) => s + n.total_centimes, 0)
  const aRembourser = notes.filter((n) => cochees.has(n.id))

  async function marquerRemboursees() {
    try {
      await api.rembourser(aRembourser.map((n) => n.id))
      setCochees(new Set())
      charger()
    } catch (err) {
      setErreur(err.message)
    }
  }

  function basculer(id) {
    setCochees((actuel) => {
      const suivant = new Set(actuel)
      if (suivant.has(id)) suivant.delete(id)
      else suivant.add(id)
      return suivant
    })
  }

  return (
    <>
      <SegmentedTabs
        options={options}
        value={filtre}
        onChange={(v) => {
          setFiltre(v)
          setCochees(new Set())
        }}
      />

      {filtre === 'terminees' && (
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
              telechargerFichier(api.urlExport(periode.debut, periode.fin), 'notes-de-frais.xlsx').catch((err) =>
                setErreur(err.message),
              )
            }
          >
            <Icon name="download" size={18} /> Excel
          </button>
        </div>
      )}

      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {!donnees && !erreur && <p className="muted">Chargement…</p>}
      {donnees && notes.length === 0 && (
        <p className="muted">
          {filtre === 'a_valider'
            ? 'Aucune note à valider.'
            : filtre === 'a_rembourser'
              ? 'Aucune note à rembourser.'
              : 'Aucune note terminée sur cette période.'}
        </p>
      )}

      <div className="nf-liste">
        {notes.map((n) => (
          <div key={n.id} className="nf-ligne">
            {filtre === 'a_rembourser' && (
              <input
                type="checkbox"
                checked={cochees.has(n.id)}
                onChange={() => basculer(n.id)}
                aria-label={`Remboursée : ${n.titre}`}
              />
            )}
            <button type="button" className="nf-ligne__corps" onClick={() => setOuverte(n)}>
              <span className="nf-ligne__titre">{n.titre}</span>
              <span className="muted">
                {n.personne?.nom}
                {n.personne?.role ? ` (${n.personne.role})` : ''} · {api.dateCourte(n.envoyee_le)} · {n.depenses.length}{' '}
                dépense{n.depenses.length > 1 ? 's' : ''}
              </span>
              {filtre === 'a_rembourser' && n.rib && (
                <span className="muted nf-iban">
                  {n.rib.titulaire} · {n.rib.iban}
                </span>
              )}
            </button>
            <span className="nf-ligne__droite">
              <span className="nf-ligne__montant">{api.euros(n.total_centimes)}</span>
              {filtre === 'terminees' && <BadgeStatut note={n} />}
            </span>
          </div>
        ))}
      </div>

      {notes.length > 0 && (
        <p className="nf-total">
          Total : <strong>{api.euros(total)}</strong>
        </p>
      )}

      {filtre === 'a_rembourser' && notes.length > 0 && (
        <button type="button" className="btn btn--primary" disabled={!aRembourser.length} onClick={marquerRemboursees}>
          <Icon name="check" size={18} /> Marquer remboursées ({aRembourser.length}) ·{' '}
          {api.euros(aRembourser.reduce((s, n) => s + n.total_centimes, 0))}
        </button>
      )}

      {ouverte && (
        <NoteTresorierModal
          note={ouverte}
          onClose={() => setOuverte(null)}
          onTraitee={() => {
            setOuverte(null)
            charger()
          }}
        />
      )}
    </>
  )
}

// Détail d'une note (§7) : dépenses et photos, RIB, Valider / Refuser.
function NoteTresorierModal({ note, onClose, onTraitee }) {
  const [refus, setRefus] = useState(null)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  async function agir(action) {
    setErreur('')
    setEnCours(true)
    try {
      await action()
      onTraitee()
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  const footer =
    note.statut !== 'envoyee' ? null : refus === null ? (
      <div className="nf-boutons">
        <button type="button" className="btn btn--danger" disabled={enCours} onClick={() => setRefus('')}>
          Refuser…
        </button>
        <button type="button" className="btn btn--primary" disabled={enCours} onClick={() => agir(() => api.valider(note.id))}>
          Valider
        </button>
      </div>
    ) : (
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
          Refuser la note
        </button>
      </div>
    )

  return (
    <Modal title={note.titre} onClose={onClose} footer={footer}>
      <div className="nf-entete-note">
        <span>
          {note.personne?.nom}
          {note.personne?.role ? <span className="muted"> ({note.personne.role})</span> : null}
        </span>
        <BadgeStatut note={note} />
      </div>
      <p className="muted">
        Envoyée le {api.dateCourte(note.envoyee_le)}
        {note.traitee_par ? ` · traitée par ${note.traitee_par}` : ''}
      </p>
      <DetailDepenses depenses={note.depenses} />
      <p className="nf-total">
        Total : <strong>{api.euros(note.total_centimes)}</strong>
      </p>
      {note.don ? (
        <p className="badge badge--success">Don à l’association : pas de remboursement</p>
      ) : note.rib ? (
        <p className="nf-iban">
          RIB : {note.rib.titulaire ? `${note.rib.titulaire} · ` : ''}
          {note.statut === 'envoyee' ? masquerIban(note.rib.iban) : note.rib.iban}
          {note.rib.bic ? ` · ${note.rib.bic}` : ''}
        </p>
      ) : null}
      {note.motif_refus && <p className="login-screen__erreur">Motif du refus : {note.motif_refus}</p>}
      {note.depenses.some((d) => d.pieces.length) && (
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
      {refus !== null && (
        <>
          <label htmlFor="nf-motif">Motif du refus (envoyé à la personne)</label>
          <textarea id="nf-motif" rows={3} value={refus} onChange={(e) => setRefus(e.target.value)} autoFocus />
        </>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

// Choix de la personne pour qui le trésorier saisit : toutes les personnes
// de l'école, avec une recherche par nom.
function ChoixPersonneModal({ onClose, onChoisie }) {
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
