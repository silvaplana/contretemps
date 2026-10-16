import { useCallback, useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { BadgeStatut, Pieces } from './commun.jsx'
import DepenseModal from './DepenseModal.jsx'
import EnvoiModal from './EnvoiModal.jsx'
import './notes-frais.css'

// Profil > « Mes notes de frais » (spec/modules/notes-de-frais.md §4) :
// en haut les dépenses « À envoyer » (cochées par défaut), en dessous les
// notes envoyées et leur statut.
export default function MesNotesDeFrais({ onBack }) {
  const [donnees, setDonnees] = useState(null)
  const [decochees, setDecochees] = useState(() => new Set())
  const [edition, setEdition] = useState(null) // null | 'nouvelle' | dépense
  const [envoi, setEnvoi] = useState(false)
  const [noteOuverte, setNoteOuverte] = useState(null)
  const [erreur, setErreur] = useState('')

  const charger = useCallback(() => {
    api
      .espace()
      .then(setDonnees)
      .catch((err) => setErreur(err.message))
  }, [])
  useEffect(charger, [charger])

  if (!donnees) {
    return (
      <div className="screen nf-screen">
        <Retour onBack={onBack} />
        {erreur ? <p className="login-screen__erreur">{erreur}</p> : <p className="muted">Chargement…</p>}
      </div>
    )
  }

  const choisies = donnees.a_envoyer.filter((d) => !decochees.has(d.id))
  const totalChoisi = choisies.reduce((s, d) => s + d.montant_centimes, 0)

  function basculer(id) {
    setDecochees((actuel) => {
      const suivant = new Set(actuel)
      if (suivant.has(id)) suivant.delete(id)
      else suivant.add(id)
      return suivant
    })
  }

  return (
    <div className="screen nf-screen">
      <Retour onBack={onBack} />

      <section>
        <h3 className="section-label">À envoyer</h3>
        {donnees.a_envoyer.length === 0 ? (
          <p className="muted">
            Aucune dépense en attente. Appuyez sur « + » et prenez le ticket en photo : il est lu et rempli pour vous.
          </p>
        ) : (
          <div className="nf-liste">
            {donnees.a_envoyer.map((d) => (
              <div key={d.id} className="nf-ligne">
                <input
                  type="checkbox"
                  checked={!decochees.has(d.id)}
                  onChange={() => basculer(d.id)}
                  aria-label={`Envoyer ${d.description || 'cette dépense'}`}
                />
                <button type="button" className="nf-ligne__corps" onClick={() => setEdition(d)}>
                  <span className="nf-ligne__titre">{d.description || d.categorie?.libelle || 'Dépense'}</span>
                  <span className="muted">
                    {api.dateCourte(d.date)}
                    {d.categorie ? ` · ${d.categorie.libelle}` : ''}
                    {d.sans_justificatif && <span className="badge badge--warning nf-mini">sans justificatif</span>}
                  </span>
                </button>
                <span className="nf-ligne__montant">{api.euros(d.montant_centimes)}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      {donnees.notes.length > 0 && (
        <section>
          <h3 className="section-label">Envoyées</h3>
          <div className="nf-liste">
            {donnees.notes.map((n) => (
              <button key={n.id} type="button" className="nf-ligne nf-ligne--note" onClick={() => setNoteOuverte(n)}>
                <span className="nf-ligne__corps">
                  <span className="nf-ligne__titre">{n.titre}</span>
                  <span className="muted">
                    {api.dateCourte(n.envoyee_le)} · {n.depenses.length} dépense{n.depenses.length > 1 ? 's' : ''}
                  </span>
                </span>
                <span className="nf-ligne__droite">
                  <span className="nf-ligne__montant">{api.euros(n.total_centimes)}</span>
                  <BadgeStatut note={n} />
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="nf-barre">
        <button
          type="button"
          className="btn btn--primary nf-barre__envoyer"
          disabled={choisies.length === 0}
          onClick={() => setEnvoi(true)}
        >
          <Icon name="send" size={18} /> Envoyer ({choisies.length}) · {api.euros(totalChoisi)}
        </button>
        <button type="button" className="nf-barre__plus" onClick={() => setEdition('nouvelle')} aria-label="Nouvelle dépense">
          <Icon name="plus" size={26} />
        </button>
      </div>

      {edition && (
        <DepenseModal
          depense={edition === 'nouvelle' ? null : edition}
          categories={donnees.categories}
          lectureDisponible={donnees.lecture_disponible}
          onClose={() => setEdition(null)}
          onEnregistree={() => {
            setEdition(null)
            charger()
          }}
        />
      )}
      {envoi && (
        <EnvoiModal
          depenses={choisies}
          rib={donnees.rib}
          tresoriers={donnees.tresoriers}
          onClose={() => setEnvoi(false)}
          onEnvoyee={() => {
            setEnvoi(false)
            setDecochees(new Set())
            charger()
          }}
        />
      )}
      {noteOuverte && (
        <NoteModal
          note={noteOuverte}
          onClose={() => setNoteOuverte(null)}
          onReprise={() => {
            setNoteOuverte(null)
            charger()
          }}
        />
      )}
    </div>
  )
}

function Retour({ onBack }) {
  return (
    <button type="button" className="btn btn--link nf-retour" onClick={onBack}>
      <Icon name="chevronLeft" size={18} /> Profil
    </button>
  )
}

// Détail d'une note envoyée ; « Reprendre » tant qu'aucun trésorier ne l'a
// validée, ou après un refus (spec §4.4, §5).
function NoteModal({ note, onClose, onReprise }) {
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const reprenable = note.statut === 'envoyee' || note.statut === 'refusee'

  async function reprendre() {
    setEnCours(true)
    try {
      await api.reprendre(note.id)
      onReprise()
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <Modal
      title={note.titre}
      onClose={onClose}
      footer={
        reprenable && (
          <button type="button" className="btn btn--secondary btn--block" disabled={enCours} onClick={reprendre}>
            Reprendre (les dépenses repassent « À envoyer »)
          </button>
        )
      }
    >
      <div className="nf-entete-note">
        <BadgeStatut note={note} />
        <strong>{api.euros(note.total_centimes)}</strong>
      </div>
      {note.motif_refus && <p className="login-screen__erreur">Motif du refus : {note.motif_refus}</p>}
      <DetailDepenses depenses={note.depenses} />
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

export function DetailDepenses({ depenses }) {
  return (
    <div className="nf-detail">
      {depenses.map((d) => (
        <div key={d.id} className="nf-detail__depense">
          <div className="nf-detail__ligne">
            <span>
              <strong>{d.description || 'Dépense'}</strong>
              <span className="muted">
                {' '}
                · {api.dateCourte(d.date)}
                {d.categorie ? ` · ${d.categorie.libelle}` : ''}
              </span>
            </span>
            <span className="nf-ligne__montant">{api.euros(d.montant_centimes)}</span>
          </div>
          <Pieces pieces={d.pieces} />
        </div>
      ))}
    </div>
  )
}
