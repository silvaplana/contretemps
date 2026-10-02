import { useEffect, useRef, useState } from 'react'
import * as inscriptionsApi from '../../api/inscriptions.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { formaterCout, urlInscriptionDepuisFiche } from '../../utils/inscriptionEleve.js'
import { reduirePhoto } from '../../utils/reduirePhoto.js'

// La fiche papier est en recto verso : une photo par face.
const FACES = [
  { cle: 'recto', titre: 'Recto' },
  { cle: 'verso', titre: 'Verso' },
]

// « Inscription élève (OCR) » (Admin > Élèves, menu ⋮ — demande utilisateur
// du 2026-10-02) : l'admin photographie ou importe les deux faces d'une
// fiche d'inscription remplie à la main ; le serveur la fait lire par
// Claude, puis le formulaire d'inscription en ligne s'affiche pré-rempli,
// ici même, dans un cadre. « Enregistrer l'élève » l'ajoute à la liste
// officielle ; on revient alors à cet écran, vide, pour la fiche suivante,
// avec un message de confirmation en bas.
// Plusieurs membres d'une même famille d'un coup (« Galerie multi-membres »,
// demande utilisateur du 2026-10-02) : 2 ou 3 fiches, donc 4 ou 6 photos.
const MEMBRES_MAX = 3

export default function AjoutEleveOcr({ ecoleId, onEleveAjoute, onClose }) {
  const [fichiers, setFichiers] = useState({ recto: null, verso: null })
  // Photos de la galerie multi-membres, dans l'ordre : recto puis verso du
  // premier membre, recto puis verso du deuxième...
  const [photos, setPhotos] = useState([])
  const [enCours, setEnCours] = useState(0) // nombre de fiches en cours de lecture
  const [erreur, setErreur] = useState('')
  // Fiches lues, à vérifier l'une après l'autre : [{ jeton, coutUsd }].
  const [file, setFile] = useState([])
  const [total, setTotal] = useState(0)
  const [message, setMessage] = useState('')
  const cadreRef = useRef(null)
  const multiRef = useRef(null)
  const lue = file[0] ?? null

  // Pas de bouton « Lire la fiche » (demande utilisateur du 2026-10-02) :
  // la lecture part toute seule dès que les deux faces sont là.
  function choisir(face, fichier) {
    setErreur('')
    const suivants = { ...fichiers, [face]: fichier }
    setFichiers(suivants)
    if (suivants.recto && suivants.verso) analyser([[suivants.recto, suivants.verso]])
  }

  // `fiches` : une liste de [recto, verso]. Plusieurs fiches = une famille.
  async function analyser(fiches) {
    setErreur('')
    setMessage('')
    setEnCours(fiches.length)
    const famille = fiches.length > 1 ? Math.min(fiches.length, MEMBRES_MAX) : null
    const resultats = await Promise.allSettled(
      fiches.map(async (pages) =>
        inscriptionsApi.lireFiche(ecoleId, await Promise.all(pages.map(reduirePhoto)), famille)
      )
    )
    const lues = resultats.filter((r) => r.status === 'fulfilled').map((r) => r.value)
    const echecs = resultats
      .map((r, i) => (r.status === 'rejected' ? `fiche ${i + 1} : ${r.reason.message}` : null))
      .filter(Boolean)
    if (echecs.length > 0) {
      setErreur(fiches.length > 1 ? `Lecture impossible — ${echecs.join(' ; ')}` : resultats[0].reason.message)
    }
    if (lues.length > 0) setPhotos([])
    setTotal(lues.length)
    setFile(lues)
    setEnCours(0)
  }

  // Fiche suivante, ou retour à l'écran de saisie, vide, après la dernière.
  function suivante() {
    setFile((f) => f.slice(1))
    setFichiers({ recto: null, verso: null })
  }

  // Le formulaire (dans le cadre) annonce la fin de la saisie.
  useEffect(() => {
    function recevoir(evenement) {
      if (evenement.source !== cadreRef.current?.contentWindow) return
      const fin = evenement.data
      if (fin?.type !== 'contretemps-fiche') return
      suivante()
      if (fin.issue === 'enregistre') {
        setMessage(
          `${fin.prenom} ${fin.nom} a été ajouté(e) aux adhérents ${fin.saison}` +
            (fin.mailEnvoye ? '' : ' (le mail n’a pas pu être envoyé)')
        )
        onEleveAjoute()
      }
    }
    window.addEventListener('message', recevoir)
    return () => window.removeEventListener('message', recevoir)
  }, [onEleveAjoute])

  // Message temporaire.
  useEffect(() => {
    if (!message) return undefined
    const minuteur = setTimeout(() => setMessage(''), 8000)
    return () => clearTimeout(minuteur)
  }, [message])

  // Croix du cadre : la fiche en cours est abandonnée.
  function abandonner() {
    inscriptionsApi.annulerFiche(lue.jeton)
    suivante()
  }

  function photosChoisies(e) {
    const choisies = [...(e.target.files ?? [])]
    e.target.value = ''
    setErreur('')
    if (choisies.length > 0) setPhotos(choisies.slice(0, MEMBRES_MAX * 2))
  }

  // Avance une photo d'un cran : l'ordre rendu par le téléphone n'est pas
  // toujours celui de la sélection.
  function avancer(index) {
    setPhotos((p) => {
      const suivantes = [...p]
      ;[suivantes[index - 1], suivantes[index]] = [suivantes[index], suivantes[index - 1]]
      return suivantes
    })
  }

  const nbMembres = photos.length / 2
  const photosValides = photos.length >= 4 && photos.length % 2 === 0

  const messageBas = message && (
    <button type="button" className="acces-message ocr__message" role="status" onClick={() => setMessage('')}>
      {message}
    </button>
  )

  if (lue) {
    return (
      <div className="ocr__formulaire">
        <div className="ocr__formulaire-entete">
          <strong>
            Inscription élève (OCR)
            {total > 1 && ` — fiche ${total - file.length + 1} sur ${total}`}
          </strong>
          <span className="muted">Lecture : {formaterCout(lue.coutUsd)}</span>
          <button type="button" className="icon-btn" onClick={abandonner} aria-label="Annuler cette fiche">
            <Icon name="x" />
          </button>
        </div>
        {/* `key` : un cadre neuf par fiche. */}
        <iframe
          key={lue.jeton}
          ref={cadreRef}
          title="Formulaire d'inscription pré-rempli"
          src={urlInscriptionDepuisFiche(lue.jeton)}
        />
        {messageBas}
      </div>
    )
  }

  return (
    <Modal title="Inscription élève (OCR)" onClose={onClose}>
      <p className="muted">
        La fiche d’inscription est en recto verso : il faut <strong>2 photos</strong>, une par face,
        bien à plat et nettes. La lecture démarre dès que les deux sont là.
      </p>
      {/* Recto et verso côte à côte (demande utilisateur du 2026-10-02). */}
      <div className="ocr__faces">
        {FACES.map((face) => (
          <FaceFiche
            key={face.cle}
            face={face}
            fichier={fichiers[face.cle]}
            desactive={enCours > 0}
            onChoisir={(fichier) => choisir(face.cle, fichier)}
          />
        ))}
      </div>

      <div className="ocr__face">
        <strong>Plusieurs membres d’une famille</strong>
        <p className="muted">
          Choisissez toutes les photos d’un coup, <strong>dans l’ordre</strong> : recto puis verso du
          premier membre, recto puis verso du deuxième… (2 ou 3 membres). La réduction famille est
          appliquée à chacun.
        </p>
        <div className="ocr__boutons">
          <button
            type="button"
            className="btn btn--secondary"
            disabled={enCours > 0}
            onClick={() => multiRef.current?.click()}
          >
            <Icon name="image" size={18} /> Galerie multi-membres
          </button>
        </div>
        <input ref={multiRef} type="file" accept="image/*" multiple hidden onChange={photosChoisies} />
        {photos.length > 0 && (
          <>
            <div className="ocr__vignettes">
              {photos.map((photo, index) => (
                <Vignette
                  key={`${photo.name}-${photo.lastModified}-${index}`}
                  photo={photo}
                  legende={`Membre ${Math.floor(index / 2) + 1} — ${index % 2 === 0 ? 'recto' : 'verso'}`}
                  numero={index + 1}
                  desactive={enCours > 0}
                  onAvancer={index > 0 ? () => avancer(index) : null}
                  onRetirer={() => setPhotos((p) => p.filter((_, i) => i !== index))}
                />
              ))}
            </div>
            {!photosValides && (
              <p className="login-screen__erreur">
                Il faut 2 photos par membre, pour 2 ou 3 membres : 4 ou 6 photos ({photos.length}{' '}
                choisie{photos.length > 1 ? 's' : ''}).
              </p>
            )}
            <button
              type="button"
              className="btn btn--primary btn--block"
              disabled={!photosValides || enCours > 0}
              onClick={() =>
                analyser(Array.from({ length: nbMembres }, (_, i) => [photos[2 * i], photos[2 * i + 1]]))
              }
            >
              Lire les {photosValides ? nbMembres : ''} fiches
            </button>
          </>
        )}
      </div>

      {enCours > 0 && (
        <p className="ocr__attente" role="status">
          {enCours > 1
            ? `Lecture des ${enCours} fiches en cours, de 10 à 30 secondes`
            : 'Lecture de la fiche en cours, de 10 à 30 secondes'}
          <span className="ocr__points" aria-hidden="true">
            <span>.</span>
            <span>.</span>
            <span>.</span>
          </span>
          {/* Barre ESTIMÉE : le service de lecture n'indique pas son
              avancement. Elle avance vite au début, ralentit, et ne se
              remplit jamais seule ; la fiche s'affiche dès la réponse. */}
          <span className="ocr__barre" aria-hidden="true">
            <span />
          </span>
        </p>
      )}
      {erreur && (
        <>
          <p className="login-screen__erreur">{erreur}</p>
          {fichiers.recto && fichiers.verso && (
            <button
              type="button"
              className="btn btn--secondary btn--block"
              onClick={() => analyser([[fichiers.recto, fichiers.verso]])}
            >
              Réessayer
            </button>
          )}
        </>
      )}
      {messageBas}
    </Modal>
  )
}

// Adresse d'aperçu d'une image choisie (null pour un PDF). Créée et libérée
// dans le même effet : une adresse libérée trop tôt donne une image cassée.
function useApercu(fichier) {
  const [apercu, setApercu] = useState(null)
  useEffect(() => {
    if (!fichier?.type.startsWith('image/')) return undefined
    const url = URL.createObjectURL(fichier)
    setApercu(url)
    return () => {
      URL.revokeObjectURL(url)
      setApercu(null)
    }
  }, [fichier])
  return apercu
}

function Vignette({ photo, legende, numero, desactive, onAvancer, onRetirer }) {
  const apercu = useApercu(photo)
  return (
    <figure className="ocr__vignette">
      {apercu ? <img src={apercu} alt={legende} /> : <div className="ocr__vignette-vide" />}
      <span className="ocr__vignette-numero">{numero}</span>
      <figcaption>{legende}</figcaption>
      <div className="ocr__vignette-actions">
        {onAvancer && (
          <button type="button" className="icon-btn" disabled={desactive} onClick={onAvancer} aria-label={`Avancer la photo ${numero}`}>
            <Icon name="chevronLeft" size={18} />
          </button>
        )}
        <button type="button" className="icon-btn" disabled={desactive} onClick={onRetirer} aria-label={`Retirer la photo ${numero}`}>
          <Icon name="x" size={18} />
        </button>
      </div>
    </figure>
  )
}

function FaceFiche({ face, fichier, desactive, onChoisir }) {
  const importRef = useRef(null)
  const photoRef = useRef(null)
  const galerieRef = useRef(null)
  const apercu = useApercu(fichier)

  function recu(e) {
    const choisi = e.target.files?.[0]
    // Vidé pour pouvoir rechoisir le même fichier après une erreur.
    e.target.value = ''
    if (choisi) onChoisir(choisi)
  }

  return (
    <div className="ocr__face">
      <strong>{face.titre}</strong>
      <div className="ocr__boutons">
        <button
          type="button"
          className="btn btn--secondary"
          disabled={desactive}
          onClick={() => importRef.current?.click()}
        >
          <Icon name="docs" size={18} /> Importer
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={desactive}
          onClick={() => galerieRef.current?.click()}
        >
          <Icon name="image" size={18} /> Galerie
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={desactive}
          onClick={() => photoRef.current?.click()}
        >
          <Icon name="camera" size={18} /> Photo
        </button>
      </div>
      {/* L'image choisie, sous les boutons (demande utilisateur du 2026-10-02). */}
      {fichier && (
        <div className="ocr__apercu">
          {apercu ? <img src={apercu} alt={`${face.titre} de la fiche`} /> : <span>{fichier.name}</span>}
          <button
            type="button"
            className="icon-btn"
            disabled={desactive}
            onClick={() => onChoisir(null)}
            aria-label={`Retirer le ${face.titre.toLowerCase()}`}
          >
            <Icon name="x" size={18} />
          </button>
        </div>
      )}
      {/* Images ET PDF : sur téléphone, ouvre l'explorateur de fichiers (une
          fiche scannée peut être un PDF ou un JPG rangé dans un dossier). */}
      <input ref={importRef} type="file" accept="image/*,application/pdf" hidden onChange={recu} />
      {/* Images seules : sur téléphone, ouvre le sélecteur de photos du
          système, qui présente les dernières photos prises en premier. Une
          appli web ne peut pas lire elle-même les photos de l'appareil. */}
      <input ref={galerieRef} type="file" accept="image/*" hidden onChange={recu} />
      {/* `capture` : ouvre directement l'appareil photo sur téléphone. */}
      <input ref={photoRef} type="file" accept="image/*" capture="environment" hidden onChange={recu} />
    </div>
  )
}
