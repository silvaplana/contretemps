// Vidéos gardées sur le téléphone tant que leur envoi n'est pas fini (Seb,
// 22/11 : un combat filmé perdu après 6 min sans réseau) : si l'appli est
// fermée ou rechargée, l'envoi reprend à la prochaine ouverture (voir
// videoUploads.js : reprendreEnvois). Une base IndexedDB, une ligne par
// envoi : { uploadId, fichier, videoId }.
const BASE = 'envois-video'
const TABLE = 'envois'

function ouvrir() {
  return new Promise((resolve, reject) => {
    const demande = indexedDB.open(BASE, 1)
    demande.onupgradeneeded = () => demande.result.createObjectStore(TABLE, { keyPath: 'uploadId' })
    demande.onsuccess = () => resolve(demande.result)
    demande.onerror = () => reject(demande.error)
  })
}

async function table(mode, agir) {
  const base = await ouvrir()
  return new Promise((resolve, reject) => {
    const transaction = base.transaction(TABLE, mode)
    const resultat = agir(transaction.objectStore(TABLE))
    transaction.oncomplete = () => {
      base.close()
      resolve(resultat?.result)
    }
    transaction.onerror = () => {
      base.close()
      reject(transaction.error)
    }
  })
}

export function garderEnvoi(envoi) {
  return table('readwrite', (t) => t.put(envoi)).catch(() => {})
}

export function oublierEnvoi(uploadId) {
  return table('readwrite', (t) => t.delete(uploadId)).catch(() => {})
}

export function envoisGardes() {
  return table('readonly', (t) => t.getAll()).catch(() => [])
}
