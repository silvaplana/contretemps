import { useCallback, useEffect, useRef, useState } from 'react'
import { documentsApi } from '../../api/documents.js'
import VideoThumb from '../../components/VideoThumb.jsx'
import {
  annulerTeleversement,
  demarrerTeleversement,
  finaliserTeleversement,
  useProgressionTeleversement,
} from '../../utils/videoUploads.js'
import * as api from './api.js'
import './news.css'

// Actualités (spec/modules/actualites.md, maquette validée
// spec/maquettes/actualites.html). Tout le monde lit les actus ; qui a le
// droit 🔒 « Publier les actualités » a deux onglets, Édition et Visualisation.
// Un éditeur ouvert remplace l'écran, avec la flèche de retour.

const ANNULER_MS = 10000
const VIDEO_MAX = 100 * 1024 * 1024 // avant compression, comme la Messagerie (§4.2)
const NIVEAUX = [
  { cle: 'important', libelle: 'Important', aide: 'En haut des actus, en rouge, jusqu’à la date choisie. Pour ce qui ne doit pas être manqué.' },
  { cle: 'normal', libelle: 'Normal', aide: 'Une grande carte.' },
  { cle: 'brief', libelle: 'Brève', aide: 'Une ligne. Pour les petites infos.' },
]
const LIBELLE = Object.fromEntries(NIVEAUX.map((n) => [n.cle, n.libelle]))

const jour = (d) => d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long' })
const iso = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
function dansJours(n) {
  const d = new Date()
  d.setDate(d.getDate() + n)
  return iso(d)
}

// « Aujourd'hui », « Cette semaine », « Plus tôt » (§3.2).
function periode(date) {
  const debut = new Date()
  debut.setHours(0, 0, 0, 0)
  if (date >= debut) return 'Aujourd’hui'
  debut.setDate(debut.getDate() - 6)
  return date >= debut ? 'Cette semaine' : 'Plus tôt'
}

function Alerte() {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 3l10 18H2z" />
      <path d="M12 10v5M12 18v.5" />
    </svg>
  )
}

const IconePhoto = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <circle cx="9" cy="10" r="2" />
    <path d="M21 16l-5-5-8 8" />
  </svg>
)
const IconeVideo = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <rect x="3" y="6" width="13" height="12" rx="2" />
    <path d="M16 10l5-3v10l-5-3" />
  </svg>
)
const IconeFichier = ({ taille = 20 }) => (
  <svg viewBox="0 0 24 24" width={taille} height={taille} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
  </svg>
)

// La photo d'une actu : lue avec la session, ou la copie locale juste
// choisie dans l'éditeur.
function Photo({ ecoleId, actu }) {
  const [url, setUrl] = useState(null)
  const { id, photo, photoLocale } = actu
  useEffect(() => {
    if (photoLocale || !id || !photo) return undefined
    let annule = false
    api.lirePhoto(ecoleId, { id, photo }).then((u) => !annule && setUrl(u), () => {})
    return () => {
      annule = true
    }
  }, [ecoleId, id, photo, photoLocale])
  const src = photoLocale || url
  return <div className="actu__media">{src && <img src={src} alt="" />}</div>
}

// La vidéo pas encore envoyée, lue sur ce téléphone pendant l'envoi.
function VideoLocale({ uploadId }) {
  const etat = useProgressionTeleversement(uploadId)
  if (!etat) return null
  const pourcentage = etat.octetsTotal ? Math.round((etat.octetsEnvoyes / etat.octetsTotal) * 100) : 0
  return (
    <div className="actu__media">
      <video src={etat.previewUrl} controls playsInline />
      {!etat.complet && <div className="actu__envoi" style={{ width: `${pourcentage}%` }} />}
    </div>
  )
}

function Media({ ecoleId, actu }) {
  if (actu.photo || actu.photoLocale) return <Photo ecoleId={ecoleId} actu={actu} />
  if (actu.uploadId) return <VideoLocale uploadId={actu.uploadId} />
  if (actu.video)
    return (
      <div className="actu__media actu__media--video">
        <VideoThumb video={actu.video} />
      </div>
    )
  return null
}

// Le document : un bouton qui l'ouvre comme dans Docs, et ← revient ici.
function Document({ document }) {
  if (!document) return null
  return (
    <button
      type="button"
      className="actu__fichier"
      onClick={() => window.dispatchEvent(new CustomEvent('app-ouvrir-docs', { detail: { id: document.id, retour: true } }))}
    >
      <IconeFichier taille={26} />
      <span>{document.name}</span>
    </button>
  )
}

export function CarteActu({ actu, ecoleId }) {
  const signature = (
    <div className="actu__meta">
      <span>
        <b>{actu.auteur}</b>
        {actu.auteur ? ' · ' : ''}
        {jour(actu.publieeLe ?? new Date())}
      </span>
      {actu.nouveau && <span className="actu__nouveau">Nouveau</span>}
    </div>
  )
  if (actu.niveau === 'brief') {
    return (
      <article className="actu actu--breve">
        <span className="actu__point" aria-hidden="true" />
        <div>
          <p className="actu__texte">{actu.texte || '…'}</p>
          {signature}
        </div>
      </article>
    )
  }
  if (actu.niveau === 'important' && actu.enHaut) {
    return (
      <article className="actu actu--important">
        <div className="actu__drapeau">
          <Alerte />
          Important
        </div>
        <p className="actu__texte">{actu.texte || '…'}</p>
        <Media ecoleId={ecoleId} actu={actu} />
        <Document document={actu.document} />
        {signature}
      </article>
    )
  }
  return (
    // Le texte d'abord, puis la photo ou la vidéo (Seb et les testeurs, 8 novembre).
    <article className="actu actu--normale">
      <div className="actu__corps">
        <p className="actu__texte">{actu.texte || '…'}</p>
      </div>
      <Media ecoleId={ecoleId} actu={actu} />
      <div className="actu__corps">
        <Document document={actu.document} />
        {signature}
      </div>
    </article>
  )
}

function Fil({ actus, ecoleId }) {
  if (!actus.length) return <p className="actus__vide">Pas encore d’actu.</p>
  const enHaut = actus.filter((a) => a.enHaut)
  const autres = actus.filter((a) => !a.enHaut)
  const periodes = autres.map((a) => periode(a.publieeLe))
  return (
    <div className="actus__fil">
      {enHaut.map((a) => (
        <CarteActu key={a.id} actu={a} ecoleId={ecoleId} />
      ))}
      {autres.map((a, i) => {
        const titre = periodes[i] !== periodes[i - 1] ? periodes[i] : null
        return (
          <div key={a.id} className="actus__groupe">
            {titre && <div className="actus__periode">{titre}</div>}
            <CarteActu actu={a} ecoleId={ecoleId} />
          </div>
        )
      })}
      <p className="actus__fin">C’est tout pour le moment.</p>
    </div>
  )
}

function Atelier({ actus, ouvrir, ouverture, changerOuverture }) {
  return (
    <div className="atelier">
      {actus.map((a) => (
        <button key={a.id} type="button" className="atelier__ligne" onClick={() => ouvrir(a)}>
          <span className={`atelier__niveau atelier__niveau--${a.niveau}`} aria-hidden="true" />
          <span className="atelier__corps">
            <span className="atelier__texte">{a.texte}</span>
            <span className="actu__meta">
              <span className={`atelier__etat ${a.publieeLe ? 'is-publiee' : ''}`}>{a.publieeLe ? 'Publiée' : 'Brouillon'}</span>
              <span>
                {LIBELLE[a.niveau]} · {jour(a.publieeLe ?? a.modifieeLe)}
              </span>
            </span>
          </span>
        </button>
      ))}
      <div className="atelier__section">Options</div>
      <div className="atelier__option">
        <span>Ouvrir l’appli sur les actus</span>
        <button
          type="button"
          role="switch"
          aria-checked={ouverture}
          aria-label="Ouvrir l’appli sur les actus"
          className="actus__interrupteur"
          onClick={() => changerOuverture(!ouverture)}
        />
      </div>
    </div>
  )
}

// Choisir un document dans Docs : on descend dans les dossiers et on touche
// le fichier.
function ChoixDocument({ ecoleId, onChoisir, onFermer }) {
  const docs = useState(() => documentsApi(ecoleId))[0]
  const [espaces, setEspaces] = useState([])
  const [espace, setEspace] = useState(null)
  const [dossier, setDossier] = useState(null)
  const [contenu, setContenu] = useState(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => {
    docs.spaces().then(
      (liste) => {
        setEspaces(liste)
        setEspace(liste[0]?.key ?? null)
      },
      (e) => setErreur(e.message),
    )
  }, [docs])
  useEffect(() => {
    if (!espace) return undefined
    let annule = false
    docs.browse(espace, dossier).then(
      (x) => !annule && (setContenu(x), setErreur('')),
      (e) => !annule && setErreur(e.message),
    )
    return () => {
      annule = true
    }
  }, [docs, espace, dossier])

  const fil = contenu?.breadcrumb ?? []
  const remonter = () => (dossier ? setDossier(fil.length > 1 ? fil[fil.length - 2].id : null) : onFermer())
  const elements = contenu?.items ?? []
  return (
    <div className="actus actus--choix" role="dialog" aria-label="Choisir un document">
      <div className="actus__entete">
        <button type="button" className="actus__retour" aria-label="Retour" onClick={remonter}>
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M19 12H5M11 18l-6-6 6-6" />
          </svg>
        </button>
        <strong>{contenu?.folder?.name ?? 'Choisir un document'}</strong>
      </div>
      {!dossier && espaces.length > 1 && (
        <div className="actus__onglets" role="tablist">
          {espaces.map((x) => (
            <button key={x.key} type="button" role="tab" aria-selected={x.key === espace} onClick={() => setEspace(x.key)}>
              {x.label}
            </button>
          ))}
        </div>
      )}
      <div className="choix">
        {erreur && <p className="actus__vide">{erreur}</p>}
        {contenu && !elements.length && <p className="actus__vide">Ce dossier est vide.</p>}
        {elements.map((x) => (
          <button
            key={x.id}
            type="button"
            className="choix__ligne"
            onClick={() => (x.kind === 'folder' ? setDossier(x.id) : onChoisir({ id: x.id, name: x.name }))}
          >
            {x.kind === 'folder' ? (
              <svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                <path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
              </svg>
            ) : (
              <IconeFichier taille={26} />
            )}
            <span>{x.name}</span>
            {x.kind === 'folder' && <span className="choix__chevron">›</span>}
          </button>
        ))}
      </div>
    </div>
  )
}

function Editeur({ actu, auteur, ecoleId, onRetour, onEnregistrer, onSupprimer }) {
  const [brouillon, setBrouillon] = useState(actu)
  const [envoi, setEnvoi] = useState(false)
  const [photoEnvoi, setPhotoEnvoi] = useState(false)
  const [choixDocument, setChoixDocument] = useState(false)
  const champPhoto = useRef(null)
  const champVideo = useRef(null)
  const changer = (champs) => setBrouillon((b) => ({ ...b, ...champs }))
  // Une vidéo choisie mais pas encore publiée : son envoi s'arrête.
  const oublierEnvoi = () => brouillon.uploadId && annulerTeleversement(brouillon.uploadId)
  const sansMedia = { photo: null, photoLocale: null, video: null, uploadId: null }
  const choisirNiveau = (niveau) => {
    if (niveau === 'brief') oublierEnvoi()
    changer({
      niveau,
      // Nouvelle actu : la notification suit le niveau (§4.2).
      ...(actu.id ? {} : { notifier: niveau === 'important' }),
      enHautJusquau: brouillon.enHautJusquau ?? dansJours(7),
      // Une brève n'a ni photo, ni vidéo, ni document (§4.2).
      ...(niveau === 'brief' ? { ...sansMedia, document: null } : {}),
    })
  }
  const vide = !brouillon.texte.trim()
  const publiee = Boolean(actu.publieeLe)
  const aide = NIVEAUX.find((n) => n.cle === brouillon.niveau).aide
  const aPhoto = Boolean(brouillon.photo || brouillon.photoLocale)
  const aVideo = Boolean(brouillon.video || brouillon.uploadId)

  async function choisirPhoto(fichier) {
    if (!fichier) return
    oublierEnvoi()
    changer({ ...sansMedia, photoLocale: URL.createObjectURL(fichier) })
    setPhotoEnvoi(true)
    try {
      changer({ photo: await api.envoyerPhoto(ecoleId, fichier) })
    } catch (e) {
      changer({ photoLocale: null })
      window.alert(e.message)
    } finally {
      setPhotoEnvoi(false)
    }
  }

  async function choisirVideo(fichier) {
    if (!fichier) return
    if (fichier.size > VIDEO_MAX) {
      window.alert(`« ${fichier.name} » est trop grosse : 100 Mo au maximum.`)
      return
    }
    oublierEnvoi()
    try {
      changer({ ...sansMedia, uploadId: await demarrerTeleversement(ecoleId, fichier) })
    } catch (e) {
      window.alert(e.message)
    }
  }

  function basculer(media) {
    if (media === 'photo' && aPhoto) return changer(sansMedia)
    if (media === 'video' && aVideo) {
      oublierEnvoi()
      return changer(sansMedia)
    }
    if (media === 'document') return brouillon.document ? changer({ document: null }) : setChoixDocument(true)
    ;(media === 'photo' ? champPhoto : champVideo).current?.click()
  }

  async function envoyer(publier) {
    setEnvoi(true)
    try {
      let pret = brouillon
      if (brouillon.uploadId) {
        // La vidéo existe dès maintenant ; son envoi finit derrière.
        const video = await finaliserTeleversement(brouillon.uploadId, (id) => api.attacherVideo(ecoleId, id))
        pret = { ...brouillon, video, uploadId: null }
        setBrouillon(pret)
      }
      await onEnregistrer({ ...pret, publier })
    } catch (e) {
      window.alert(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  function retour() {
    oublierEnvoi()
    onRetour()
  }

  if (choixDocument) {
    return (
      <ChoixDocument
        ecoleId={ecoleId}
        onFermer={() => setChoixDocument(false)}
        onChoisir={(document) => {
          changer({ document })
          setChoixDocument(false)
        }}
      />
    )
  }

  return (
    <div className="actus actus--editeur">
      <div className="actus__entete">
        <button type="button" className="actus__retour" aria-label="Retour" onClick={retour}>
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M19 12H5M11 18l-6-6 6-6" />
          </svg>
        </button>
        <strong>{actu.id ? 'Modifier l’actu' : 'Nouvelle actu'}</strong>
      </div>
      <div className="editeur">
        <div className="editeur__niveaux" role="group" aria-label="Niveau">
          {NIVEAUX.map((n) => (
            <button
              key={n.cle}
              type="button"
              className={`editeur__niveau editeur__niveau--${n.cle}`}
              aria-pressed={brouillon.niveau === n.cle}
              onClick={() => choisirNiveau(n.cle)}
            >
              {n.libelle}
            </button>
          ))}
        </div>
        <p className="editeur__aide">{aide}</p>
        <textarea
          id="actu-texte"
          className="editeur__texte"
          aria-label="Texte de l’actu"
          placeholder="Écrivez l’actu…"
          value={brouillon.texte}
          onChange={(e) => changer({ texte: e.target.value })}
        />
        {brouillon.niveau !== 'brief' && (
          <div className="editeur__ajouts">
            <button type="button" aria-pressed={aPhoto} onClick={() => basculer('photo')}>
              <IconePhoto />
              Photo
            </button>
            <button type="button" aria-pressed={aVideo} onClick={() => basculer('video')}>
              <IconeVideo />
              Vidéo
            </button>
            <button type="button" aria-pressed={Boolean(brouillon.document)} onClick={() => basculer('document')}>
              <IconeFichier />
              Document
            </button>
            <input ref={champPhoto} type="file" accept="image/*" hidden onChange={(e) => (choisirPhoto(e.target.files[0]), (e.target.value = ''))} />
            <input ref={champVideo} type="file" accept="video/*" hidden onChange={(e) => (choisirVideo(e.target.files[0]), (e.target.value = ''))} />
          </div>
        )}
        {brouillon.niveau === 'important' && (
          <label className="editeur__ligne" htmlFor="actu-en-haut">
            <span>En haut jusqu’au</span>
            <input
              id="actu-en-haut"
              type="date"
              min={iso(new Date())}
              value={brouillon.enHautJusquau ?? dansJours(7)}
              onChange={(e) => changer({ enHautJusquau: e.target.value || dansJours(7) })}
            />
          </label>
        )}
        <div className="atelier__option">
          <span>Envoyer une notification</span>
          <button
            type="button"
            role="switch"
            aria-checked={brouillon.notifier}
            aria-label="Envoyer une notification"
            className="actus__interrupteur"
            onClick={() => changer({ notifier: !brouillon.notifier })}
          />
        </div>
        <div className="actus__periode">Ce que verront les autres</div>
        <div className="editeur__apercu">
          <CarteActu
            ecoleId={ecoleId}
            actu={{
              ...brouillon,
              enHaut: brouillon.niveau === 'important',
              auteur: actu.auteur || auteur,
              publieeLe: actu.publieeLe,
              nouveau: true,
            }}
          />
        </div>
        {actu.id && (
          <button type="button" className="editeur__supprimer" onClick={() => onSupprimer(actu)}>
            Supprimer cette actu
          </button>
        )}
      </div>
      <div className="actus__barre">
        <button type="button" className="btn btn--secondary actus__brouillon" disabled={vide || envoi || photoEnvoi} onClick={() => envoyer(false)}>
          Brouillon
        </button>
        <button type="button" className="btn btn--primary actus__principal" disabled={vide || envoi || photoEnvoi} onClick={() => envoyer(true)}>
          {publiee ? 'Enregistrer' : 'Publier'}
        </button>
      </div>
    </div>
  )
}

export default function Actus({ ecoleId, prenom }) {
  const [fil, setFil] = useState(null) // { peutPublier, actus }
  const [atelier, setAtelier] = useState([])
  const [onglet, setOnglet] = useState('apercu')
  const [ouverture, setOuverture] = useState(true)
  const [edite, setEdite] = useState(null) // l'actu ouverte dans l'éditeur
  const [caches, setCaches] = useState(new Set()) // supprimées, Annuler possible
  const [toast, setToast] = useState(null) // { texte, annuler }
  const [erreur, setErreur] = useState('')
  const minuteur = useRef(null)

  const charger = useCallback(async () => {
    try {
      const f = await api.lireActus(ecoleId)
      setFil(f)
      if (f.peutPublier) {
        const [a, o] = await Promise.all([api.lireAtelier(ecoleId), api.ouvrirSurLesActus(ecoleId)])
        setAtelier(a)
        setOuverture(o)
      }
      setErreur('')
    } catch (e) {
      setErreur(e.message)
    }
  }, [ecoleId])

  useEffect(() => {
    charger()
  }, [charger])
  useEffect(() => () => clearTimeout(minuteur.current), [])

  const montrer = useCallback((texte, annuler) => {
    clearTimeout(minuteur.current)
    setToast({ texte, annuler })
    minuteur.current = setTimeout(() => setToast(null), annuler ? ANNULER_MS : 3000)
  }, [])

  async function enregistrer(brouillon) {
    try {
      const actu = await api.enregistrer(ecoleId, brouillon)
      const vientDePublier = brouillon.publier && !edite.publieeLe
      setEdite(null)
      await charger()
      if (vientDePublier) {
        setOnglet('apercu')
        montrer('Actu publiée', async () => {
          await api.depublier(ecoleId, actu.id)
          charger()
        })
      } else {
        montrer(brouillon.publier ? 'Actu enregistrée' : 'Gardée en brouillon')
      }
    } catch (e) {
      montrer(e.message)
    }
  }

  // Supprimer : l'actu disparaît tout de suite et part vraiment au bout de
  // 10 s, comme dans Sparring.
  function supprimer(actu) {
    setEdite(null)
    setCaches((c) => new Set([...c, actu.id]))
    const retard = setTimeout(() => {
      api.supprimer(ecoleId, actu.id).then(charger, (e) => montrer(e.message))
    }, ANNULER_MS)
    montrer('Actu supprimée', () => {
      clearTimeout(retard)
      setCaches((c) => {
        const n = new Set(c)
        n.delete(actu.id)
        return n
      })
    })
  }

  async function changerOuverture(valeur) {
    setOuverture(valeur)
    try {
      await api.changerOuverture(ecoleId, valeur)
      montrer(valeur ? 'L’appli s’ouvrira sur les actus' : 'L’appli s’ouvrira sur le dernier onglet')
    } catch (e) {
      setOuverture(!valeur)
      montrer(e.message)
    }
  }

  const toastEl = toast && (
    <div className={`actus__toast ${edite || onglet === 'atelier' ? 'actus__toast--haut' : ''}`} role="status">
      <span>{toast.texte}</span>
      {toast.annuler && (
        <button
          type="button"
          onClick={() => {
            clearTimeout(minuteur.current)
            setToast(null)
            toast.annuler()
          }}
        >
          Annuler
        </button>
      )}
    </div>
  )

  if (edite) {
    return (
      <>
        <Editeur actu={edite} auteur={prenom} ecoleId={ecoleId} onRetour={() => setEdite(null)} onEnregistrer={enregistrer} onSupprimer={supprimer} />
        {toastEl}
      </>
    )
  }

  if (!fil) return <div className="actus">{erreur && <p className="actus__vide">{erreur}</p>}</div>
  const visibles = (liste) => liste.filter((a) => !caches.has(a.id))
  const vueAtelier = fil.peutPublier && onglet === 'atelier'

  return (
    <div className={`actus ${vueAtelier ? 'actus--avec-barre' : ''}`}>
      {fil.peutPublier && (
        <div className="actus__onglets" role="tablist">
          {[
            // Libellés de Seb (8 novembre) : Édition | Visualisation.
            ['atelier', 'Édition'],
            ['apercu', 'Visualisation'],
          ].map(([cle, libelle]) => (
            <button key={cle} type="button" role="tab" aria-selected={onglet === cle} onClick={() => setOnglet(cle)}>
              {libelle}
            </button>
          ))}
        </div>
      )}
      {vueAtelier ? (
        <Atelier actus={visibles(atelier)} ouvrir={setEdite} ouverture={ouverture} changerOuverture={changerOuverture} />
      ) : (
        <Fil actus={visibles(fil.actus)} ecoleId={ecoleId} />
      )}
      {vueAtelier && (
        <div className="actus__barre">
          <button
            type="button"
            className="btn btn--primary actus__principal"
            onClick={() => setEdite({ id: null, niveau: 'normal', texte: '', enHautJusquau: dansJours(7), notifier: false, publieeLe: null, photo: null, video: null, document: null })}
          >
            Nouvelle actu
          </button>
        </div>
      )}
      {toastEl}
    </div>
  )
}
