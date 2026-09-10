// Domaine "vidéos" (écran Vidéo + onglet vidéos d'une chorégraphie, voir
// spec/SPEC.md §6.8) — voir api/README.md pour le principe général.
//
// Vrai upload de fichier (voir AddVideoModal.jsx : `fichier`, un objet
// File brut, plus juste une URL locale) — mutualisé entre l'écran Vidéo
// et le détail d'une chorégraphie via ce même `creer()`, qui bascule
// vers `creerAvecFichierReel`/`creerAvecFichierMaquette` dès que
// `donnees.fichier` est fourni. Côté réel : POST multipart vers
// /cours/{id}/videos/upload (voir backend/src/videos/receiver.py), qui
// écrit le fichier, mesure sa durée et génère sa vignette côté serveur
// (voir videos/duree.py et poster.py) — rien à faire ici. Côté maquette
// (pas de vrai backend pour stocker un fichier) : toujours
// URL.createObjectURL, valable seulement pour cette session navigateur ;
// pas de vignette générée (capture <canvas> possible mais pas la
// priorité, le mock est voué à disparaître, voir messagerie).
//
// `duree` (affichée seulement si `url` est vide, voir VideoThumb.jsx)
// n'existe pas côté backend — jamais envoyée/lue en mode réel.

import { choregraphiesParCours, cours as coursListe, videosParCours } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function dateAffichee() {
  return new Date().toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
}

// --- Maquette : copie mutable en mémoire, jamais l'objet original de
// mockData.js (voir eleves.js pour la même logique, plus détaillée). ---
let magasin = null
function lireMagasin() {
  if (magasin === null) {
    magasin = Object.fromEntries(
      Object.entries(videosParCours).map(([coursId, liste]) => [coursId, liste.map((v) => ({ ...v }))]),
    )
  }
  return magasin
}
function listeMaquette(coursId) {
  const m = lireMagasin()
  if (!m[coursId]) m[coursId] = []
  return m[coursId]
}
function trouverOuLever(videoId) {
  for (const liste of Object.values(lireMagasin())) {
    const v = liste.find((x) => x.id === videoId)
    if (v) return v
  }
  throw new Error('Vidéo introuvable')
}

async function listerMaquette(coursId) {
  return listeMaquette(coursId)
}

async function creerMaquette(coursId, { titre, description, choregraphieId }) {
  const nouvelle = {
    id: crypto.randomUUID(),
    titre,
    description: description ?? '',
    duree: '00:00',
    url: null,
    poster: null,
    choregraphieId: choregraphieId ?? null,
    datePublication: dateAffichee(),
  }
  listeMaquette(coursId).push(nouvelle)
  return nouvelle
}

async function creerAvecFichierMaquette(coursId, { titre, description, choregraphieId, fichier }) {
  const url = URL.createObjectURL(fichier)
  const dureeSecondes = await dureeFichierMaquette(url)
  const mm = String(Math.floor(dureeSecondes / 60)).padStart(2, '0')
  const ss = String(dureeSecondes % 60).padStart(2, '0')
  const nouvelle = {
    id: crypto.randomUUID(),
    titre,
    description: description ?? '',
    duree: `${mm}:${ss}`, // pas affichée tant que `url` est là, voir VideoThumb.jsx — gardée par cohérence avec le reste du magasin
    url,
    poster: null,
    choregraphieId: choregraphieId ?? null,
    datePublication: dateAffichee(),
  }
  listeMaquette(coursId).push(nouvelle)
  return nouvelle
}

async function modifierMaquette(videoId, patch) {
  const v = trouverOuLever(videoId)
  Object.assign(v, patch)
  return v
}

async function supprimerMaquette(coursId, videoId) {
  const liste = listeMaquette(coursId)
  const index = liste.findIndex((v) => v.id === videoId)
  if (index !== -1) liste.splice(index, 1)
}

// Utilisée par le panneau "Usage vidéo" (toute l'école, pas un cours en
// particulier) : cherche/retire dans TOUTES les listes, comme
// trouverOuLever ci-dessus, plutôt que d'exiger le coursId de l'appelant.
async function supprimerParIdMaquette(videoId) {
  for (const liste of Object.values(lireMagasin())) {
    const index = liste.findIndex((v) => v.id === videoId)
    if (index !== -1) {
      liste.splice(index, 1)
      return
    }
  }
}

// Taille réelle d'un fichier statique (voir public/videos/) via une requête
// HEAD (juste les en-têtes, pas le corps) — pas stockée en dur dans
// mockData.js, contrairement au backend qui, lui, lit le fichier sur disque
// à la demande (voir videos.py : usage_ecole). Mode maquette uniquement.
async function tailleFichierMaquette(url) {
  try {
    const reponse = await fetch(url, { method: 'HEAD' })
    const longueur = reponse.headers.get('content-length')
    return longueur ? Number(longueur) : 0
  } catch {
    return 0
  }
}

// Durée réelle d'un fichier statique, lue via un <video> hors-page (pas de
// champ "durée" en dur pour les vraies vidéos, voir note en tête de
// fichier). Mode maquette uniquement — le backend, lui, la mesure une
// seule fois via ffmpeg (voir videos/duree.py) et la stocke.
function dureeFichierMaquette(url) {
  return new Promise((resolve) => {
    const el = document.createElement('video')
    el.preload = 'metadata'
    el.onloadedmetadata = () => resolve(Math.round(el.duration) || 0)
    el.onerror = () => resolve(0)
    el.src = url
  })
}

async function usageMaquette() {
  const coursParId = Object.fromEntries(coursListe.map((c) => [c.id, c.nom]))
  // Toutes les chorégraphies de tous les cours, indexées par id (voir
  // choregraphiesParCours : même principe indexé par coursId que
  // videosParCours, aplati une fois ici plutôt qu'à chaque vidéo).
  const choregraphieParId = Object.fromEntries(
    Object.values(choregraphiesParCours)
      .flat()
      .map((ch) => [ch.id, ch.nom]),
  )
  const magasin = lireMagasin()
  const avecFichier = Object.entries(magasin).flatMap(([coursId, liste]) =>
    liste.filter((v) => v.url).map((v) => ({ ...v, coursNom: coursParId[coursId] ?? '?' })),
  )
  const mesures = await Promise.all(
    avecFichier.map(async (v) => {
      const [tailleOctets, dureeSecondes] = await Promise.all([
        tailleFichierMaquette(v.url),
        dureeFichierMaquette(v.url),
      ])
      return {
        id: v.id,
        titre: v.titre,
        cours: v.coursNom,
        choregraphie: choregraphieParId[v.choregraphieId] ?? null,
        tailleOctets,
        dureeSecondes,
      }
    }),
  )
  const totalOctets = mesures.reduce((s, m) => s + m.tailleOctets, 0)
  const totalSecondes = mesures.reduce((s, m) => s + m.dureeSecondes, 0)
  const topVideos = [...mesures].sort((a, b) => b.tailleOctets - a.tailleOctets).slice(0, 10)
  return { totalOctets, totalSecondes, topVideos }
}

// --- Réel : voir backend/src/videos/receiver.py.

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
    duree: '', // voir note en tête de fichier : pas de champ backend
    url: urlMedia(v.lien_fichier),
    poster: urlMedia(v.poster),
    choregraphieId: v.choregraphie_id,
    datePublication: v.date_publication.slice(8, 10) + '/' + v.date_publication.slice(5, 7),
  }
}

async function listerReel(coursId) {
  const liste = await requete(`/cours/${coursId}/videos`)
  return liste.map(versEcran)
}

async function creerReel(coursId, { titre, description, choregraphieId }, uploaderId) {
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
async function creerAvecFichierReel(coursId, { titre, description, choregraphieId, fichier }, uploaderId) {
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

async function modifierReel(videoId, { titre, choregraphieId, ...reste }) {
  const patch = {
    ...reste,
    ...(titre !== undefined && { nom: titre }),
    ...(choregraphieId !== undefined && { choregraphie_id: choregraphieId }),
  }
  const v = await requete(`/videos/${videoId}`, { method: 'PUT', body: JSON.stringify(patch) })
  return versEcran(v)
}

async function supprimerReel(_coursId, videoId) {
  await requete(`/videos/${videoId}`, { method: 'DELETE' })
}

async function supprimerParIdReel(videoId) {
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

async function usageReel(ecoleId) {
  return versEcranUsage(await requete(`/ecoles/${ecoleId}/videos/usage`))
}

// --- Point d'entrée unique, appelé par les écrans (voir VideoScreen.jsx
// et ChoregraphieScreen.jsx). `uploaderId` = compte connecté (voir
// activeUser dans App.jsx) — requis par le backend, ignoré en maquette.

export async function lister(coursId) {
  return estModeDemo() ? listerMaquette(coursId) : listerReel(coursId)
}

export async function creer(coursId, donnees, uploaderId) {
  if (donnees.fichier) {
    return estModeDemo()
      ? creerAvecFichierMaquette(coursId, donnees)
      : creerAvecFichierReel(coursId, donnees, uploaderId)
  }
  return estModeDemo() ? creerMaquette(coursId, donnees) : creerReel(coursId, donnees, uploaderId)
}

export async function modifier(videoId, patch) {
  return estModeDemo() ? modifierMaquette(videoId, patch) : modifierReel(videoId, patch)
}

export async function supprimer(coursId, videoId) {
  return estModeDemo() ? supprimerMaquette(coursId, videoId) : supprimerReel(coursId, videoId)
}

// Utilisée par le panneau "Usage vidéo" (Admin > École), qui ne connaît
// que l'id de la vidéo, pas son cours — voir supprimerParIdMaquette.
export async function supprimerParId(videoId) {
  return estModeDemo() ? supprimerParIdMaquette(videoId) : supprimerParIdReel(videoId)
}

// Panneau "Usage vidéo" (Admin > École) : Go utilisés, minutes de vidéo,
// top 10 par taille décroissante — voir AdminParametres.jsx.
export async function usage(ecoleId) {
  return estModeDemo() ? usageMaquette() : usageReel(ecoleId)
}
