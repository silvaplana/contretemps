// Envoi d'un fichier vers Google Drive DEPUIS LE NAVIGATEUR, avec le
// propre compte Google de l'admin (voir SauvegardeEcoleMenu.jsx —
// distinct du compte de service utilisé côté serveur pour la sauvegarde
// programmée, voir backend/src/ecoles/google_drive.py). Décision
// utilisateur explicite : au clic sur "Sauvegarder École", si la
// destination choisie est "Drive", les fichiers partent directement dans
// le Drive personnel de l'admin (scope `drive.file`, limité aux fichiers
// créés par CETTE appli — jamais un accès au reste de son Drive).
//
// Pas de bibliothèque npm : le script Google Identity Services (GIS) est
// chargé à la demande (pas dans index.html — seulement si l'admin choisit
// vraiment Drive un jour, voir chargerScriptGoogle), comme le reste de
// l'appli évite les dépendances externes quand un simple appel direct
// suffit (voir Icon.jsx).

const SCOPE_DRIVE = 'https://www.googleapis.com/auth/drive.file'

export function estConfigureDrive() {
  return Boolean(import.meta.env.VITE_GOOGLE_CLIENT_ID)
}

let promesseScript = null

function chargerScriptGoogle() {
  if (promesseScript) return promesseScript
  promesseScript = new Promise((resolve, reject) => {
    if (window.google?.accounts?.oauth2) {
      resolve()
      return
    }
    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Impossible de charger le script Google.'))
    document.head.appendChild(script)
  })
  return promesseScript
}

// Jeton mémorisé EN MÉMOIRE seulement (pas de stockage persistant — un
// jeton d'accès Google expire vite, ~1h, et le reprendre tel quel après
// fermeture de l'onglet ne servirait à rien) : évite de redemander le
// consentement Google à chaque fichier d'un même "Sauvegarder École"
// (2 fichiers = 2 televerserVersDrive), pas à chaque session.
let jetonMemoire = null

function demanderJeton() {
  return new Promise((resolve, reject) => {
    if (jetonMemoire) {
      resolve(jetonMemoire)
      return
    }
    const client = window.google.accounts.oauth2.initTokenClient({
      client_id: import.meta.env.VITE_GOOGLE_CLIENT_ID,
      scope: SCOPE_DRIVE,
      callback: (reponse) => {
        if (reponse.error) {
          reject(new Error(`Autorisation Google refusée (${reponse.error}).`))
          return
        }
        jetonMemoire = reponse.access_token
        // Le jeton n'est plus réutilisable après son expiration (voir
        // `expires_in`, secondes) — on oublie juste assez tôt pour ne
        // jamais tenter un envoi voué à échouer.
        setTimeout(() => {
          jetonMemoire = null
        }, (reponse.expires_in - 60) * 1000)
        resolve(reponse.access_token)
      },
    })
    client.requestAccessToken()
  })
}

export async function televerserVersDrive(nomFichier, blob) {
  await chargerScriptGoogle()
  const jeton = await demanderJeton()
  const metadonnees = { name: nomFichier }
  const corps = new FormData()
  corps.append('metadata', new Blob([JSON.stringify(metadonnees)], { type: 'application/json' }))
  corps.append('media', blob)

  const reponse = await fetch(
    'https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart',
    { method: 'POST', headers: { Authorization: `Bearer ${jeton}` }, body: corps },
  )
  if (!reponse.ok) throw new Error(`Envoi Google Drive échoué (${reponse.status})`)
}
