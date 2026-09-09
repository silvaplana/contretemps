import Icon from './Icon.jsx'

// Vignette vidéo réutilisée par l'onglet Vidéo (VideoScreen.jsx) et le
// détail d'une chorégraphie (ChoregraphieDetailScreen.jsx) : joue vraiment
// le fichier si `url` existe (voir AddVideoModal.jsx), sinon affiche un
// espace réservé statique avec un bouton play désactivé.
//
// `poster` (image statique) affichée immédiatement, sans attendre le
// moindre octet de vidéo — indispensable sur mobile : contrairement à
// Chrome desktop, Chrome/Brave/Samsung Internet sur Android n'affichent
// PAS la 1re image d'une vidéo tant qu'elle n'a pas été jouée (juste une
// case noire + icône "média"), ce qui donnait l'impression que "les
// vidéos ne marchent pas" (repéré sur un vrai téléphone). `preload="none"`
// (au lieu de "metadata") : dans une LISTE de plusieurs vidéos, ne
// télécharge aucun octet de la vidéo tant qu'on n'a pas tapé play — le
// poster suffit à afficher un aperçu, comme YouTube (voir aussi le
// "faststart" déjà présent dans les fichiers, pour un démarrage rapide
// une fois la lecture lancée).
export default function VideoThumb({ url, poster, titre, duree }) {
  return (
    <div className="video-card__thumb">
      {url ? (
        <video
          className="video-card__player"
          src={url}
          poster={poster || undefined}
          controls
          preload="none"
          playsInline
        />
      ) : (
        <>
          <button type="button" className="video-card__play" aria-label={`Lire ${titre}`} disabled>
            <Icon name="play" size={22} />
          </button>
          <span className="video-card__duree">{duree}</span>
        </>
      )}
    </div>
  )
}
