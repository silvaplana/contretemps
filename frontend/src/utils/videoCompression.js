// Compression AVANT l'envoi, via l'encodeur matériel du téléphone/PC (API
// WebCodecs, accessible même sur le web — voir mediabunny.dev, qui
// encapsule WebCodecs proprement plutôt que de le manipuler à la main).
// Réduit nettement le volume à ENVOYER (facteur ~5-15x sur une vidéo de
// téléphone), donc l'upload lui-même est plus rapide — pas seulement le
// stockage, contrairement à la compression serveur après coup qui reste
// en place comme filet de sécurité (voir backend/src/videos/compression.py,
// toujours utile pour les navigateurs sans WebCodecs).
//
// Ne bloque JAMAIS l'envoi (règle explicite, même philosophie que le
// reste du projet — SMTP/HelloAsso/Google Drive échouent tous en
// silence) : codec non supporté, navigateur trop ancien, fichier illisible,
// erreur quelconque -> renvoie le fichier ORIGINAL tel quel, l'upload brut
// prend le relais normalement.
//
// `import('mediabunny')` DYNAMIQUE, jamais statique : cette bibliothèque
// (~135 Ko gzip, mesuré) ne doit être téléchargée QUE par les personnes
// qui ajoutent vraiment une vidéo — un `import` statique l'aurait mise
// dans le bundle initial, ralentissant le chargement de toute l'appli
// pour tout le monde (vécu : le build est passé de ~95 à ~230 Ko gzip).

// Même limite que la compression serveur (voir compression.py:HAUTEUR_MAX)
// — une répétition filmée au téléphone n'a pas besoin de 4K pour rester
// lisible, et c'est la résolution qui pèse le plus sur la taille.
const HAUTEUR_MAX = 1080

export async function estCompressionDisponible() {
  // Vérif la moins chère d'abord : évite de télécharger mediabunny pour
  // rien sur un navigateur qui n'a de toute façon pas WebCodecs.
  if (typeof VideoEncoder === 'undefined') return false
  try {
    const { canEncodeVideo } = await import('mediabunny')
    return await canEncodeVideo('avc')
  } catch {
    return false
  }
}

// `onProgress(pourcentage)` : 0-100, appelé pendant la compression (avant
// que l'envoi par blocs ne démarre, voir AjouterVideo.jsx) — permet
// d'afficher un état "Compression…" distinct de la barre de progression
// d'envoi qui prend le relais juste après.
export async function compresserOuOriginal(fichier, { onProgress } = {}) {
  try {
    if (!(await estCompressionDisponible())) return fichier

    const { ALL_FORMATS, BlobSource, BufferTarget, Conversion, Input, Mp4OutputFormat, Output, Quality } =
      await import('mediabunny')

    const input = new Input({ source: new BlobSource(fichier), formats: ALL_FORMATS })
    const pisteVideo = await input.getPrimaryVideoTrack()
    if (!pisteVideo) return fichier // fichier sans piste vidéo lisible

    const hauteur = await pisteVideo.getDisplayHeight()
    const output = new Output({ format: new Mp4OutputFormat(), target: new BufferTarget() })
    const conversion = await Conversion.init({
      input,
      output,
      video: {
        codec: 'avc',
        quality: new Quality('medium'),
        // Ne JAMAIS agrandir une vidéo déjà plus petite que la limite.
        height: hauteur > HAUTEUR_MAX ? HAUTEUR_MAX : undefined,
        // "no-preference" (le défaut recommandé par mediabunny, voir sa
        // doc) plutôt que "prefer-hardware" : ce dernier fait ÉCHOUER la
        // configuration si aucun encodeur matériel n'est dispo pour ces
        // paramètres précis (vécu : testé sans repli logiciel possible),
        // au lieu de simplement utiliser le logiciel comme repli — perdrait
        // la vitesse gagnée seulement sur les appareils SANS accélération
        // matérielle, ce qui est exactement le cas où on ne veut surtout
        // pas échouer.
        hardwareAcceleration: 'no-preference',
      },
      audio: { codec: 'aac', quality: new Quality('medium') },
    })
    // Une piste perdue (le plus souvent l'audio — vécu : AAC pas
    // encodable dans un environnement de test) ne doit JAMAIS passer
    // inaperçue : une vidéo de danse sans sa musique serait inutilisable.
    // Plutôt que de risquer ça en silence, on abandonne la compression
    // entière et on repart sur l'original (son intact).
    if (!conversion.isValid || conversion.discardedTracks.length > 0) return fichier

    if (onProgress) conversion.onProgress = (p) => onProgress(Math.round(p * 100))
    await conversion.execute()

    const buffer = output.target.buffer
    if (!buffer || buffer.byteLength === 0) return fichier
    const compresse = new File(
      [buffer],
      fichier.name.replace(/\.[^/.]+$/, '') + '.mp4',
      { type: 'video/mp4' },
    )
    // Rien à gagner si le résultat n'est pas plus petit (ex. source déjà
    // très compressée) — envoyer l'original évite un aller-retour inutile.
    return compresse.size < fichier.size ? compresse : fichier
  } catch (err) {
    console.error('Compression vidéo ignorée, envoi du fichier original :', err)
    return fichier
  }
}
