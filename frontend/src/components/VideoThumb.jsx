import { useState } from 'react'
import { useProgressionVideo } from '../utils/videoUploads.js'
import Icon from './Icon.jsx'

// Vignette vidéo réutilisée par l'onglet Vidéo (VideoScreen.jsx) et le
// détail d'une chorégraphie (ChoregraphieDetailScreen.jsx). Prend le
// `video` entier (pas juste url/poster/titre/duree) : `statut` décide si
// on montre l'aperçu local pendant l'envoi (voir plus bas) ou la vignette
// normale.
//
// Tant que la lecture n'a pas été demandée (vidéo déjà en ligne), AUCUN
// <video> n'est monté — juste une simple <img> (le `poster`) : s'affiche
// instantanément, comme une vignette YouTube. Monter directement un
// <video poster preload> (essayé d'abord) laissait apparaître, sur mobile
// (Chrome/Brave/Samsung Internet Android testés), une brève animation de
// chargement autour du bouton play avant que le poster ne s'affiche — et,
// tant que la vidéo n'était pas assez initialisée, les contrôles natifs
// n'incluaient pas le bouton plein écran (présent une fois la lecture
// réellement commencée, comme dans Chorégraphie où l'utilisateur avait
// déjà tapé play). Ne créer le <video> qu'au clic règle les deux à la
// fois : la vignette est immédiate, et une fois monté avec `autoPlay`, le
// navigateur a tout de suite les infos nécessaires pour afficher les
// contrôles complets, plein écran inclus.
export default function VideoThumb({ video }) {
  const [lecture, setLecture] = useState(false)
  const enCours = video.statut === 'en_cours'
  const progression = useProgressionVideo(enCours ? video.id : null)

  // Fichier pas encore complet (voir utils/videoUploads.js) : le
  // navigateur a déjà les octets du fichier choisi/filmé EN LOCAL —
  // jouable tout de suite, sans dépendre du serveur (demande utilisateur
  // explicite : "tu peux voir la vidéo" pendant l'envoi, "ça fait
  // magique" — même effet que sur WhatsApp), avec une barre de
  // progression discrète superposée.
  if (enCours && progression?.previewUrl) {
    const pourcentage = progression.octetsTotal
      ? Math.round((progression.octetsEnvoyes / progression.octetsTotal) * 100)
      : 0
    return (
      <div className="video-card__thumb">
        <video className="video-card__player" src={progression.previewUrl} controls playsInline />
        <div className="video-card__upload-progress">
          <div className="video-card__upload-progress-bar" style={{ width: `${pourcentage}%` }} />
        </div>
      </div>
    )
  }

  if (video.url && lecture) {
    return (
      <div className="video-card__thumb">
        <video
          className="video-card__player"
          src={video.url}
          poster={video.poster || undefined}
          controls
          autoPlay
          preload="metadata"
          playsInline
          // Bloque l'entrée standard "Picture-in-Picture" de Chromium —
          // sur Samsung Internet (basé sur Chromium), une bulle flottante
          // "vidéo pop-up" apparaît par-dessus le lecteur sans qu'on
          // l'ait demandé ; à essayer, mais c'est une fonctionnalité du
          // navigateur (Smart pop-up view), pas garanti désactivable
          // depuis une page web — sinon, réglage côté Samsung Internet.
          disablePictureInPicture
        />
      </div>
    )
  }

  return (
    <div className="video-card__thumb">
      {video.poster && <img className="video-card__poster" src={video.poster} alt={video.titre} />}
      <button
        type="button"
        className="video-card__play"
        aria-label={`Lire ${video.titre}`}
        onClick={() => video.url && setLecture(true)}
        disabled={!video.url}
      >
        <Icon name="play" size={22} />
      </button>
      {!video.url && <span className="video-card__duree">{enCours ? 'Envoi…' : video.duree}</span>}
    </div>
  )
}
