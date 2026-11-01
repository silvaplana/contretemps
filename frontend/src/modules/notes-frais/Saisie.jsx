import { useEffect, useRef, useState } from 'react'
import { unzipSync } from 'fflate'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import Modal from '../../components/Modal.jsx'
import { BadgeEtat, NATURES, qui } from './commun.jsx'

const LISIBLE = (nom) => /\.(jpe?g|png|webp|gif|heic|heif|pdf)$/i.test(nom)
const TYPES = { pdf: 'application/pdf', jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp', gif: 'image/gif', heic: 'image/heic', heif: 'image/heif' }

// Un zip (dossier de factures) : un fichier dedans = une pièce ; les fichiers
// vides et les dossiers cachés sont laissés de côté.
async function depaqueter(zip) {
  const entrees = unzipSync(new Uint8Array(await zip.arrayBuffer()))
  return Object.entries(entrees)
    .filter(([chemin, octets]) => octets.length && LISIBLE(chemin) && !chemin.split('/').some((p) => p.startsWith('.') || p === '__MACOSX'))
    .sort(([a], [b]) => a.localeCompare(b, 'fr'))
    .map(([chemin, octets]) => {
      const nom = chemin.split('/').pop()
      return new File([octets], nom, { type: TYPES[nom.split('.').pop().toLowerCase()] ?? '' })
    })
}

// Ce que dit une ligne du lot sous le nom : nature et montant, ou ce que la
// preuve de virement a trouvé.
function sousTitre(note) {
  const montant = note.preuve?.montant_centimes ?? note.total_centimes
  if (note.sorte === 'virement') {
    if (note.id === null) {
      if (note.preuve.interne) return 'Virement entre les comptes de l’association : rien à faire'
      const op = note.preuve.operation
      return `Aucune pièce de ${api.euros(montant)} · ${op ? `sur le compte le ${api.dateCourte(op.date)} : ${op.libelle}` : 'pas encore sur le compte'}`
    }
    return `Paiement de : ${note.titre} · ${api.euros(montant)}${note.operation_id ? ' · payée selon la banque' : ''}`
  }
  return `${NATURES[note.nature]} · ${note.total_centimes ? api.euros(note.total_centimes) : 'Montant ?'}${note.operation_id ? ' · payée selon la banque' : ''}`
}

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
  const lotId = useRef(null) // l'import en cours, pour « Annuler cet import »

  function etablir(fichier) {
    const cle = `${Date.now()}-${Math.random()}`
    setLot((l) => [...l, { cle, nom: fichier.name, note: null }])
    lotId.current ??= crypto.randomUUID()
    const promesse = api
      .etablir(null, fichier, { batch_id: lotId.current })
      .then((note) => {
        setLot((l) => l.map((x) => (x.cle === cle ? { ...x, note } : x)))
        if (note.id !== null) onChange()
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

  async function importer(liste) {
    let fichiers = []
    for (const f of liste) {
      if (/\.zip$/i.test(f.name)) {
        try {
          fichiers.push(...(await depaqueter(f)))
        } catch {
          setErreur(`${f.name} : ce zip ne s’ouvre pas.`)
        }
      } else if (f.type.startsWith('image/') || f.type === 'application/pdf') {
        fichiers.push(f)
      }
    }
    // Une à une : la lecture de chaque pièce a son coût, pas de rafale au serveur.
    derniere.current = fichiers.reduce((suite, f) => suite.then(() => etablir(f)), Promise.resolve(null))
  }

  // Fichiers glissés sur Pièces depuis l'ordinateur.
  useEffect(() => {
    if (deposes) importer(deposes)
  }, [deposes]) // eslint-disable-line react-hooks/exhaustive-deps

  const enLecture = lot.some((x) => !x.note && !x.erreur)
  // À revoir : les pièces créées, une fois chacune (la preuve d'un virement
  // rejoint la pièce qu'elle paie, déjà dans le lot ou non).
  const lues = lot.filter((x) => x.note && x.note.id !== null).map((x) => x.note)
  const aRevoir = [...new Map(lues.map((n) => [n.id, n])).values()]

  function terminer() {
    const notes = aRevoir
    const batchId = lotId.current
    setLot([])
    setErreur('')
    lotId.current = null
    if (notes.length) onRevue(notes, batchId)
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
              {enLecture ? 'Lecture en cours…' : aRevoir.length ? `Terminé : vérifier ${aRevoir.length > 1 ? `les ${aRevoir.length} pièces` : 'la pièce'}` : 'Terminé'}
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
                <span className="nf-ligne__titre">
                  {x.note ? (x.note.sorte === 'virement' ? `Preuve de virement${x.note.id !== null ? ` · ${qui(x.note)}` : ''}` : qui(x.note)) : x.erreur ? 'Pas prise' : 'Lecture en cours…'}
                </span>
                <span className="muted">{x.note ? sousTitre(x.note) : x.erreur || x.nom}</span>
              </span>
              {x.note && x.note.id !== null && (
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
        accept="image/*,application/pdf,.zip,application/zip"
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
