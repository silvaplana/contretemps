// Domaine "vidéos" (écran Vidéo + onglet vidéos d'une chorégraphie, voir
// spec/SPEC.md §6.8) — voir api/README.md pour le principe général.
//
// Upload par blocs, façon WhatsApp (demande utilisateur explicite) — voir
// utils/videoUploads.js pour l'orchestration (progression, reprise sur
// coupure réseau, annulation) : ce fichier n'expose que les appels réseau
// bruts, dans l'ordre d'utilisation :
//   1. ouvrirTeleversement — dès le fichier choisi/filmé, avant toute
//      métadonnée (voir backend/src/videos/receiver.py).
//   2. ecrireBloc — répété pendant l'envoi.
//   3. finaliserVideo — au clic "Ajouter", même si l'envoi continue.
// annulerTeleversement à tout moment (bouton "Annuler").

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
    coursId: v.cours_id,
    titre: v.nom,
    description: v.description ?? '',
    duree: '', // pas de champ backend pour la durée d'une vidéo réelle
    url: urlMedia(v.lien_fichier),
    poster: urlMedia(v.poster),
    choregraphieId: v.choregraphie_id,
    datePublication: v.date_publication.slice(8, 10) + '/' + v.date_publication.slice(5, 7),
    // 'en_cours' : fichier pas encore complet (voir statut plus haut,
    // Televersement côté backend) — url/poster valent alors null, une
    // vraie lecture locale (aperçu direct du fichier choisi, sans
    // dépendre du serveur) prend le relais côté IHM, voir VideoThumb.jsx
    // et utils/videoUploads.js.
    statut: v.statut,
  }
}

export async function lister(coursId) {
  const liste = await requete(`/cours/${coursId}/videos`)
  return liste.map(versEcran)
}

export async function obtenir(videoId) {
  return versEcran(await requete(`/videos/${videoId}`))
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

// --- Upload par blocs (voir utils/videoUploads.js pour l'orchestration) ---

export async function ouvrirTeleversement(coursId, extension, octetsTotal) {
  return requete(`/cours/${coursId}/videos/televersements`, {
    method: 'POST',
    body: JSON.stringify({ extension, octets_total: octetsTotal }),
  })
}

// Corps BRUT (octet-stream), pas de FormData/JSON : `bloc` est un Blob
// (File.slice()), directement le contenu binaire de ce morceau. Le
// décalage voyage en en-tête (X-Decalage), pas dans l'URL, pour rester
// cohérent avec un simple PUT idempotent sur la ressource "session".
export async function ecrireBloc(uploadId, decalage, bloc) {
  const reponse = await fetch(`${BASE_URL}/videos/televersements/${uploadId}`, {
    method: 'PUT',
    headers: { 'X-Decalage': String(decalage), 'Content-Type': 'application/octet-stream' },
    body: bloc,
  })
  if (reponse.status === 409) {
    // Décalage désynchronisé (voir backend/src/videos/videos.py :
    // DecalageInvalide) — le corps donne le VRAI décalage à reprendre.
    const detail = await reponse.json().catch(() => null)
    const erreur = new Error('Décalage désynchronisé')
    erreur.decalageActuel = detail?.detail?.octets_recus
    throw erreur
  }
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  const donnees = await reponse.json()
  return { octetsRecus: donnees.octets_recus, complet: donnees.complet }
}

export async function annulerTeleversement(uploadId) {
  await fetch(`${BASE_URL}/videos/televersements/${uploadId}`, { method: 'DELETE' })
}

export async function finaliserVideo(coursId, uploadId, { nom, description, choregraphieId, uploaderId }) {
  const v = await requete(`/cours/${coursId}/videos/depuis-televersement`, {
    method: 'POST',
    body: JSON.stringify({
      upload_id: uploadId,
      nom,
      description: description || '',
      choregraphie_id: choregraphieId ?? null,
      uploaded_by: uploaderId,
    }),
  })
  return versEcran(v)
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
