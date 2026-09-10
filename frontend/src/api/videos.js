// Domaine "vidéos" (écran Vidéo + onglet vidéos d'une chorégraphie, voir
// spec/SPEC.md §6.8) — voir api/README.md pour le principe général.
//
// ⚠️ Limite connue, pas résolue ici : "ajouter une vidéo" ne fait
// aujourd'hui QUE choisir un fichier local (URL.createObjectURL, voir
// AddVideoModal.jsx — valable seulement dans cette session de
// navigateur). Le vrai upload de fichier n'existe pas encore côté
// backend (chantier à part, différé). En mode réel, ce fichier envoie
// donc la forme REST correcte (POST/PUT/DELETE avec les bons champs),
// mais une URL locale choisie par l'utilisateur resterait inutilisable
// ailleurs qu'ici — décision explicite (voir l'utilisateur), à corriger
// seulement quand le vrai upload existera.
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

async function creerMaquette(coursId, donnees) {
  const nouvelle = {
    id: crypto.randomUUID(),
    titre: donnees.titre,
    description: donnees.description ?? '',
    duree: donnees.duree || '00:00',
    url: donnees.url || null,
    poster: donnees.poster || null,
    choregraphieId: donnees.choregraphieId ?? null,
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

// --- Réel : voir backend/src/videos/receiver.py. Pas encore exercé
// (mode démo par défaut, voir mode.js) mais tenu à jour avec les vraies
// routes.

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

async function creerReel(coursId, { titre, description, url, poster, choregraphieId }, uploaderId) {
  const v = await requete(`/cours/${coursId}/videos`, {
    method: 'POST',
    body: JSON.stringify({
      nom: titre,
      description: description ?? '',
      lien_fichier: url ?? '',
      poster: poster ?? null,
      choregraphie_id: choregraphieId ?? null,
      uploaded_by: uploaderId,
    }),
  })
  return versEcran(v)
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
