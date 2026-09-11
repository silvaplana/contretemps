// Domaine "inscriptions" (page publique contretemps-inscription, voir
// spec/SPEC-inscription.md et backend/src/inscriptions/) — l'appli
// principale n'a qu'UN seul besoin ici : permettre à l'admin de
// télécharger le fichier Excel "nouvelles inscriptions" (voir
// AdminParametres.jsx, bouton à côté de "Usage vidéo"). Tout le reste
// (formulaire, calcul du tarif...) vit dans frontend-inscription/, un
// projet séparé.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Déclenche le téléchargement du classeur courant — pas de <a download>
// direct vers l'URL de l'API : ça éviterait de distinguer un vrai succès
// (fichier reçu) d'un 404 ("aucune nouvelle inscription", voir
// receiver.py) avant de lancer le téléchargement.
export async function telechargerNouvellesInscriptions(ecoleId) {
  const reponse = await fetch(`${BASE_URL}/inscriptions/export?ecole_id=${ecoleId}`)
  if (reponse.status === 404) {
    throw new Error('Aucune nouvelle inscription pour le moment.')
  }
  if (!reponse.ok) {
    throw new Error(`Requête échouée (${reponse.status})`)
  }
  const blob = await reponse.blob()
  const url = URL.createObjectURL(blob)
  const lien = document.createElement('a')
  lien.href = url
  lien.download = 'nouvelles_inscriptions.xlsx'
  document.body.appendChild(lien)
  lien.click()
  lien.remove()
  URL.revokeObjectURL(url)
}
