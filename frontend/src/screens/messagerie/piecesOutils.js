// Photos et fichiers à envoyer (spec/modules/messagerie-instantanee.md §4.3).

export const TAILLE_MAX_FICHIER = 25 * 1024 * 1024 // comme le serveur
const COTE_MAX_PHOTO = 1600

export function tailleLisible(octets) {
  if (octets < 1024 * 1024) return `${Math.max(1, Math.round(octets / 1024))} Ko`
  return `${(octets / (1024 * 1024)).toFixed(1).replace('.', ',')} Mo`
}

// Réduit une photo sur le téléphone avant l'envoi (§4.3) : côté le plus
// long 1 600 px, JPEG. Une image que le navigateur ne sait pas lire part
// telle quelle, comme un fichier.
export async function preparerPhoto(fichier) {
  try {
    const image = await createImageBitmap(fichier, { imageOrientation: 'from-image' })
    const echelle = Math.min(1, COTE_MAX_PHOTO / Math.max(image.width, image.height))
    const canvas = document.createElement('canvas')
    canvas.width = Math.round(image.width * echelle)
    canvas.height = Math.round(image.height * echelle)
    canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height)
    const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', 0.82))
    if (!blob) throw new Error('conversion impossible')
    const nom = `${fichier.name.replace(/\.[^.]+$/, '') || 'photo'}.jpg`
    return { fichier: blob, nom, kind: 'photo', apercu: URL.createObjectURL(blob) }
  } catch {
    return { fichier, nom: fichier.name, kind: 'file', apercu: null }
  }
}
