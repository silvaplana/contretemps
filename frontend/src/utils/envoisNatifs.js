// La file d'envoi d'Android (appli « Tournage <école> », uploads/VideoQueue.kt) :
// la vidéo est écrite sur le téléphone, puis c'est Android qui l'envoie, même
// appli fermée (Seb, 23/11 : « il faut que ce module soit béton de chez
// béton »). Hors de l'appli, rien de tout ça n'existe : l'envoi reste celui de
// la page, qui reprend à la réouverture (voir videoUploads.js).
import { Capacitor, registerPlugin } from '@capacitor/core'
import { compteEnCours, jetonEnCours } from '../api/session.js'

const EnvoisVideo = registerPlugin('EnvoisVideo')
// L'appli Android seulement : le plugin n'existe nulle part ailleurs.
export const FILE_NATIVE = Capacitor.isNativePlatform() && Capacitor.isPluginAvailable('EnvoisVideo')

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
// Le téléphone appelle le serveur sans la page : il lui faut une adresse
// entière, pas « /contretemps/api ».
function adresseApi() {
  return new URL(BASE_URL, window.location.origin).href.replace(/\/$/, '')
}

// Par blocs de 1 Mo : le pont avec Android passe du texte, un gros fichier
// d'un seul coup tiendrait la page.
const TAILLE_BLOC = 1024 * 1024

function base64(morceau) {
  return new Promise((resolve, reject) => {
    const lecteur = new FileReader()
    lecteur.onload = () => resolve(String(lecteur.result).split(',')[1] ?? '')
    lecteur.onerror = () => reject(lecteur.error)
    lecteur.readAsDataURL(morceau)
  })
}

/**
 * Confie la vidéo à Android. Renvoie `true` si elle est bien dans la file :
 * à Android de l'envoyer, la page n'a plus qu'à suivre l'avancement
 * (`avancementNatif`). `false` : à la page de l'envoyer comme d'habitude.
 */
export async function confierEnvoi(uploadId, fichier) {
  if (!FILE_NATIVE) return false
  try {
    await EnvoisVideo.enqueue({ uploadId })
    for (let decalage = 0; decalage < fichier.size; decalage += TAILLE_BLOC) {
      await EnvoisVideo.append({
        uploadId,
        data: await base64(fichier.slice(decalage, decalage + TAILLE_BLOC)),
      })
    }
    await EnvoisVideo.commit({
      uploadId,
      server: adresseApi(),
      token: jetonEnCours(),
      accountId: compteEnCours() === null ? null : String(compteEnCours()),
    })
    return true
  } catch (err) {
    // Place manquante sur le téléphone, vieille version de l'appli… : la page
    // envoie elle-même plutôt que de perdre la vidéo.
    console.error("File d'envoi d'Android indisponible, envoi par la page :", err)
    await annulerEnvoiNatif(uploadId)
    return false
  }
}

/** Les envois encore dans la file : `{ uploadId, sent, size }`. */
export async function avancementNatif() {
  if (!FILE_NATIVE) return []
  try {
    return (await EnvoisVideo.state()).uploads ?? []
  } catch {
    return []
  }
}

export async function annulerEnvoiNatif(uploadId) {
  if (!FILE_NATIVE) return
  try {
    await EnvoisVideo.cancel({ uploadId })
  } catch {
    // Déjà parti : rien à faire.
  }
}
