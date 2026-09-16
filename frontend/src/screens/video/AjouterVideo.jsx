import { useState } from 'react'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { compresserOuOriginal } from '../../utils/videoCompression.js'
import {
  annulerTeleversement,
  demarrerTeleversement,
  finaliserTeleversement,
  useProgressionTeleversement,
} from '../../utils/videoUploads.js'

// Ajout d'une vidéo, façon WhatsApp (demande utilisateur explicite) —
// réutilisé par l'onglet Vidéo (VideoScreen.jsx) et le détail d'une
// chorégraphie (ChoregraphieDetailScreen.jsx), même composant pour les
// deux (une seule implémentation). Déroulé :
//  1. Les 2 boutons "Filmer"/"Choisir une vidéo" sont TOUJOURS visibles
//     (pas cachés derrière un "+" à ouvrir d'abord).
//  2. Dès le fichier choisi/filmé, l'envoi démarre tout de suite (voir
//     utils/videoUploads.js) ET la modale de remplissage s'ouvre, avec un
//     aperçu local de la vidéo + une barre de progression pendant qu'on
//     tape le titre/la description.
//  3. "Ajouter" enregistre la ligne tout de suite (même si l'envoi n'est
//     pas fini, voir backend/src/videos/videos.py : statut 'en_cours') —
//     l'envoi continue en tâche de fond, indépendant de cette modale.
//     "Annuler" arrête tout et nettoie côté serveur.
export default function AjouterVideo({ coursId, choregraphies = [], lockedChoregraphieId, uploaderId, onAdded }) {
  const [session, setSession] = useState(null) // { uploadId, previewUrl }
  const [titre, setTitre] = useState('')
  const [description, setDescription] = useState('')
  const [choregraphieId, setChoregraphieId] = useState('')
  // Garde-fou contre un double-clic (voir AdminEleves.jsx pour le même
  // motif) : "Ajouter" appelle finaliserTeleversement, async.
  const [enCours, setEnCours] = useState(false)
  // Compression AVANT l'envoi (voir utils/videoCompression.js) : lancée
  // dès le fichier choisi, PENDANT que l'admin remplit le formulaire —
  // souvent terminée avant qu'il valide (conseil reçu, confirmé par
  // l'utilisateur). `null` : pas en cours (soit pas encore commencée,
  // soit déjà finie et l'envoi par blocs a pris le relais).
  const [compressionPourcentage, setCompressionPourcentage] = useState(null)
  const progression = useProgressionTeleversement(session?.uploadId)

  async function choisir(fichier) {
    if (!fichier) return
    const previewUrl = URL.createObjectURL(fichier)
    setSession({ uploadId: null, previewUrl })
    setTitre(fichier.name.replace(/\.[^/.]+$/, ''))
    setCompressionPourcentage(0)
    const fichierAEnvoyer = await compresserOuOriginal(fichier, {
      onProgress: setCompressionPourcentage,
    })
    setCompressionPourcentage(null)
    const uploadId = await demarrerTeleversement(coursId, fichierAEnvoyer)
    setSession({ uploadId, previewUrl })
  }

  function reinitialiser() {
    if (session) URL.revokeObjectURL(session.previewUrl)
    setSession(null)
    setTitre('')
    setDescription('')
    setChoregraphieId('')
    setEnCours(false)
    setCompressionPourcentage(null)
  }

  function annuler() {
    if (session?.uploadId) annulerTeleversement(session.uploadId)
    reinitialiser()
  }

  async function ajouter() {
    if (enCours || !session?.uploadId) return
    setEnCours(true)
    try {
      const video = await finaliserTeleversement(coursId, session.uploadId, {
        nom: titre,
        description,
        choregraphieId: lockedChoregraphieId ?? (choregraphieId || null),
        uploaderId,
      })
      onAdded(video)
      reinitialiser()
    } catch (err) {
      console.error(err)
      setEnCours(false)
    }
  }

  const pourcentage =
    progression?.octetsTotal ? Math.round((progression.octetsEnvoyes / progression.octetsTotal) * 100) : 0

  return (
    <>
      {/* Empilés en bas à droite, caméra au-dessus (voir .fab/.fab--secondary,
          même principe que "Importer des élèves" dans AdminEleves.jsx). */}
      <label className="fab--secondary" aria-label="Filmer une vidéo">
        <Icon name="camera" size={20} />
        <input
          type="file"
          accept="video/*"
          capture="environment"
          hidden
          onChange={(e) => choisir(e.target.files[0])}
        />
      </label>
      <label className="fab" aria-label="Choisir une vidéo">
        <Icon name="folder" size={24} />
        <input type="file" accept="video/*" hidden onChange={(e) => choisir(e.target.files[0])} />
      </label>

      {session && (
        <Modal
          title="Ajouter une vidéo"
          onClose={annuler}
          footer={
            <div className="video-upload-form__actions">
              <button type="button" className="btn btn--secondary" onClick={annuler}>
                Annuler
              </button>
              <button
                type="button"
                className="btn btn--primary"
                disabled={!titre || !session.uploadId || enCours}
                onClick={ajouter}
              >
                Ajouter
              </button>
            </div>
          }
        >
          <div className="video-upload-preview">
            <video className="video-upload-preview__video" src={session.previewUrl} controls playsInline />
            {(compressionPourcentage !== null || !progression?.complet) && (
              <div className="video-upload-preview__progress">
                <div
                  className="video-upload-preview__progress-bar"
                  style={{ width: `${compressionPourcentage ?? pourcentage}%` }}
                />
              </div>
            )}
          </div>
          <p className="muted">
            <Icon name={progression?.complet ? 'check' : 'clock'} size={14} />{' '}
            {compressionPourcentage !== null
              ? `Compression… ${compressionPourcentage}%`
              : progression?.complet
                ? 'Envoi terminé'
                : `Envoi en cours… ${pourcentage}%`}
          </p>

          <label htmlFor="add-video-titre">Titre</label>
          <input id="add-video-titre" value={titre} onChange={(e) => setTitre(e.target.value)} />

          {lockedChoregraphieId === undefined && (
            <>
              <label htmlFor="add-video-choregraphie">Chorégraphie</label>
              <select
                id="add-video-choregraphie"
                value={choregraphieId}
                onChange={(e) => setChoregraphieId(e.target.value)}
              >
                <option value="">Aucune</option>
                {choregraphies.map((ch) => (
                  <option key={ch.id} value={ch.id}>
                    {ch.nom}
                  </option>
                ))}
              </select>
            </>
          )}

          <label htmlFor="add-video-desc">Description (optionnelle)</label>
          <textarea
            id="add-video-desc"
            className="modal-textarea"
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </Modal>
      )}
    </>
  )
}
