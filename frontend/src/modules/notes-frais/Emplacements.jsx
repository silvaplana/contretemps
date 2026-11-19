import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'
import * as drivesApi from '../drives/api.js'

// Financier › Pièces › ⋯ › Emplacement des pièces manuelles (financier.md
// §8.13 ; maquette https://claude.ai/artifact/32JWw7Ga3jbpetgCXGbYMQ) : par
// nature, où va le fichier d'une pièce saisie avec « + ». Par défaut, les
// dossiers d'aujourd'hui.

const ANNULER_MS = 10000
const NATURES = [
  { nature: 'achat', label: 'Factures d’achat', suite: '', exemple: '2026-08-12 Facture Decathlon 39,90.pdf' },
  { nature: 'honoraires', label: 'Honoraires', suite: 'un dossier par prof, puis par note', exemple: 'MARYSA LEROY › 2025-10-31 Octobre › Facture.pdf' },
  { nature: 'frais', label: 'Notes de frais', suite: 'un dossier par personne, puis par note', exemple: 'Julia Dho › 2025-11-12 Gala › Ticket.jpg' },
  { nature: 'vente', label: 'Ventes', suite: 'un dossier par compte de recettes', exemple: 'COTISATIONS › Vente cotisation 150,00.pdf' },
]
const DEFAUTS = { achat: 'ACHATS', honoraires: 'HONORAIRES', frais: 'Notes de frais', vente: 'VENTES' }
const fleches = (path) => path.split('/').join(' › ')
const cle = (lieu) => (lieu.kind === 'docs' ? 'docs' : `drive:${lieu.drive_id}`)

function chemin(place, drives) {
  if (place.kind === 'docs') return `Docs › Financier › ${fleches(place.path)}`
  const drive = drives.find((d) => d.id === place.drive_id)
  return `Drive « ${drive?.name ?? '?'} » › ${fleches(place.path)} › saison`
}

// Choisir un dossier : sous Financier (Docs) ou sur un drive.
function ChoixDossier({ orgId, lieu, onChoix, onRetour }) {
  const [pile, setPile] = useState([])
  const [enfants, setEnfants] = useState(null)
  const [erreur, setErreur] = useState(null)
  const [nouveau, setNouveau] = useState('')
  const ici = pile.join('/')

  useEffect(() => {
    setEnfants(null)
    setErreur(null)
    const lire =
      lieu.kind === 'docs'
        ? api.dossiersFinancier(ici)
        : drivesApi.lister(orgId, lieu.drive_id, ici).then((l) => l.filter((e) => e.is_dir).map((e) => e.name))
    lire.then(setEnfants, (e) => setErreur(e.message))
  }, [orgId, lieu, ici])

  return (
    <div className="creer-saison" role="dialog" aria-label="Choisir un dossier">
      <div className="thread-screen__header">
        <button
          type="button"
          className="icon-btn"
          onClick={() => (pile.length ? setPile(pile.slice(0, -1)) : onRetour())}
          aria-label="Retour"
        >
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">Choisir un dossier</h2>
      </div>
      <div className="creer-saison__corps nf-emp">
        <p className="mail__discret">{[lieu.kind === 'docs' ? 'Docs › Financier' : lieu.label, ...pile].join(' › ')}</p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        {enfants === null && !erreur && <p className="mail__discret">Lecture…</p>}
        {enfants?.map((nom) => (
          <button key={nom} type="button" className="nf-emp__dossier" onClick={() => setPile([...pile, nom])}>
            📁 {nom}
          </button>
        ))}
        {enfants?.length === 0 && <p className="mail__discret">Aucun sous-dossier.</p>}
        <span className="nf-emp__ligne">
          <input
            type="text"
            className="nf-emp__nouveau"
            placeholder="Nouveau dossier"
            aria-label="Nouveau dossier"
            maxLength={80}
            value={nouveau}
            onChange={(e) => setNouveau(e.target.value)}
          />
          <button
            type="button"
            className="mail__lien"
            disabled={!nouveau.trim() || nouveau.includes('/')}
            onClick={() => {
              setPile([...pile, nouveau.trim()])
              setNouveau('')
            }}
          >
            Ajouter
          </button>
        </span>
        <button type="button" className="btn btn--primary" disabled={!pile.length} onClick={() => onChoix(ici)}>
          Choisir ce dossier
        </button>
      </div>
    </div>
  )
}

function Fiche({ orgId, drives, nature, place, onRegler, onRetour }) {
  const [choix, setChoix] = useState(null) // le lieu dont on choisit le dossier
  const lieux = [{ kind: 'docs', drive_id: null, label: 'Docs' }].concat(
    drives.map((d) => ({ kind: 'drive', drive_id: d.id, label: `Drive « ${d.name} »` })),
  )
  const valeur = cle(place)
  const achatParMois = nature.nature === 'achat' && place.by_month
  const exemple = `${chemin(place, drives).replace(/ › saison$/, ' › 2025-2026')} › ${achatParMois ? '08.2026 › ' : ''}${nature.exemple}`

  if (choix)
    return (
      <ChoixDossier
        orgId={orgId}
        lieu={choix}
        onRetour={() => setChoix(null)}
        onChoix={(path) => {
          onRegler({ kind: choix.kind, drive_id: choix.drive_id, path, by_month: place.by_month })
          setChoix(null)
        }}
      />
    )
  return (
    <div className="creer-saison" role="dialog" aria-label={nature.label}>
      <div className="thread-screen__header">
        <button type="button" className="icon-btn" onClick={onRetour} aria-label="Retour">
          <Icon name="chevronLeft" size={22} />
        </button>
        <h2 className="creer-saison__titre">{nature.label}</h2>
      </div>
      <div className="creer-saison__corps nf-emp">
        <label className="mail__champ">
          <span>Où</span>
          <select value={valeur} onChange={(e) => setChoix(lieux.find((l) => cle(l) === e.target.value))}>
            {lieux.map((l) => (
              <option key={cle(l)} value={cle(l)}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
        <label className="mail__champ">
          <span>Dossier</span>
          <button type="button" className="nf-emp__champ" onClick={() => setChoix(lieux.find((l) => cle(l) === valeur) ?? lieux[0])}>
            {chemin(place, drives).replace(/ › saison$/, '')}
          </button>
        </label>
        <p className="mail__discret">
          {place.kind === 'docs' ? 'Dans le dossier de chaque saison.' : 'L’appli y ajoute un dossier par saison.'}
        </p>
        {nature.nature === 'achat' ? (
          <label className="nf-emp__case">
            <input type="checkbox" checked={place.by_month} onChange={(e) => onRegler({ ...place, by_month: e.target.checked })} />
            <span>Un sous-dossier par mois (08.2026)</span>
          </label>
        ) : (
          <p className="mail__discret">Dessous, {nature.suite}.</p>
        )}
        <p className="nf-emp__exemple">
          <span className="mail__discret">Exemple :</span> {exemple}
        </p>
        <p className="mail__discret">
          Les fichiers déjà rangés restent où ils sont ; seules les nouvelles pièces vont dans le nouvel emplacement.
        </p>
        {!place.default && (
          <button
            type="button"
            className="mail__lien nf-emp__defaut"
            onClick={() => onRegler({ kind: 'docs', drive_id: null, path: DEFAUTS[nature.nature], by_month: true })}
          >
            Revenir à l’emplacement par défaut
          </button>
        )}
      </div>
    </div>
  )
}

export default function Emplacements({ onClose }) {
  const [etat, setEtat] = useState(null) // { org_id, places }
  const [drives, setDrives] = useState([])
  const [erreur, setErreur] = useState(null)
  const [ouverte, setOuverte] = useState(null) // nature
  const [toast, setToast] = useState(null)
  const minuteur = useRef(null)

  useEffect(() => {
    api
      .emplacements()
      .then((e) => {
        setEtat(e)
        drivesApi.etat(e.org_id).then((d) => setDrives(d.drives.filter((x) => !x.cut)), () => setDrives([]))
      })
      .catch((e) => setErreur(e.message))
    return () => clearTimeout(minuteur.current)
  }, [])

  const placeDe = (nature) => etat.places.find((p) => p.nature === nature)

  async function regler(nature, place, annulable = true) {
    const avant = placeDe(nature)
    setErreur(null)
    try {
      const apres = await api.reglerEmplacement(nature, place)
      setEtat((e) => ({ ...e, places: e.places.map((p) => (p.nature === nature ? apres : p)) }))
      if (!annulable) return
      clearTimeout(minuteur.current)
      const label = NATURES.find((n) => n.nature === nature).label
      setToast({ texte: `${label} : emplacement changé.`, nature, avant })
      minuteur.current = setTimeout(() => setToast(null), ANNULER_MS)
    } catch (e) {
      setErreur(e.message)
    }
  }

  const nature = ouverte && NATURES.find((n) => n.nature === ouverte)
  return createPortal(
    <div className="creer-saison" role="dialog" aria-label="Emplacement des pièces manuelles">
      <div className="thread-screen__header nf-emp__entete">
        <h2 className="creer-saison__titre">Emplacement des pièces manuelles</h2>
        <button type="button" className="icon-btn" onClick={onClose} aria-label="Fermer">
          <Icon name="x" size={22} />
        </button>
      </div>
      <div className="creer-saison__corps nf-emp">
        <p className="mail__discret">Où l’appli range le fichier d’une pièce saisie avec « + » (photo ou fichier).</p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        {etat &&
          NATURES.map((n) => (
            <button key={n.nature} type="button" className="nf-emp__nature" onClick={() => setOuverte(n.nature)}>
              <strong>{n.label}</strong>
              <span className="mail__discret">{chemin(placeDe(n.nature), drives)}</span>
            </button>
          ))}
      </div>
      {nature && (
        <Fiche
          orgId={etat.org_id}
          drives={drives}
          nature={nature}
          place={placeDe(nature.nature)}
          onRegler={(place) => regler(nature.nature, place)}
          onRetour={() => setOuverte(null)}
        />
      )}
      {toast && (
        <div className="admin-groupes__toast" role="status">
          <span>{toast.texte}</span>
          <button
            type="button"
            onClick={() => {
              clearTimeout(minuteur.current)
              setToast(null)
              const { kind, drive_id, path, by_month } = toast.avant
              regler(toast.nature, { kind, drive_id, path, by_month }, false)
            }}
          >
            Annuler
          </button>
        </div>
      )}
    </div>,
    document.body,
  )
}
