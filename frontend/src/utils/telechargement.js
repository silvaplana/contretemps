import { televerserVersDrive } from './googleDrive.js'

// Récupération + sauvegarde d'un fichier généré par le backend — soit en
// LOCAL (choix de l'emplacement quand le navigateur le permet), soit sur
// GOOGLE DRIVE (voir googleDrive.js) : destination choisie par l'admin,
// voir SauvegardeEcoleMenu.jsx.
//
// Le nom de fichier vient du serveur (en-tête Content-Disposition, voir
// backend/src/ecoles/receiver.py) plutôt que recalculé ici — une seule
// source de vérité pour la convention de nommage (<École>_<date>...).
async function recupererFichier(url, nomSecours) {
  const reponse = await fetch(url)
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  const entete = reponse.headers.get('Content-Disposition') ?? ''
  // `filename*=UTF-8''…` (noms accentués, ex. notes de frais) ou `filename="…"`.
  const encode = entete.match(/filename\*=UTF-8''([^;]+)/i)
  const correspondance = entete.match(/filename="([^"]+)"/)
  const nom = encode ? decodeURIComponent(encode[1]) : correspondance ? correspondance[1] : nomSecours
  const blob = await reponse.blob()
  return { nom, blob }
}

// LOCAL — CHOIX DE L'EMPLACEMENT quand le navigateur le permet (File
// System Access API — Chrome/Edge desktop uniquement, voir MDN
// showSaveFilePicker) : ouvre une vraie boîte "Enregistrer sous" où
// choisir le dossier. Ailleurs (Firefox, Safari, mobile), repli sur le
// téléchargement classique (dossier de téléchargement par défaut du
// navigateur, comme api/inscriptions.js:telechargerNouvellesInscriptions).
const TYPE_EXCEL = {
  description: 'Classeur Excel',
  accept: { 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
}
const TYPE_ZIP = { description: 'Archive zip', accept: { 'application/zip': ['.zip'] } }

export async function telechargerFichier(url, nomSecours) {
  const { nom, blob } = await recupererFichier(url, nomSecours)

  if (typeof window.showSaveFilePicker === 'function') {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: nom,
        types: [nom.endsWith('.zip') ? TYPE_ZIP : TYPE_EXCEL],
      })
      const flux = await handle.createWritable()
      await flux.write(blob)
      await flux.close()
      return
    } catch (err) {
      // L'utilisateur a annulé la boîte "Enregistrer sous" (pas une vraie
      // erreur) : on s'arrête là, pas de repli — il a dit non, pas
      // "essaie autrement".
      if (err.name === 'AbortError') return
      // Autre échec (permission refusée...) : on retente en classique.
    }
  }

  const objetUrl = URL.createObjectURL(blob)
  const lien = document.createElement('a')
  lien.href = objetUrl
  lien.download = nom
  document.body.appendChild(lien)
  lien.click()
  lien.remove()
  URL.revokeObjectURL(objetUrl)
}

// GOOGLE DRIVE — voir googleDrive.js:televerserVersDrive.
export async function envoyerFichierVersDrive(url, nomSecours) {
  const { nom, blob } = await recupererFichier(url, nomSecours)
  await televerserVersDrive(nom, blob)
}
