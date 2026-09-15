// Téléchargement d'un fichier généré par le backend, avec CHOIX DE
// L'EMPLACEMENT quand le navigateur le permet (File System Access API —
// Chrome/Edge desktop uniquement, voir MDN showSaveFilePicker) : ouvre une
// vraie boîte "Enregistrer sous" où choisir le dossier. Ailleurs (Firefox,
// Safari, mobile), repli sur le téléchargement classique (dossier de
// téléchargement par défaut du navigateur, comme
// api/inscriptions.js:telechargerNouvellesInscriptions).
//
// Le nom de fichier vient du serveur (en-tête Content-Disposition, voir
// backend/src/ecoles/receiver.py) plutôt que recalculé ici — une seule
// source de vérité pour la convention de nommage (<École>_<date>...).
export async function telechargerFichier(url, nomSecours) {
  const reponse = await fetch(url)
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  const entete = reponse.headers.get('Content-Disposition') ?? ''
  const correspondance = entete.match(/filename="([^"]+)"/)
  const nomFichier = correspondance ? correspondance[1] : nomSecours
  const blob = await reponse.blob()

  if (typeof window.showSaveFilePicker === 'function') {
    try {
      const handle = await window.showSaveFilePicker({
        suggestedName: nomFichier,
        types: [
          {
            description: 'Classeur Excel',
            accept: {
              'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
            },
          },
        ],
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
  lien.download = nomFichier
  document.body.appendChild(lien)
  lien.click()
  lien.remove()
  URL.revokeObjectURL(objetUrl)
}
