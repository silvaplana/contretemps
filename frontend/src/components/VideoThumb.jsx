import { useState } from 'react'
import Icon from './Icon.jsx'

// Vignette vidéo réutilisée par l'onglet Vidéo (VideoScreen.jsx) et le
// détail d'une chorégraphie (ChoregraphieDetailScreen.jsx).
//
// Tant que la lecture n'a pas été demandée, AUCUN <video> n'est monté —
// juste une simple <img> (le `poster`) : s'affiche instantanément, comme
// une vignette YouTube. Monter directement un <video poster preload>
// (essayé d'abord) laissait apparaître, sur mobile (Chrome/Brave/Samsung
// Internet Android testés), une brève animation de chargement autour du
// bouton play avant que le poster ne s'affiche — et, tant que la vidéo
// n'était pas assez initialisée, les contrôles natifs n'incluaient pas
// le bouton plein écran (présent une fois la lecture réellement
// commencée, comme dans Chorégraphie où l'utilisateur avait déjà tapé
// play). Ne créer le <video> qu'au clic règle les deux à la fois : la
// vignette est immédiate, et une fois monté avec `autoPlay`, le
// navigateur a tout de suite les infos nécessaires pour afficher les
// contrôles complets, plein écran inclus.
export default function VideoThumb({ url, poster, titre, duree }) {
  const [lecture, setLecture] = useState(false)

  if (url && lecture) {
    return (
      <div className="video-card__thumb">
        <video
          className="video-card__player"
          src={url}
          poster={poster || undefined}
          controls
          autoPlay
          preload="metadata"
          playsInline
        />
      </div>
    )
  }

  return (
    <div className="video-card__thumb">
      {poster && <img className="video-card__poster" src={poster} alt={titre} />}
      <button
        type="button"
        className="video-card__play"
        aria-label={`Lire ${titre}`}
        onClick={() => url && setLecture(true)}
        disabled={!url}
      >
        <Icon name="play" size={22} />
      </button>
      {!url && <span className="video-card__duree">{duree}</span>}
    </div>
  )
}
