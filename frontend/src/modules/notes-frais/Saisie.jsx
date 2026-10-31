import { useEffect, useRef, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { BadgeEtat, NATURES, qui } from './commun.jsx'

// Financier › Pièces › « + » : Saisir une dépense (§7 quinquies). On prend
// les photos à la suite (ou on fournit des fichiers), chacune est lue et
// rangée dans la nature que l'appli propose ; « Terminé » ouvre la revue,
// pièce par pièce, où l'on valide d'un toucher ou l'on corrige.
export default function Saisie({ ouverte, deposes, onFermer, onALaMain, onRevue, onChange }) {
  const [lot, setLot] = useState([]) // { cle, nom, note | null, erreur }
  const [erreur, setErreur] = useState('')
  const camera = useRef(null)
  const galerie = useRef(null)
  const derniere = useRef(null) // promesse de la dernière pièce, pour « Encore une page »
  const page = useRef(false)

  function etablir(fichier) {
    const cle = `${Date.now()}-${Math.random()}`
    setLot((l) => [...l, { cle, nom: fichier.name, note: null }])
    const promesse = api
      .etablir(null, fichier)
      .then((note) => {
        setLot((l) => l.map((x) => (x.cle === cle ? { ...x, note } : x)))
        onChange()
        return note
      })
      .catch((err) => {
        setLot((l) => l.map((x) => (x.cle === cle ? { ...x, erreur: err.message } : x)))
        return null
      })
    return promesse
  }

  function photo(fichier) {
    if (!fichier) return
    if (page.current && derniere.current) {
      page.current = false
      derniere.current = derniere.current.then(async (note) => {
        if (!note) return null
        try {
          const complete = await api.ajouterPage(note.id, fichier)
          setLot((l) => l.map((x) => (x.note?.id === note.id ? { ...x, note: complete } : x)))
        } catch (err) {
          setErreur(err.message)
        }
        return note
      })
      return
    }
    derniere.current = etablir(fichier)
  }

  function importer(liste) {
    const fichiers = [...liste].filter((f) => f.type.startsWith('image/') || f.type === 'application/pdf')
    // Une à une : la lecture de chaque pièce a son coût, pas de rafale au serveur.
    derniere.current = fichiers.reduce((suite, f) => suite.then(() => etablir(f)), Promise.resolve(null))
  }

  // Fichiers glissés sur Pièces depuis l'ordinateur.
  useEffect(() => {
    if (deposes) importer(deposes)
  }, [deposes]) // eslint-disable-line react-hooks/exhaustive-deps

  const enLecture = lot.some((x) => !x.note && !x.erreur)
  const lues = lot.filter((x) => x.note).map((x) => x.note)

  function terminer() {
    const notes = lues
    setLot([])
    setErreur('')
    if (notes.length) onRevue(notes)
    else onFermer()
  }

  if (!ouverte && lot.length === 0) {
    return <Entrees camera={camera} galerie={galerie} photo={photo} importer={importer} />
  }

  return (
    <Modal
      title="Saisir une dépense"
      onClose={lot.length ? terminer : onFermer}
      footer={
        <div className="nf-choix">
          <button
            type="button"
            className="btn btn--primary"
            onClick={() => {
              page.current = false
              camera.current?.click()
            }}
          >
            <Icon name="camera" size={18} /> {lot.length ? 'Pièce suivante' : 'Prendre en photo'}
          </button>
          {lot.length > 0 && (
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
          )}
          <button type="button" className="btn btn--secondary" onClick={() => galerie.current?.click()}>
            <Icon name="image" size={18} /> {lot.length ? 'Ajouter des fichiers' : 'Choisir des fichiers'}
          </button>
          {lot.length === 0 && (
            <button type="button" className="btn btn--secondary" onClick={onALaMain}>
              <Icon name="edit" size={18} /> Saisir sans photo
            </button>
          )}
          {lot.length > 0 && (
            <button type="button" className="btn btn--link" disabled={enLecture} onClick={terminer}>
              {enLecture ? 'Lecture en cours…' : `Terminé : vérifier ${lues.length > 1 ? `les ${lues.length} pièces` : 'la pièce'}`}
            </button>
          )}
        </div>
      }
    >
      {lot.length === 0 ? (
        <p className="muted">
          Enchaînez les photos : chaque pièce est lue, et l’appli propose si c’est une note de frais, des honoraires ou
          un achat. Vous vérifiez ensuite, une par une.
        </p>
      ) : (
        <div className="nf-liste">
          {lot.map((x) => (
            <div key={x.cle} className="nf-ligne">
              <span className="nf-ligne__corps">
                <span className="nf-ligne__titre">{x.note ? qui(x.note) : x.erreur ? 'Pas prise' : 'Lecture en cours…'}</span>
                <span className="muted">
                  {x.note
                    ? `${NATURES[x.note.nature]} · ${x.note.total_centimes ? api.euros(x.note.total_centimes) : 'Montant ?'}`
                    : x.erreur || x.nom}
                </span>
              </span>
              {x.note && (
                <span className="nf-ligne__droite">
                  <BadgeEtat note={x.note} />
                </span>
              )}
            </div>
          ))}
        </div>
      )}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      <Entrees camera={camera} galerie={galerie} photo={photo} importer={importer} />
    </Modal>
  )
}

function Entrees({ camera, galerie, photo, importer }) {
  return (
    <>
      <input
        ref={camera}
        type="file"
        accept="image/*"
        capture="environment"
        hidden
        onChange={(e) => {
          photo(e.target.files[0])
          e.target.value = ''
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
    </>
  )
}
