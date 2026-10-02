import { useEffect, useMemo, useRef, useState } from 'react'
import * as inscriptionsApi from '../../api/inscriptions.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { formaterCout, urlInscriptionDepuisFiche } from '../../utils/inscriptionEleve.js'
import { reduirePhoto } from '../../utils/reduirePhoto.js'

// La fiche papier est en recto verso : une photo par face.
const FACES = [
  { cle: 'recto', titre: 'Recto', aide: "Informations de l'élève, cours, urgence, santé" },
  { cle: 'verso', titre: 'Verso', aide: "Droit à l'image et règlement intérieur" },
]

// « Ajouter élève (OCR) » (Admin > Élèves, menu ⋮ — demande utilisateur du
// 2026-10-02) : l'admin photographie ou importe les deux faces d'une fiche
// d'inscription remplie à la main ; le serveur la fait lire par Claude,
// puis le formulaire d'inscription en ligne s'ouvre pré-rempli, à corriger
// et valider. L'inscription suit alors le même chemin qu'une inscription
// en ligne. Le coût de la lecture est annoncé dès qu'elle est finie.
export default function AjoutEleveOcr({ ecoleId, onClose }) {
  const [fichiers, setFichiers] = useState({ recto: null, verso: null })
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')
  const [lue, setLue] = useState(null)

  function choisir(face, fichier) {
    setErreur('')
    setFichiers((f) => ({ ...f, [face]: fichier }))
  }

  async function analyser() {
    setErreur('')
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

  function annuler() {
    if (lue) inscriptionsApi.annulerFiche(lue.jeton)
    onClose()
  }

  if (lue) {
    return (
      <Modal title="Ajouter élève (OCR)" onClose={annuler}>
        <p>
          <strong>Fiche lue.</strong>{' '}
          {lue.nbChampsDouteux > 0
            ? `${lue.nbChampsDouteux} champ${lue.nbChampsDouteux > 1 ? 's' : ''} à vérifier en priorité.`
            : 'Relisez tout de même chaque champ.'}
        </p>
        <p className="ocr__cout">Coût de la lecture : {formaterCout(lue.coutUsd)}</p>
        {/* Un vrai lien, cliqué par l'admin : une fenêtre ouverte après
            l'attente de la lecture serait bloquée par le navigateur. */}
        <a
          className="btn btn--primary btn--block"
          href={urlInscriptionDepuisFiche(lue.jeton)}
          target="_blank"
          rel="noopener"
          onClick={onClose}
        >
          Ouvrir le formulaire rempli
        </a>
        <button type="button" className="btn btn--secondary btn--block" onClick={annuler}>
          Annuler
        </button>
      </Modal>
    )
  }

  return (
    <Modal
      title="Ajouter élève (OCR)"
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
      {FACES.map((face) => (
        <FaceFiche
          key={face.cle}
          face={face}
          fichier={fichiers[face.cle]}
          desactive={enCours}
          onChoisir={(fichier) => choisir(face.cle, fichier)}
        />
      ))}
      {fichiers.recto && !fichiers.verso && !enCours && (
        <p className="muted">
          Sans le verso, le droit à l’image et le règlement intérieur seront à remplir à la main.
        </p>
      )}
      {enCours && <p className="muted">La lecture prend de 10 à 30 secondes.</p>}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
    </Modal>
  )
}

function FaceFiche({ face, fichier, desactive, onChoisir }) {
  const importRef = useRef(null)
  const photoRef = useRef(null)
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
      <div className="ocr__face-titre">
        <strong>{face.titre}</strong>
        <span className="muted">{face.aide}</span>
      </div>
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
          onClick={() => photoRef.current?.click()}
        >
          <Icon name="camera" size={18} /> Prendre photo
        </button>
      </div>
      <input ref={importRef} type="file" accept="image/*,application/pdf" hidden onChange={recu} />
      {/* `capture` : ouvre directement l'appareil photo sur téléphone. */}
      <input ref={photoRef} type="file" accept="image/*" capture="environment" hidden onChange={recu} />
    </div>
  )
}
