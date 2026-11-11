import { useCallback, useEffect, useRef, useState } from 'react'
import { documentsApi } from '../../api/documents.js'
import Icon from '../../components/Icon.jsx'
import MenuEntete from '../../components/MenuEntete.jsx'
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
const MEDIA_MAX = 10 // photos et vidéos par actu, comme Instagram (§3.3)
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
const IconeLien = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M10 14a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1" />
    <path d="M14 10a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1" />
  </svg>
)
const IconeFichier = ({ taille = 20 }) => (
  <svg viewBox="0 0 24 24" width={taille} height={taille} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
  </svg>
)

// Une photo de l'actu : lue avec la session, ou la copie locale juste
// choisie dans l'éditeur.
function Photo({ ecoleId, actuId, element }) {
  const [url, setUrl] = useState(null)
  const { photo, photoLocale } = element
  useEffect(() => {
    if (photoLocale || !actuId || !photo) return undefined
    let annule = false
    api.lirePhoto(ecoleId, actuId, photo).then((u) => !annule && setUrl(u), () => {})
    return () => {
      annule = true
    }
  }, [ecoleId, actuId, photo, photoLocale])
  const src = photoLocale || url
  return <div className="actu__media">{src && <img src={src} alt="" />}</div>
}

// La vidéo pas encore envoyée, lue sur ce téléphone pendant l'envoi.
function VideoLocale({ uploadId }) {
  const etat = useProgressionTeleversement(uploadId)
  if (!etat) return <div className="actu__media" />
  const pourcentage = etat.octetsTotal ? Math.round((etat.octetsEnvoyes / etat.octetsTotal) * 100) : 0
  return (
    <div className="actu__media">
      <video src={etat.previewUrl} controls playsInline />
      {!etat.complet && <div className="actu__envoi" style={{ width: `${pourcentage}%` }} />}
    </div>
  )
}

// Un lien YouTube se lit dans la case (§3.3, Seb 9 novembre) : d'abord son
// image avec ▶, la vidéo ne se charge qu'au toucher (le carrousel glisse
// encore du doigt tant qu'elle ne joue pas).
const YOUTUBE = /^https?:\/\/(?:www\.|m\.)?(?:youtube\.com\/(?:watch\?(?:.*&)?v=|shorts\/|embed\/|live\/)|youtu\.be\/)([\w-]{11})/

function YouTube({ ecoleId, actuId, element, id }) {
  const [lecture, setLecture] = useState(false)
  if (lecture) {
    return (
      <div className="actu__media actu__media--youtube">
        <iframe
          src={`https://www.youtube-nocookie.com/embed/${id}?autoplay=1&playsinline=1`}
          title={element.titre || 'YouTube'}
          allow="autoplay; encrypted-media; picture-in-picture; fullscreen"
          allowFullScreen
        />
      </div>
    )
  }
  return (
    <button type="button" className="actu__youtube" aria-label={`Lire « ${element.titre || 'la vidéo'} »`} onClick={() => setLecture(true)}>
      {element.photo || element.photoLocale ? (
        <Photo ecoleId={ecoleId} actuId={actuId} element={element} />
      ) : (
        <div className="actu__media">
          <img src={`https://i.ytimg.com/vi/${id}/hqdefault.jpg`} alt="" />
        </div>
      )}
      <span className="actu__youtube-play" aria-hidden="true">▶</span>
    </button>
  )
}

// Un autre lien : l'image du site, son titre, et « Ouvrir le lien ».
function Lien({ ecoleId, actuId, element }) {
  const id = element.lien.match(YOUTUBE)?.[1]
  if (id) return <YouTube ecoleId={ecoleId} actuId={actuId} element={element} id={id} />
  let site = element.lien
  try {
    site = new URL(element.lien).hostname.replace(/^www\./, '')
  } catch {
    // on garde le lien tel quel
  }
  return (
    <div className="actu__lien">
      {(element.photo || element.photoLocale) && <Photo ecoleId={ecoleId} actuId={actuId} element={element} />}
      <div className="actu__lien-texte">
        {element.titre && <strong>{element.titre}</strong>}
        <span>{site}</span>
        <a className="actu__lien-ouvrir" href={element.lien} target="_blank" rel="noopener noreferrer">
          Ouvrir le lien
        </a>
      </div>
    </div>
  )
}

function Element({ ecoleId, actuId, element }) {
  if (element.lien) return <Lien ecoleId={ecoleId} actuId={actuId} element={element} />
  if (element.photo || element.photoLocale) return <Photo ecoleId={ecoleId} actuId={actuId} element={element} />
  if (element.uploadId) return <VideoLocale uploadId={element.uploadId} />
  return (
    <div className="actu__media actu__media--video">
      <VideoThumb video={element.video} />
    </div>
  )
}

// Les photos et vidéos de l'actu ; à plusieurs, un carrousel qu'on fait
// glisser du doigt, avec des points toujours visibles, comme sur Instagram (§3.3).
function Media({ ecoleId, actu }) {
  const [rang, setRang] = useState(0)
  const media = actu.media ?? []
  if (!media.length) return null
  if (media.length === 1) return <Element ecoleId={ecoleId} actuId={actu.id} element={media[0]} />
  return (
    <div className="carrousel">
      <div
        className="carrousel__piste"
        onScroll={(e) => setRang(Math.round(e.currentTarget.scrollLeft / e.currentTarget.clientWidth))}
      >
        {media.map((element, i) => (
          <div key={element.cle ?? element.photo ?? element.video?.id ?? i} className="carrousel__case">
            <Element ecoleId={ecoleId} actuId={actu.id} element={element} />
          </div>
        ))}
      </div>
      <div className="carrousel__points" aria-label={`${Math.min(rang, media.length - 1) + 1} sur ${media.length}`}>
        {media.map((element, i) => (
          <span key={i} className={i === rang ? 'carrousel__point carrousel__point--actif' : 'carrousel__point'} />
        ))}
      </div>
    </div>
  )
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

// mediaEnHaut : réglage « En haut de chaque actu : Photo, vidéo » (Seb, 9 novembre).
export function CarteActu({ actu, ecoleId, mediaEnHaut = false }) {
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
  // Une actu peut n'être qu'une photo, une vidéo, un lien ou un document
  // (Seb, 10 novembre) : pas de ligne de texte vide. « … » seulement pour
  // une actu encore vide dans l'éditeur.
  const sansTexte = !actu.texte && (actu.media?.length > 0 || Boolean(actu.document))
  const texte = sansTexte ? null : <p className="actu__texte">{actu.texte || '…'}</p>
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
        {mediaEnHaut && <Media ecoleId={ecoleId} actu={actu} />}
        {texte}
        {!mediaEnHaut && <Media ecoleId={ecoleId} actu={actu} />}
        <Document document={actu.document} />
        {signature}
      </article>
    )
  }
  return (
    // Par défaut le texte d'abord, puis la photo ou la vidéo (Seb et les testeurs, 8 novembre).
    <article className="actu actu--normale">
      {mediaEnHaut && <Media ecoleId={ecoleId} actu={actu} />}
      {texte && <div className="actu__corps">{texte}</div>}
      {!mediaEnHaut && <Media ecoleId={ecoleId} actu={actu} />}
      <div className="actu__corps">
        <Document document={actu.document} />
        {signature}
      </div>
    </article>
  )
}

function Fil({ actus, ecoleId, mediaEnHaut }) {
  if (!actus.length) return <p className="actus__vide">Pas encore d’actu.</p>
  const enHaut = actus.filter((a) => a.enHaut)
  const autres = actus.filter((a) => !a.enHaut)
  const periodes = autres.map((a) => periode(a.publieeLe))
  return (
    <div className="actus__fil">
      {enHaut.map((a) => (
        <CarteActu key={a.id} actu={a} ecoleId={ecoleId} mediaEnHaut={mediaEnHaut} />
      ))}
      {autres.map((a, i) => {
        const titre = periodes[i] !== periodes[i - 1] ? periodes[i] : null
        return (
          <div key={a.id} className="actus__groupe">
            {titre && <div className="actus__periode">{titre}</div>}
            <CarteActu actu={a} ecoleId={ecoleId} mediaEnHaut={mediaEnHaut} />
          </div>
        )
      })}
      <p className="actus__fin">C’est tout pour le moment.</p>
    </div>
  )
}

function Atelier({ ecoleId, actus, ouvrir, ouverture, changerOuverture, mediaEnHaut, changerMediaEnHaut, pourTous, changerPourTous, parametres, changerParametres }) {
  return (
    <div className="atelier">
      {actus.map((a) => (
        <button key={a.id} type="button" className="atelier__ligne" onClick={() => ouvrir(a)}>
          <span className={`atelier__niveau atelier__niveau--${a.niveau}`} aria-hidden="true" />
          <span className="atelier__corps">
            <span className="atelier__texte">{a.texte || 'Actu sans texte'}</span>
            <span className="actu__meta">
              <span className={`atelier__etat ${a.publieeLe ? 'is-publiee' : ''}`}>{a.publieeLe ? 'Publiée' : 'Brouillon'}</span>
              <span>
                {LIBELLE[a.niveau]} · {jour(a.publieeLe ?? a.modifieeLe)}
              </span>
            </span>
          </span>
        </button>
      ))}
      <ParametresEdition
        ecoleId={ecoleId}
        ouverture={ouverture}
        changerOuverture={changerOuverture}
        mediaEnHaut={mediaEnHaut}
        changerMediaEnHaut={changerMediaEnHaut}
        pourTous={pourTous}
        changerPourTous={changerPourTous}
        ouvert={parametres}
        setOuvert={changerParametres}
      />
    </div>
  )
}

// « Paramètres d'édition » : repliés par défaut, on les déroule au besoin
// (Seb, 8 novembre) ; aussi depuis le menu ⋯ (Seb, 9 novembre).
function ParametresEdition({ ecoleId, ouverture, changerOuverture, mediaEnHaut, changerMediaEnHaut, pourTous, changerPourTous, ouvert, setOuvert }) {
  return (
    <div className="parametres" id="actus-parametres">
      {/* Même présentation que les volets d'Admin › École (Seb, 9 novembre). */}
      <h3 className="section-label parametres__titre">
        <button type="button" className="section-label__depliant" aria-expanded={ouvert} onClick={() => setOuvert(!ouvert)}>
          <Icon name={ouvert ? 'chevronDown' : 'chevronRight'} size={14} />
          Paramètres d’édition des actus
        </button>
      </h3>
      {ouvert && (
        <>
          <h4 className="section-label perso__sous-partie">En haut de chaque actu</h4>
          <div className="editeur__niveaux parametres__choix" role="group" aria-label="En haut de chaque actu">
            {[
              [false, 'Texte'],
              [true, 'Photo, vidéo'],
            ].map(([valeur, libelle]) => (
              <button
                key={libelle}
                type="button"
                className="editeur__niveau editeur__niveau--normal"
                aria-pressed={mediaEnHaut === valeur}
                onClick={() => mediaEnHaut !== valeur && changerMediaEnHaut(valeur)}
              >
                {libelle}
              </button>
            ))}
          </div>
          <h4 className="section-label perso__sous-partie">Ouverture de l’appli</h4>
          <div className="atelier__option">
            <span>L’appli affiche toujours les actus à son ouverture</span>
            <button
              type="button"
              role="switch"
              aria-checked={ouverture}
              aria-label="L’appli affiche toujours les actus à son ouverture"
              className="actus__interrupteur"
              onClick={() => changerOuverture(!ouverture)}
            />
          </div>
          <p className="editeur__aide">Sinon, elle affiche le dernier onglet ouvert.</p>
          <h4 className="section-label perso__sous-partie">Visibilité</h4>
          <div className="atelier__option">
            <span>Les actus sont visibles par tout le monde</span>
            <button
              type="button"
              role="switch"
              aria-checked={pourTous}
              aria-label="Les actus sont visibles par tout le monde"
              className="actus__interrupteur"
              onClick={() => changerPourTous(!pourTous)}
            />
          </div>
          <p className="editeur__aide">Sinon, seuls ceux qui publient les voient.</p>
          <h4 className="section-label perso__sous-partie">Instagram</h4>
          <Instagram ecoleId={ecoleId} />
        </>
      )}
    </div>
  )
}

// Relier un compte Instagram (§6 bis) : ses nouveaux posts arrivent dans
// les actus, toutes les 5 minutes.
function Instagram({ ecoleId }) {
  const [etat, setEtat] = useState(null)
  const [cle, setCle] = useState('')
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState(() => {
    const message = RETOURS_INSTAGRAM[retourInstagram] ?? ''
    oublierRetourInstagram() // montré une fois
    return message
  })
  const [hashtag, setHashtag] = useState('')
  const [choix, setChoix] = useState('tous') // tous | hashtag | un_par_un
  useEffect(() => {
    api.lireInstagram(ecoleId).then(setEtat, (e) => setErreur(e.message))
    api.lireTriInstagram(ecoleId).then((t) => {
      setHashtag(t.hashtag)
      setChoix(!t.publier ? 'un_par_un' : t.hashtag ? 'hashtag' : 'tous')
    }, () => {})
  }, [ecoleId])

  async function changerTri(changement) {
    try {
      setHashtag((await api.changerTriInstagram(ecoleId, changement)).hashtag)
    } catch (e) {
      setErreur(e.message)
    }
  }

  // Seb, 11 novembre (maquette spec/maquettes/actualites-instagram.html) :
  // qui relie choisit quels posts arrivent, une question à trois réponses
  // (réglable avant de relier). Côté serveur : un hashtag et « publier ».
  function choisir(c) {
    setChoix(c)
    if (c === 'tous') changerTri({ instagram_hashtag: '', instagram_publish: true })
    if (c === 'hashtag') changerTri({ instagram_hashtag: hashtag, instagram_publish: true })
    if (c === 'un_par_un') changerTri({ instagram_hashtag: '', instagram_publish: false })
  }
  const CHOIX = [
    ['tous', 'Tous mes posts', 'Chaque nouveau post arrive dans les actus, tout de suite.'],
    ['hashtag', 'Seulement ceux avec un hashtag', 'Seuls les posts où vous écrivez ce hashtag arrivent, tout de suite.'],
    ['un_par_un', 'Je les choisis un par un', 'Chaque post arrive en brouillon ici. Vous touchez « Publier » pour ceux que vous voulez.'],
  ]
  const champHashtag = (
    <fieldset className="parametres__tri">
      <legend>Quels posts Instagram mettre dans les actus ?</legend>
      {CHOIX.map(([c, titre, aide]) => (
        <label key={c} className="parametres__tri-choix" aria-checked={choix === c}>
          <input type="radio" name="tri-instagram" checked={choix === c} onChange={() => choisir(c)} />
          <span>
            <b>{titre}</b>
            <small>{aide}</small>
            {c === 'hashtag' && choix === 'hashtag' && (
              <span className="parametres__hashtag">
                #
                <input
                  className="editeur__texte"
                  aria-label="Hashtag"
                  placeholder="contretemps"
                  value={hashtag}
                  onChange={(e) => setHashtag(e.target.value)}
                  onBlur={() => changerTri({ instagram_hashtag: hashtag, instagram_publish: true })}
                />
              </span>
            )}
          </span>
        </label>
      ))}
    </fieldset>
  )

  async function agir(action) {
    setEnvoi(true)
    setErreur('')
    try {
      setEtat(await action())
      setCle('')
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  // Instagram, puis retour ici (?instagram=ok).
  async function seConnecter() {
    setEnvoi(true)
    try {
      window.location.assign(await api.connexionInstagram(ecoleId))
    } catch (e) {
      setErreur(e.message)
      setEnvoi(false)
    }
  }

  if (!etat) return erreur ? <p className="parametres__erreur">{erreur}</p> : null
  return (
    <div className="atelier__option parametres__instagram">
      {etat.relie ? (
        <>
          <p>
            Relié à <b>@{etat.compte}</b>. Ses nouveaux posts arrivent dans les actus en 5 minutes au plus.
          </p>
          {champHashtag}
          {etat.erreur && <p className="parametres__erreur">{etat.erreur}</p>}
          <button type="button" className="btn btn--secondary" disabled={envoi} onClick={() => agir(() => api.delierInstagram(ecoleId))}>
            Délier
          </button>
        </>
      ) : etat.peutSeConnecter ? (
        <>
          <p>Reliez le compte Instagram (compte professionnel) : ses nouveaux posts arriveront dans les actus.</p>
          {champHashtag}
          {erreur && <p className="parametres__erreur">{erreur}</p>}
          <button type="button" className="btn btn--secondary" disabled={envoi} onClick={seConnecter}>
            Se connecter avec Instagram
          </button>
        </>
      ) : (
        <>
          <p>Collez la clé d’accès du compte Instagram (compte professionnel) : ses nouveaux posts arriveront dans les actus.</p>
          <input
            className="editeur__texte parametres__cle"
            aria-label="Clé d’accès Instagram"
            placeholder="Clé d’accès"
            value={cle}
            onChange={(e) => setCle(e.target.value)}
          />
          {erreur && <p className="parametres__erreur">{erreur}</p>}
          <button
            type="button"
            className="btn btn--secondary"
            disabled={envoi || cle.trim().length < 20}
            onClick={() => agir(() => api.relierInstagram(ecoleId, cle.trim()))}
          >
            Relier
          </button>
        </>
      )}
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

function Editeur({ actu, auteur, ecoleId, mediaEnHaut, onRetour, onEnregistrer, onSupprimer }) {
  // Chaque photo ou vidéo a une clé, pour la retirer.
  const [brouillon, setBrouillon] = useState(() => ({ ...actu, media: actu.media.map((m, i) => ({ ...m, cle: `e${i}` })) }))
  const [envoi, setEnvoi] = useState(false)
  const [photoEnvoi, setPhotoEnvoi] = useState(0) // photos en cours d'envoi
  const numero = useRef(0)
  const [choixDocument, setChoixDocument] = useState(false)
  const champPhoto = useRef(null)
  const champVideo = useRef(null)
  const [lien, setLien] = useState(null) // le lien en train d'être collé, ou null
  const [lienEnvoi, setLienEnvoi] = useState(false)
  const changer = (champs) => setBrouillon((b) => ({ ...b, ...champs }))
  const ajouter = (element) => setBrouillon((b) => ({ ...b, media: [...b.media, element] }))
  const remplacer = (cle, champs) =>
    setBrouillon((b) => ({ ...b, media: b.media.map((m) => (m.cle === cle ? { ...m, ...champs } : m)) }))
  const enlever = (cle) => setBrouillon((b) => ({ ...b, media: b.media.filter((m) => m.cle !== cle) }))
  // Une vidéo choisie mais pas encore publiée : son envoi s'arrête.
  const oublierEnvois = (media = brouillon.media) => media.forEach((m) => m.uploadId && annulerTeleversement(m.uploadId))
  const choisirNiveau = (niveau) => {
    if (niveau === 'brief') oublierEnvois()
    changer({
      niveau,
      // Nouvelle actu : la notification suit le niveau (§4.2).
      ...(actu.id ? {} : { notifier: niveau === 'important' }),
      enHautJusquau: brouillon.enHautJusquau ?? dansJours(7),
      // Une brève n'a ni photo, ni vidéo, ni document (§4.2).
      ...(niveau === 'brief' ? { media: [], document: null } : {}),
    })
  }
  // Le texte est facultatif dès qu'il y a une photo, une vidéo, un lien ou
  // un document (Seb, 10 novembre) ; une Brève n'est que du texte.
  const vide =
    !brouillon.texte.trim() && (brouillon.niveau === 'brief' || (!brouillon.media.length && !brouillon.document))
  const publiee = Boolean(actu.publieeLe)
  const aide = NIVEAUX.find((n) => n.cle === brouillon.niveau).aide
  const place = MEDIA_MAX - brouillon.media.length

  async function choisirPhotos(fichiers) {
    const choisies = [...fichiers].slice(0, place)
    if (fichiers.length > place) window.alert(`${MEDIA_MAX} photos ou vidéos au plus par actu.`)
    if (!choisies.length) return
    setPhotoEnvoi((n) => n + choisies.length)
    await Promise.all(
      choisies.map(async (fichier) => {
        const cle = `p${++numero.current}`
        ajouter({ cle, photoLocale: URL.createObjectURL(fichier) })
        try {
          remplacer(cle, { photo: await api.envoyerPhoto(ecoleId, fichier) })
        } catch (e) {
          enlever(cle)
          window.alert(e.message)
        } finally {
          setPhotoEnvoi((n) => n - 1)
        }
      }),
    )
  }

  async function choisirVideo(fichier) {
    if (!fichier) return
    if (fichier.size > VIDEO_MAX) {
      window.alert(`« ${fichier.name} » est trop grosse : 100 Mo au maximum.`)
      return
    }
    try {
      ajouter({ cle: `v${++numero.current}`, uploadId: await demarrerTeleversement(ecoleId, fichier) })
    } catch (e) {
      window.alert(e.message)
    }
  }

  function retirer(element) {
    oublierEnvois([element])
    enlever(element.cle)
  }

  async function ajouterLien() {
    const url = lien.trim()
    if (!url) return
    setLienEnvoi(true)
    try {
      ajouter({ cle: `l${++numero.current}`, ...(await api.ajouterLien(ecoleId, /^https?:\/\//i.test(url) ? url : `https://${url}`)) })
      setLien(null)
    } catch (e) {
      window.alert(e.message)
    } finally {
      setLienEnvoi(false)
    }
  }

  function basculer(ajout) {
    if (ajout === 'document') return brouillon.document ? changer({ document: null }) : setChoixDocument(true)
    if (place <= 0) return window.alert(`${MEDIA_MAX} photos ou vidéos au plus par actu.`)
    if (ajout === 'lien') return setLien((l) => (l === null ? '' : null))
    ;(ajout === 'photo' ? champPhoto : champVideo).current?.click()
  }

  async function envoyer(publier) {
    setEnvoi(true)
    try {
      // Les vidéos existent dès maintenant ; leur envoi finit derrière.
      const media = await Promise.all(
        brouillon.media.map(async (m) =>
          m.uploadId
            ? { cle: m.cle, video: await finaliserTeleversement(m.uploadId, (id) => api.attacherVideo(ecoleId, id)) }
            : m,
        ),
      )
      const pret = { ...brouillon, media }
      setBrouillon(pret)
      await onEnregistrer({ ...pret, publier })
    } catch (e) {
      window.alert(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  function retour() {
    oublierEnvois()
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
            <button type="button" onClick={() => basculer('photo')}>
              <IconePhoto />
              Photo
            </button>
            <button type="button" onClick={() => basculer('video')}>
              <IconeVideo />
              Vidéo
            </button>
            <button type="button" aria-pressed={lien !== null} onClick={() => basculer('lien')}>
              <IconeLien />
              Lien
            </button>
            <button type="button" aria-pressed={Boolean(brouillon.document)} onClick={() => basculer('document')}>
              <IconeFichier />
              Document
            </button>
            <input ref={champPhoto} type="file" accept="image/*" multiple hidden onChange={(e) => (choisirPhotos(e.target.files), (e.target.value = ''))} />
            <input ref={champVideo} type="file" accept="video/*" hidden onChange={(e) => (choisirVideo(e.target.files[0]), (e.target.value = ''))} />
          </div>
        )}
        {brouillon.niveau !== 'brief' && lien !== null && (
          <form
            className="editeur__lien"
            onSubmit={(e) => {
              e.preventDefault()
              ajouterLien()
            }}
          >
            <input
              type="text"
              inputMode="url"
              autoCapitalize="off"
              autoCorrect="off"
              aria-label="Lien"
              placeholder="Collez le lien (YouTube ou autre site)"
              value={lien}
              autoFocus
              onChange={(e) => setLien(e.target.value)}
            />
            <button type="submit" disabled={lienEnvoi || !lien.trim()}>
              {lienEnvoi ? '…' : 'Ajouter'}
            </button>
          </form>
        )}
        {brouillon.media.length > 0 && (
          <ul className="editeur__medias" aria-label="Photos et vidéos">
            {brouillon.media.map((element) => (
              <li key={element.cle}>
                <Element ecoleId={ecoleId} actuId={actu.id} element={element} />
                <button type="button" aria-label="Retirer" onClick={() => retirer(element)}>
                  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
                    <path d="M6 6l12 12M18 6L6 18" />
                  </svg>
                </button>
              </li>
            ))}
          </ul>
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
            mediaEnHaut={mediaEnHaut}
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
        <button type="button" className="btn btn--secondary actus__brouillon" disabled={vide || envoi || photoEnvoi > 0} onClick={() => envoyer(false)}>
          Brouillon
        </button>
        <button type="button" className="btn btn--primary actus__principal" disabled={vide || envoi || photoEnvoi > 0} onClick={() => envoyer(true)}>
          {publiee ? 'Enregistrer' : 'Publier'}
        </button>
      </div>
    </div>
  )
}

// Retour de « Se connecter avec Instagram » (?instagram=ok|annule|erreur,
// voir news/instagram.py) : retiré de l'adresse et gardé pour la session,
// au cas où l'appli se recharge aussitôt (nouvelle version), montré une fois.
const RETOURS_INSTAGRAM = {
  annule: 'Connexion à Instagram annulée.',
  erreur: 'La connexion à Instagram n’a pas abouti : le compte est-il bien professionnel et ajouté comme testeur ? Recommencez.',
}
let retourInstagram = (() => {
  try {
    const params = new URLSearchParams(window.location.search)
    const retour = params.get('instagram')
    if (retour) {
      params.delete('instagram')
      const reste = params.toString()
      window.history.replaceState(null, '', window.location.pathname + (reste ? `?${reste}` : '') + window.location.hash)
      sessionStorage.setItem('retour-instagram', retour)
    }
    return sessionStorage.getItem('retour-instagram')
  } catch {
    return null
  }
})()
function oublierRetourInstagram() {
  retourInstagram = null
  try {
    sessionStorage.removeItem('retour-instagram')
  } catch {
    // rien à oublier
  }
}

export default function Actus({ ecoleId, prenom }) {
  const [fil, setFil] = useState(null) // { peutPublier, actus }
  const [atelier, setAtelier] = useState([])
  const [onglet, setOnglet] = useState(retourInstagram ? 'atelier' : 'apercu')
  const [ouverture, setOuverture] = useState(true)
  const [pourTous, setPourTous] = useState(true) // « visibles par tout le monde »
  // Paramètres d'édition dépliés ; au retour d'Instagram, ils s'ouvrent sur le résultat.
  const [parametres, setParametres] = useState(Boolean(retourInstagram))
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
        const [a, r] = await Promise.all([api.lireAtelier(ecoleId), api.lireReglages(ecoleId)])
        setAtelier(a)
        setOuverture(r.ouvrir)
        setPourTous(r.pourTous)
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

  async function changerMediaEnHaut(valeur) {
    setFil((f) => ({ ...f, mediaEnHaut: valeur }))
    try {
      await api.changerMediaEnHaut(ecoleId, valeur)
      montrer(valeur ? 'Photos et vidéos en haut de chaque actu' : 'Texte en haut de chaque actu')
    } catch (e) {
      setFil((f) => ({ ...f, mediaEnHaut: !valeur }))
      montrer(e.message)
    }
  }

  async function changerOuverture(valeur) {
    setOuverture(valeur)
    try {
      await api.changerOuverture(ecoleId, valeur)
      montrer(valeur ? 'L’appli affichera toujours les actus à son ouverture' : 'L’appli affichera le dernier onglet ouvert')
    } catch (e) {
      setOuverture(!valeur)
      montrer(e.message)
    }
  }

  async function changerPourTous(valeur) {
    setPourTous(valeur)
    try {
      await api.changerPourTous(ecoleId, valeur)
      montrer(valeur ? 'Les actus sont visibles par tout le monde' : 'Seuls ceux qui publient voient les actus')
    } catch (e) {
      setPourTous(!valeur)
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

  function montrerParametres() {
    setOnglet('atelier')
    setParametres(true)
    // Une fois affichés, on descend jusqu'à eux.
    setTimeout(() => document.getElementById('actus-parametres')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  if (edite) {
    return (
      <>
        <Editeur actu={edite} auteur={prenom} ecoleId={ecoleId} mediaEnHaut={fil?.mediaEnHaut} onRetour={() => setEdite(null)} onEnregistrer={enregistrer} onSupprimer={supprimer} />
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
        // Menu ⋯ : les mêmes Paramètres d'édition qu'en bas de l'onglet Édition.
        <MenuEntete label="Actions des actus" actions={[{ label: 'Paramètres d’édition des actus', icon: 'edit', onClick: montrerParametres }]} />
      )}
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
        <Atelier
          ecoleId={ecoleId}
          actus={visibles(atelier)}
          ouvrir={setEdite}
          ouverture={ouverture}
          changerOuverture={changerOuverture}
          mediaEnHaut={fil.mediaEnHaut}
          changerMediaEnHaut={changerMediaEnHaut}
          pourTous={pourTous}
          changerPourTous={changerPourTous}
          parametres={parametres}
          changerParametres={setParametres}
        />
      ) : (
        <Fil actus={visibles(fil.actus)} ecoleId={ecoleId} mediaEnHaut={fil.mediaEnHaut} />
      )}
      {vueAtelier && (
        <div className="actus__barre">
          <button
            type="button"
            className="btn btn--primary actus__principal"
            onClick={() => setEdite({ id: null, niveau: 'normal', texte: '', enHautJusquau: dansJours(7), notifier: false, publieeLe: null, media: [], document: null })}
          >
            Nouvelle actu
          </button>
        </div>
      )}
      {toastEl}
    </div>
  )
}
