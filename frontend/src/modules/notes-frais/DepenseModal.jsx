import { useEffect, useRef, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { Vignette } from './commun.jsx'

const TYPES = 'image/*,application/pdf'

// Nouvelle dépense ou modification (spec notes de frais §4.2, §4.3) : photo
// du ticket, lue par l'IA qui pré-remplit les champs ; sans photo, on
// saisit à la main (« sans justificatif »). Les photos choisies ne partent
// qu'à l'enregistrement.
export default function DepenseModal({ depense, categories, lectureDisponible, onClose, onEnregistree }) {
  const [jour, setJour] = useState(depense?.date ?? api.aujourdhui())
  const [montant, setMontant] = useState(api.versTexteMontant(depense?.montant_centimes))
  const [categorieId, setCategorieId] = useState(depense?.categorie?.id ?? '')
  const [description, setDescription] = useState(depense?.description ?? '')
  const [pieces, setPieces] = useState(depense?.pieces ?? [])
  const [aRetirer, setARetirer] = useState([])
  const [nouvelles, setNouvelles] = useState([])
  const [lecture, setLecture] = useState('')
  const [lueParIa, setLueParIa] = useState(false)
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)
  const camera = useRef(null)
  const galerie = useRef(null)

  // Photos pas encore envoyées, avec leur URL locale d'aperçu (libérée
  // quand on les retire ou ferme la fenêtre).
  const urls = useRef([])
  useEffect(() => () => urls.current.forEach((u) => URL.revokeObjectURL(u)), [])

  async function ajouterFichiers(liste) {
    const fichiers = [...liste]
    if (!fichiers.length) return
    const premiere = !pieces.length && !nouvelles.length
    const ajouts = fichiers.map((fichier) => ({ fichier, url: URL.createObjectURL(fichier) }))
    urls.current.push(...ajouts.map((a) => a.url))
    setNouvelles((n) => [...n, ...ajouts])
    // L'IA ne lit que la première photo d'une dépense encore vide.
    if (!premiere || !lectureDisponible) return
    setLecture('en_cours')
    try {
      const lu = await api.lireTicket(fichiers[0])
      if (lu.date) setJour(lu.date)
      if (lu.montant_centimes) setMontant(api.versTexteMontant(lu.montant_centimes))
      if (lu.categorie_id) setCategorieId(lu.categorie_id)
      if (lu.description) setDescription(lu.description)
      setLueParIa(true)
      setLecture('lue')
    } catch (err) {
      setLecture(err.message || 'Ticket illisible : remplissez à la main.')
    }
  }

  async function enregistrer() {
    setErreur('')
    const centimes = api.versCentimes(montant)
    if (!centimes) {
      setErreur('Indiquez le montant, par exemple 12,50.')
      return
    }
    const corps = {
      date: jour,
      montant_centimes: centimes,
      categorie_id: categorieId ? Number(categorieId) : null,
      description: description.trim(),
    }
    setEnCours(true)
    try {
      const enregistree = depense
        ? await api.modifierDepense(depense.id, corps)
        : await api.creerDepense({ ...corps, lue_par_ia: lueParIa })
      for (const id of aRetirer) await api.supprimerPiece(id)
      for (const { fichier } of nouvelles) await api.ajouterPiece(enregistree.id, fichier)
      onEnregistree()
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  async function supprimer() {
    setEnCours(true)
    try {
      await api.supprimerDepense(depense.id)
      onEnregistree()
    } catch (err) {
      setErreur(err.message)
      setEnCours(false)
    }
  }

  return (
    <Modal
      title={depense ? 'Modifier la dépense' : 'Nouvelle dépense'}
      onClose={onClose}
      footer={
        <div className="nf-boutons">
          {depense && (
            <button type="button" className="btn btn--danger" disabled={enCours} onClick={supprimer}>
              Supprimer
            </button>
          )}
          <button type="button" className="btn btn--primary" disabled={enCours || lecture === 'en_cours'} onClick={enregistrer}>
            Enregistrer
          </button>
        </div>
      }
    >
      <div className="nf-vignettes">
        {pieces.map((p) => (
          <Vignette
            key={p.id}
            piece={p}
            onSupprimer={() => {
              setPieces((l) => l.filter((x) => x.id !== p.id))
              setARetirer((l) => [...l, p.id])
            }}
          />
        ))}
        {nouvelles.map(({ fichier, url }) => (
          <div key={url} className="nf-vignette">
            <span className="nf-vignette__ouvrir">
              {fichier.type.startsWith('image/') ? <img src={url} alt="" /> : <Icon name="fileCheck" size={26} />}
            </span>
            <button
              type="button"
              className="nf-vignette__retirer"
              onClick={() => setNouvelles((l) => l.filter((x) => x.url !== url))}
              aria-label="Retirer la photo"
            >
              <Icon name="x" size={14} />
            </button>
          </div>
        ))}
      </div>
      <div className="nf-boutons nf-boutons--gauche">
        <button type="button" className="btn btn--secondary" onClick={() => camera.current?.click()}>
          <Icon name="camera" size={18} /> Photo du ticket
        </button>
        <button type="button" className="btn btn--secondary" onClick={() => galerie.current?.click()}>
          <Icon name="image" size={18} /> Choisir un fichier
        </button>
      </div>
      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => {
          ajouterFichiers(e.target.files)
          e.target.value = ''
        }}
      />
      <input
        ref={galerie}
        type="file"
        accept={TYPES}
        multiple
        hidden
        onChange={(e) => {
          ajouterFichiers(e.target.files)
          e.target.value = ''
        }}
      />
      {lecture === 'en_cours' && <p className="muted">Lecture du ticket…</p>}
      {lecture === 'lue' && <p className="badge badge--warning nf-a-verifier">Rempli d’après le ticket, à vérifier</p>}
      {lecture && lecture !== 'en_cours' && lecture !== 'lue' && <p className="muted">{lecture}</p>}
      {!pieces.length && !nouvelles.length && (
        <p className="muted">Pas de ticket (péage, parking…) ? Remplissez à la main : la dépense partira « sans justificatif ».</p>
      )}

      <label htmlFor="nf-date">Date</label>
      <input id="nf-date" type="date" value={jour} max={api.aujourdhui()} onChange={(e) => setJour(e.target.value)} />
      <label htmlFor="nf-montant">Montant (€)</label>
      <input
        id="nf-montant"
        inputMode="decimal"
        value={montant}
        onChange={(e) => setMontant(e.target.value)}
        placeholder="0,00"
      />
      <label htmlFor="nf-categorie">Catégorie</label>
      <select id="nf-categorie" value={categorieId} onChange={(e) => setCategorieId(e.target.value)}>
        <option value="">—</option>
        {categories.map((c) => (
          <option key={c.id} value={c.id}>
            {c.libelle}
          </option>
        ))}
      </select>
      <label htmlFor="nf-description">Description</label>
      <input
        id="nf-description"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Ex. tissu pour les costumes (Mondial Tissus)"
        maxLength={200}
      />
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}
