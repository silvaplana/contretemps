// Domaine "vidéos" (écran Vidéo + onglet vidéos d'une chorégraphie, voir
// spec/SPEC.md §6.8) — voir api/README.md pour le principe général.
//
// Vrai upload de fichier (voir AddVideoModal.jsx : `fichier`, un objet
// File brut) — mutualisé entre l'écran Vidéo et le détail d'une
// chorégraphie via ce même `creer()`, qui bascule vers
// `creerAvecFichierReel` dès que `donnees.fichier` est fourni : POST
// multipart vers /cours/{id}/videos/upload (voir
// backend/src/videos/receiver.py), qui écrit le fichier, mesure sa durée
// et génère sa vignette côté serveur (voir videos/duree.py et
// poster.py) — rien à faire ici.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// `lien_fichier`/`poster` en base sont des chemins RELATIFS (voir
// backend/src/videos/stockage.py, ex. "1/xxx.mp4") — pas des URL. Le
// backend les sert sous /media/videos/<ce chemin> (voir app/main.py) :
// sans ce préfixe, le <video>/poster pointerait sur une URL relative à
// la PAGE (jamais valide) plutôt qu'à l'API. Bug réel trouvé en testant
// sur un vrai téléphone (rien ne se chargeait, aucune erreur visible).
function urlMedia(cheminRelatif) {
  return cheminRelatif ? `${BASE_URL}/media/videos/${cheminRelatif}` : null
}

function versEcran(v) {
  return {
    id: v.id,
    titre: v.nom,
    description: v.description ?? '',
    duree: '', // pas de champ backend pour la durée d'une vidéo réelle
    url: urlMedia(v.lien_fichier),
    poster: urlMedia(v.poster),
    choregraphieId: v.choregraphie_id,
    datePublication: v.date_publication.slice(8, 10) + '/' + v.date_publication.slice(5, 7),
  }
}

export async function lister(coursId) {
  const liste = await requete(`/cours/${coursId}/videos`)
  return liste.map(versEcran)
}

async function creerSansFichier(coursId, { titre, description, choregraphieId }, uploaderId) {
  const v = await requete(`/cours/${coursId}/videos`, {
    method: 'POST',
    body: JSON.stringify({
      nom: titre,
      description: description ?? '',
      lien_fichier: '',
      choregraphie_id: choregraphieId ?? null,
      uploaded_by: uploaderId,
    }),
  })
  return versEcran(v)
}

// Vrai upload multipart (voir backend/src/videos/receiver.py : uploader)
// — FormData, jamais de Content-Type manuel (le navigateur pose lui-même
// la bonne frontière multipart, voir requete() plus haut qui force du
// JSON et ne convient donc pas ici).
async function creerAvecFichier(coursId, { titre, description, choregraphieId, fichier }, uploaderId) {
  const corps = new FormData()
  corps.append('fichier', fichier, fichier.name)
  corps.append('nom', titre)
  corps.append('uploaded_by', uploaderId)
  if (description) corps.append('description', description)
  if (choregraphieId) corps.append('choregraphie_id', choregraphieId)

  const reponse = await fetch(`${BASE_URL}/cours/${coursId}/videos/upload`, {
    method: 'POST',
    body: corps,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return versEcran(await reponse.json())
}

// `uploaderId` = compte connecté (voir activeUser dans App.jsx) — requis
// par le backend.
export async function creer(coursId, donnees, uploaderId) {
  if (donnees.fichier) return creerAvecFichier(coursId, donnees, uploaderId)
  return creerSansFichier(coursId, donnees, uploaderId)
}

export async function modifier(videoId, { titre, choregraphieId, ...reste }) {
  const patch = {
    ...reste,
    ...(titre !== undefined && { nom: titre }),
    ...(choregraphieId !== undefined && { choregraphie_id: choregraphieId }),
  }
  const v = await requete(`/videos/${videoId}`, { method: 'PUT', body: JSON.stringify(patch) })
  return versEcran(v)
}

export async function supprimer(_coursId, videoId) {
  await requete(`/videos/${videoId}`, { method: 'DELETE' })
}

// Utilisée par le panneau "Usage vidéo" (Admin > École), qui ne connaît
// que l'id de la vidéo, pas son cours.
export async function supprimerParId(videoId) {
  await requete(`/videos/${videoId}`, { method: 'DELETE' })
}

function versEcranUsage(u) {
  return {
    totalOctets: u.total_octets,
    totalSecondes: u.total_secondes,
    topVideos: u.top_videos.map((v) => ({
      id: v.id,
      titre: v.titre,
      cours: v.cours,
      choregraphie: v.choregraphie,
      tailleOctets: v.taille_octets,
      dureeSecondes: v.duree_secondes,
    })),
  }
}

// Panneau "Usage vidéo" (Admin > École) : Go utilisés, minutes de vidéo,
// top 10 par taille décroissante — voir AdminParametres.jsx.
export async function usage(ecoleId) {
  return versEcranUsage(await requete(`/ecoles/${ecoleId}/videos/usage`))
}
