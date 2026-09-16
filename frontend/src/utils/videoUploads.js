// Gestionnaire d'upload vidéo par blocs, façon WhatsApp (demande
// utilisateur explicite) — état EN DEHORS du cycle de vie React (module-
// level, pas de useState), pour survivre à la fermeture de la modale
// "Ajouter une vidéo" ou à un changement d'écran pendant l'envoi (voir
// AjouterVideo.jsx : "Ajouter" ferme l'écran mais l'envoi continue en
// tâche de fond). Ne survit PAS à un rechargement de page/fermeture de
// l'app (décision utilisateur explicite : "si on ferme l'app, on annule
// tout, pas besoin de survivre à ça") — tout est en mémoire, jamais
// persisté sur disque local, donc perdu au reload sans nécessiter de
// nettoyage particulier ici (le backend, lui, nettoie tout seul les
// sessions abandonnées après quelques heures, voir videos.py).
import { useEffect, useSyncExternalStore } from 'react'
import * as videosApi from '../api/videos.js'

const TAILLE_BLOC = 2 * 1024 * 1024 // 2 Mo

// uploadId -> { octetsEnvoyes, octetsTotal, complet, videoId, previewUrl }
const sessions = new Map()
const videoIdVersUploadId = new Map()
const abandonnes = new Set()
const abonnesProgression = new Set()
const abonnesTermines = new Set() // (video au format écran) => void

function notifierProgression() {
  for (const f of abonnesProgression) f()
}

function sabonner(f) {
  abonnesProgression.add(f)
  return () => abonnesProgression.delete(f)
}

// Pendant le remplissage du formulaire (avant "Ajouter"), suivi par
// uploadId — c'est tout ce qu'AjouterVideo.jsx connaît à ce stade.
export function useProgressionTeleversement(uploadId) {
  return useSyncExternalStore(sabonner, () => (uploadId ? sessions.get(uploadId) : undefined))
}

// Après "Ajouter", la vidéo existe déjà dans les listes (VideoScreen/
// ChoregraphieDetailScreen) avec son id — suivi par videoId pour que
// VideoThumb.jsx puisse afficher l'aperçu local + la progression tant
// que statut === 'en_cours'.
export function useProgressionVideo(videoId) {
  return useSyncExternalStore(sabonner, () => {
    const uploadId = videoIdVersUploadId.get(videoId)
    return uploadId ? sessions.get(uploadId) : undefined
  })
}

// App.jsx : rafraîchit sa liste de vidéos quand un envoi commencé "en
// cours" se termine — même si l'écran d'origine (Vidéo/Chorégraphie)
// n'est plus affiché entre-temps (l'envoi ne dépend pas de l'écran).
export function useTeleversementsTermines(onTermine) {
  useEffect(() => {
    abonnesTermines.add(onTermine)
    return () => abonnesTermines.delete(onTermine)
  }, [onTermine])
}

// Démarre tout de suite (voir demande utilisateur : dès le fichier
// choisi/filmé, avant même de connaître le titre) — renvoie l'id de
// session dès qu'il est connu, l'envoi des blocs continue derrière sans
// attendre l'appelant.
export async function demarrerTeleversement(coursId, fichier) {
  const previewUrl = URL.createObjectURL(fichier)
  const extension = `.${fichier.name.split('.').pop() || 'mp4'}`
  const session = await videosApi.ouvrirTeleversement(coursId, extension, fichier.size)
  sessions.set(session.id, {
    octetsEnvoyes: 0,
    octetsTotal: fichier.size,
    complet: false,
    videoId: null,
    previewUrl,
  })
  notifierProgression()
  envoyerBlocs(session.id, fichier)
  return session.id
}

async function envoyerBlocs(uploadId, fichier) {
  let decalage = 0
  try {
    while (decalage < fichier.size) {
      if (abandonnes.has(uploadId)) return
      decalage = await envoyerUnBloc(uploadId, fichier, decalage)
      const etat = sessions.get(uploadId)
      if (!etat) return // annulé entre-temps
      sessions.set(uploadId, { ...etat, octetsEnvoyes: decalage })
      notifierProgression()
    }
  } catch {
    // Annulé (voir annulerTeleversement) ou définitivement échoué après
    // 20 tentatives (voir envoyerUnBloc) — reste "en_cours" sans avancer,
    // pas d'autre action possible côté client pour l'instant (amélioration
    // future : bouton "réessayer"). Ne doit jamais faire planter le reste
    // de l'appli.
    return
  }

  const etat = sessions.get(uploadId)
  if (!etat) return
  sessions.set(uploadId, { ...etat, complet: true })
  notifierProgression()

  // "Ajouter" a déjà été cliqué (voir finaliserTeleversement) : la vidéo
  // existe déjà dans les listes en 'en_cours', il faut la rafraîchir avec
  // le fichier définitif (poster/durée) maintenant disponible côté
  // serveur (voir videos.py : le dernier bloc finalise tout de suite si
  // video_id est déjà connu). Si "Ajouter" n'a pas encore été cliqué,
  // rien à rafraîchir : la vidéo n'existe pas encore en base.
  if (etat.videoId) {
    const video = await videosApi.obtenir(etat.videoId)
    for (const f of abonnesTermines) f(video)
    URL.revokeObjectURL(etat.previewUrl)
    sessions.delete(uploadId)
    videoIdVersUploadId.delete(etat.videoId)
    notifierProgression()
  }
}

// Bloc envoyé jusqu'à réussite — coupure réseau (voir demande
// utilisateur : "gestion des interruptions et des ratés") : délai
// croissant entre tentatives, jamais abandonné de lui-même (seul
// annulerTeleversement interrompt réellement), sauf après 20 échecs
// consécutifs (~ quelques minutes de tentatives, au-delà ça ne relève
// probablement plus d'une coupure temporaire).
async function envoyerUnBloc(uploadId, fichier, decalageDepart) {
  let decalage = decalageDepart
  let tentative = 0
  for (;;) {
    if (abandonnes.has(uploadId)) throw new Error('Envoi annulé')
    const bloc = fichier.slice(decalage, decalage + TAILLE_BLOC)
    try {
      const resultat = await videosApi.ecrireBloc(uploadId, decalage, bloc)
      return resultat.octetsRecus
    } catch (err) {
      if (err.decalageActuel !== undefined) {
        // Désynchronisé (voir receiver.py : 409) — resynchronise sur le
        // VRAI décalage plutôt que de deviner, puis retente tout de suite.
        decalage = err.decalageActuel
        continue
      }
      tentative += 1
      if (tentative > 20) throw err
      await new Promise((resolve) => setTimeout(resolve, Math.min(1000 * tentative, 10000)))
    }
  }
}

// "Annuler" (voir spec : "arrête tout, il faudra nettoyer l'upload") —
// stoppe la boucle d'envoi en cours ET nettoie côté serveur (fichier
// partiel + ligne Video si "Ajouter" avait déjà été cliqué entre-temps,
// voir backend/src/videos/videos.py : annuler_televersement).
export function annulerTeleversement(uploadId) {
  const etat = sessions.get(uploadId)
  abandonnes.add(uploadId)
  sessions.delete(uploadId)
  if (etat?.videoId) videoIdVersUploadId.delete(etat.videoId)
  notifierProgression()
  if (etat?.previewUrl) URL.revokeObjectURL(etat.previewUrl)
  videosApi.annulerTeleversement(uploadId).catch(() => {
    // Pas grave si ça échoue (ex. déjà nettoyé côté serveur) — l'envoi
    // est de toute façon arrêté côté client (voir `abandonnes` ci-dessus).
  })
}

// Clic "Ajouter" — crée la ligne en base tout de suite (voir spec),
// l'envoi continue derrière si pas encore fini (voir envoyerBlocs).
export async function finaliserTeleversement(coursId, uploadId, metadonnees) {
  const video = await videosApi.finaliserVideo(coursId, uploadId, metadonnees)
  const etat = sessions.get(uploadId)
  if (etat) {
    if (etat.complet) {
      // L'envoi s'est terminé avant le clic "Ajouter" (fichier assez
      // petit/réseau assez rapide) — le backend a déjà tout finalisé
      // (voir finaliser() : renvoie 'complete' direct), rien à suivre.
      URL.revokeObjectURL(etat.previewUrl)
      sessions.delete(uploadId)
    } else {
      sessions.set(uploadId, { ...etat, videoId: video.id })
      videoIdVersUploadId.set(video.id, uploadId)
    }
    notifierProgression()
  }
  return video
}
