import { useEffect, useMemo, useRef, useState } from 'react'
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
export default function AjoutEleveOcr({ ecoleId, onEleveAjoute, onClose }) {
  const [fichiers, setFichiers] = useState({ recto: null, verso: null })
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const [lue, setLue] = useState(null)
  const [message, setMessage] = useState('')
  const cadreRef = useRef(null)

  function choisir(face, fichier) {
    setErreur('')
    setFichiers((f) => ({ ...f, [face]: fichier }))
  }

  async function analyser() {
    setErreur('')
    setMessage('')
    setEnCours(true)
    try {
      const pages = await Promise.all(
        FACES.map((f) => fichiers[f.cle]).filter(Boolean).map(reduirePhoto)
      )
      setLue(await inscriptionsApi.lireFiche(ecoleId, pages))
    } catch (err) {
      setErreur(err.message)
    } finally {
      setEnCours(false)
    }
  }

  // Le formulaire (dans le cadre) annonce la fin de la saisie.
  useEffect(() => {
    function recevoir(evenement) {
      if (evenement.source !== cadreRef.current?.contentWindow) return
      const fin = evenement.data
      if (fin?.type !== 'contretemps-fiche') return
      setLue(null)
      setFichiers({ recto: null, verso: null })
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
    setLue(null)
  }

  if (lue) {
    return (
      <div className="ocr__formulaire">
        <div className="ocr__formulaire-entete">
          <strong>Inscription élève (OCR)</strong>
          <span className="muted">Lecture : {formaterCout(lue.coutUsd)}</span>
          <button type="button" className="icon-btn" onClick={abandonner} aria-label="Annuler cette fiche">
            <Icon name="x" />
          </button>
        </div>
        <iframe
          ref={cadreRef}
          title="Formulaire d'inscription pré-rempli"
          src={urlInscriptionDepuisFiche(lue.jeton)}
        />
      </div>
    )
  }

  return (
    <Modal
      title="Inscription élève (OCR)"
      onClose={onClose}
      footer={
        <button
          type="button"
          className="btn btn--primary btn--block"
          disabled={enCours || !fichiers.recto}
          onClick={analyser}
        >
          {enCours ? 'Lecture en cours…' : 'Lire la fiche'}
        </button>
      }
    >
      <p className="muted">
        La fiche d’inscription est en recto verso : il faut <strong>2 photos</strong>, une par face,
        bien à plat et nettes.
      </p>
      {/* Recto et verso côte à côte (demande utilisateur du 2026-10-02). */}
      <div className="ocr__faces">
        {FACES.map((face) => (
          <FaceFiche
            key={face.cle}
            face={face}
            fichier={fichiers[face.cle]}
            desactive={enCours}
            onChoisir={(fichier) => choisir(face.cle, fichier)}
          />
        ))}
      </div>
      {fichiers.recto && !fichiers.verso && !enCours && (
        <p className="muted">
          Sans le verso, le droit à l’image et le règlement intérieur seront à remplir à la main.
        </p>
      )}
      {enCours && <p className="muted">La lecture prend de 10 à 30 secondes.</p>}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {message && (
        <button type="button" className="acces-message ocr__message" role="status" onClick={() => setMessage('')}>
          {message}
        </button>
      )}
    </Modal>
  )
}

function FaceFiche({ face, fichier, desactive, onChoisir }) {
  const importRef = useRef(null)
  const photoRef = useRef(null)
  const galerieRef = useRef(null)
  const apercu = useMemo(
    () => (fichier?.type.startsWith('image/') ? URL.createObjectURL(fichier) : null),
    [fichier]
  )
  useEffect(() => () => apercu && URL.revokeObjectURL(apercu), [apercu])

  function recu(e) {
    const choisi = e.target.files?.[0]
    // Vidé pour pouvoir rechoisir le même fichier après une erreur.
    e.target.value = ''
    if (choisi) onChoisir(choisi)
  }

  return (
    <div className="ocr__face">
      <strong>{face.titre}</strong>
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
      <div className="ocr__boutons">
        <button
          type="button"
          className="btn btn--secondary"
          disabled={desactive}
          onClick={() => importRef.current?.click()}
        >
          Importer fichier
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={desactive}
          onClick={() => galerieRef.current?.click()}
        >
          Galerie
        </button>
        <button
          type="button"
          className="btn btn--secondary"
          disabled={desactive}
          onClick={() => photoRef.current?.click()}
        >
          <Icon name="camera" size={18} /> Prendre photo
        </button>
      </div>
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
