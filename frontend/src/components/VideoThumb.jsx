import Icon from './Icon.jsx'

// Vignette vidéo réutilisée par l'onglet Vidéo (VideoScreen.jsx) et le
// détail d'une chorégraphie (ChoregraphieDetailScreen.jsx) : joue vraiment
// le fichier si `url` existe (voir AddVideoModal.jsx), sinon affiche un
// espace réservé statique avec un bouton play désactivé.
export default function VideoThumb({ url, titre, duree }) {
  return (
    <div className="video-card__thumb">
      {url ? (
        <video className="video-card__player" src={url} controls preload="metadata" />
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
