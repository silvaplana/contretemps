// Réduit une photo avant de l'envoyer (fiche d'inscription papier, voir
// screens/admin/AjoutEleveOcr.jsx) : une photo de téléphone pèse plusieurs
// mégaoctets, bien plus qu'il n'en faut pour lire une écriture, et le
// serveur refuse les images trop lourdes. Un PDF, ou une image que le
// navigateur ne sait pas décoder, repart tel quel.
const COTE_MAX = 2200
const QUALITE = 0.85

export async function reduirePhoto(fichier) {
  if (!fichier.type.startsWith('image/')) return fichier
  let image
  try {
    image = await createImageBitmap(fichier, { imageOrientation: 'from-image' })
  } catch {
    return fichier
  }
  const echelle = Math.min(1, COTE_MAX / Math.max(image.width, image.height))
  const toile = document.createElement('canvas')
  toile.width = Math.round(image.width * echelle)
  toile.height = Math.round(image.height * echelle)
  toile.getContext('2d').drawImage(image, 0, 0, toile.width, toile.height)
  image.close?.()
  const blob = await new Promise((resoudre) => toile.toBlob(resoudre, 'image/jpeg', QUALITE))
  if (!blob) return fichier
  return new File([blob], fichier.name.replace(/\.[^.]+$/, '') + '.jpg', { type: 'image/jpeg' })
}
