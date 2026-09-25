import { useState } from 'react'
import Icon from '../components/Icon.jsx'
import Modal from '../components/Modal.jsx'
import SegmentedTabs from '../components/SegmentedTabs.jsx'
import {
  DOCUMENTS_PRIVES,
  DOCUMENTS_PUBLICS,
  documentsPersonnels,
  genererProcuration,
} from '../data/documents.js'

// Module "Docs" (demande utilisateur du 2026-09-25) — PROTOTYPE, frontend
// seulement : les documents viennent de data/documents.js (contenus
// d'exemple), rien n'est lu ni enregistré sur le serveur. Accessible à
// tous les rôles, onglet placé juste avant "Profil" (voir data/nav.js).
// Trois sous-onglets : Public, Privé, Personnel.

const SOUS_ONGLETS = [
  { value: 'public', label: 'Public' },
  { value: 'prive', label: 'Privé' },
  { value: 'personnel', label: 'Personnel' },
]

function dateLisible(iso) {
  return new Date(`${iso}T12:00:00`).toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

function ListeDocuments({ documents, onOuvrir }) {
  if (documents.length === 0) return <p className="muted">Aucun document pour l’instant.</p>
  return (
    <div className="docs-liste">
      {documents.map((doc) => (
        <button key={doc.id} type="button" className="docs-carte" onClick={() => onOuvrir(doc)}>
          <Icon name="docs" size={22} />
          <span className="docs-carte__texte">
            <strong>{doc.titre}</strong>
            <span className="muted">{doc.sousTitre}</span>
            <span className="muted docs-carte__date">{dateLisible(doc.date)}</span>
          </span>
          <Icon name="chevronRight" size={18} />
        </button>
      ))}
    </div>
  )
}

// Lecture d'un document, avec "Imprimer" (ou "Enregistrer en PDF" depuis la
// fenêtre d'impression du navigateur) : seul le document est imprimé (voir
// App.css : body.impression-doc).
function LectureDocument({ doc, onRetour }) {
  function imprimer() {
    document.body.classList.add('impression-doc')
    window.print()
    document.body.classList.remove('impression-doc')
  }

  return (
    <div className="docs-lecture">
      <div className="docs-lecture__barre">
        <button type="button" className="btn btn--link" onClick={onRetour}>
          <Icon name="chevronLeft" size={18} /> Retour
        </button>
        <button type="button" className="btn btn--secondary" onClick={imprimer}>
          Imprimer
        </button>
      </div>
      <article className="docs-lecture__document">
        <h2>{doc.titre}</h2>
        <p className="muted">
          {doc.sousTitre} — {dateLisible(doc.date)}
        </p>
        {doc.sections.map((section, i) => (
          <section key={i}>
            {section.titre && <h3>{section.titre}</h3>}
            {section.paragraphes?.map((p, j) => (
              <p key={j}>{p}</p>
            ))}
            {section.liste && (
              <ul>
                {section.liste.map((li, j) => (
                  <li key={j}>{li}</li>
                ))}
              </ul>
            )}
          </section>
        ))}
        {doc.signature && <div className="docs-lecture__signature" aria-label="Emplacement de la signature" />}
      </article>
    </div>
  )
}

// "Générer une procuration" : le membre connecté donne pouvoir à un autre
// membre pour une assemblée générale.
function GenerateurProcuration({ user, onGenerer, onClose }) {
  const [champs, setChamps] = useState({
    mandant: [user?.prenom, user?.nom].filter(Boolean).join(' '),
    mandataire: '',
    dateAg: '2026-11-21',
    lieu: '',
  })
  const complet = champs.mandant.trim() && champs.mandataire.trim() && champs.dateAg && champs.lieu.trim()

  function champ(nom, libelle, type = 'text', placeholder = '') {
    return (
      <>
        <label htmlFor={`procuration-${nom}`}>{libelle}</label>
        <input
          id={`procuration-${nom}`}
          type={type}
          className="field-input"
          value={champs[nom]}
          placeholder={placeholder}
          onChange={(e) => setChamps((c) => ({ ...c, [nom]: e.target.value }))}
        />
      </>
    )
  }

  return (
    <Modal
      title="Générer une procuration"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={!complet}
          onClick={() =>
            onGenerer(
              genererProcuration({
                mandant: champs.mandant.trim(),
                mandataire: champs.mandataire.trim(),
                dateAg: champs.dateAg,
                lieu: champs.lieu.trim(),
              }),
            )
          }
        >
          Générer
        </button>
      }
    >
      <div className="form-fields">
        {champ('mandant', 'Je soussigné(e)')}
        {champ('mandataire', 'Donne pouvoir à', 'text', 'Prénom Nom du membre')}
        {champ('dateAg', 'Assemblée générale du', 'date')}
        {champ('lieu', 'Fait à', 'text', 'Ville')}
      </div>
    </Modal>
  )
}

export default function DocsScreen({ user }) {
  const [onglet, setOnglet] = useState('public')
  const [docOuvert, setDocOuvert] = useState(null)
  const [generateurOuvert, setGenerateurOuvert] = useState(false)
  // Procurations générées pendant cette visite (prototype : rien n'est
  // enregistré, elles disparaissent au rechargement).
  const [procurations, setProcurations] = useState([])

  if (docOuvert) {
    return (
      <div className="screen">
        <LectureDocument doc={docOuvert} onRetour={() => setDocOuvert(null)} />
      </div>
    )
  }

  const documents =
    onglet === 'public'
      ? DOCUMENTS_PUBLICS
      : onglet === 'prive'
        ? DOCUMENTS_PRIVES
        : [...procurations, ...documentsPersonnels(user)]

  return (
    <div className="screen">
      <p className="docs-prototype muted">Prototype : documents d’exemple, rien n’est encore enregistré.</p>
      <SegmentedTabs options={SOUS_ONGLETS} value={onglet} onChange={setOnglet} />
      <ListeDocuments documents={documents} onOuvrir={setDocOuvert} />
      {onglet === 'personnel' && (
        <button type="button" className="btn btn--primary btn--block" onClick={() => setGenerateurOuvert(true)}>
          Générer une procuration
        </button>
      )}
      {generateurOuvert && (
        <GenerateurProcuration
          user={user}
          onClose={() => setGenerateurOuvert(false)}
          onGenerer={(doc) => {
            setProcurations((liste) => [doc, ...liste])
            setGenerateurOuvert(false)
            setDocOuvert(doc)
          }}
        />
      )}
    </div>
  )
}
