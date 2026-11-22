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
// Exception, les combats du Timer de Fights (Seb, 22/11) : `garder` range la
// vidéo sur le téléphone jusqu'à la fin de l'envoi, qui reprend à la
// prochaine ouverture de l'appli (voir envoisGardes.js, reprendreEnvois).
import { useEffect, useSyncExternalStore } from 'react'
import * as videosApi from '../api/videos.js'
import { envoisGardes, garderEnvoi, oublierEnvoi } from './envoisGardes.js'

const TAILLE_BLOC = 2 * 1024 * 1024 // 2 Mo

// uploadId -> { octetsEnvoyes, octetsTotal, complet, videoId, previewUrl }
const sessions = new Map()
const videoIdVersUploadId = new Map()
const abandonnes = new Set()
const abonnesProgression = new Set()
const abonnesTermines = new Set() // (video au format écran) => void
// videoId -> { url, publieeLe } : URL locale du fichier envoyé depuis CE
// téléphone, et l'instant d'envoi de la vidéo (un numéro de vidéo supprimée
// peut être réutilisé : on ne montre la copie qu'à la bonne). Une fois
// l'envoi fini, on continue de lire cette copie tant que l'appli reste
// ouverte (Seb, 2026-10-15) — pas de coupure de la lecture à la fin de
// l'envoi, pas d'attente du téléchargement, et pas de mélange avec le
// fichier que le serveur compresse juste après.
const copiesLocales = new Map()
// Vidéos refaites par le serveur (incrustation de Fights, Seb 21/11) : la
// copie du téléphone ne sert que pendant l'envoi, ensuite c'est celle du serveur.
const sansCopie = new Set()

function garderCopieLocale(video, previewUrl) {
  if (video?.id && previewUrl && !sansCopie.has(video.id)) copiesLocales.set(video.id, { url: previewUrl, publieeLe: video.publieeLe })
  else if (previewUrl) URL.revokeObjectURL(previewUrl)
}

export function sansCopieLocale(videoId) {
  sansCopie.add(videoId)
  const copie = copiesLocales.get(videoId)
  if (copie) {
    copiesLocales.delete(videoId)
    URL.revokeObjectURL(copie.url)
    notifierProgression()
  }
}

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

// La vidéo, lisible depuis ce téléphone sans rien télécharger : pendant
// l'envoi, puis après (voir copiesLocales). `undefined` sinon.
export function useCopieLocale(video) {
  return useSyncExternalStore(sabonner, () => {
    const uploadId = videoIdVersUploadId.get(video.id)
    if (uploadId && sessions.get(uploadId)?.previewUrl) return sessions.get(uploadId).previewUrl
    const copie = copiesLocales.get(video.id)
    return copie && copie.publieeLe === video.publieeLe ? copie.url : undefined
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
export async function demarrerTeleversement(ecoleId, fichier, { garder = false } = {}) {
  const previewUrl = URL.createObjectURL(fichier)
  const extension = `.${fichier.name.split('.').pop() || 'mp4'}`
  const session = await videosApi.ouvrirTeleversement(ecoleId, extension, fichier.size)
  if (garder) await garderEnvoi({ uploadId: session.id, fichier, videoId: null })
  sessions.set(session.id, {
    octetsEnvoyes: 0,
    octetsTotal: fichier.size,
    complet: false,
    videoId: null,
    previewUrl,
    garder,
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
  } catch (err) {
    // Annulé (voir annulerTeleversement) ou refusé par le serveur (envoi
    // introuvable, voir envoyerUnBloc) — reste "en_cours" sans avancer.
    // Ne doit jamais faire planter le reste de l'appli.
    if (err.status) oublierEnvoi(uploadId)
    return
  }

  const etat = sessions.get(uploadId)
  if (!etat) return
  if (etat.garder) oublierEnvoi(uploadId)
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
    garderCopieLocale(video, etat.previewUrl)
    sessions.delete(uploadId)
    videoIdVersUploadId.delete(etat.videoId)
    notifierProgression()
  }
}

// Bloc envoyé jusqu'à réussite — coupure réseau (voir demande
// utilisateur : "gestion des interruptions et des ratés") : délai
// croissant entre tentatives (10 s au plus), reprise dès que le réseau
// revient, jamais abandonné de lui-même (Seb, 22/11 : 6 min sans réseau
// avaient fait perdre un combat). Seuls annulerTeleversement et un refus
// du serveur (envoi introuvable…) l'arrêtent.
function attendre(ms) {
  return new Promise((resolve) => {
    const fini = () => {
      clearTimeout(minuteur)
      window.removeEventListener('online', fini)
      resolve()
    }
    const minuteur = setTimeout(fini, ms)
    window.addEventListener('online', fini)
  })
}

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
      if (err.status >= 400 && err.status < 500 && err.status !== 408 && err.status !== 429) throw err
      tentative += 1
      await attendre(Math.min(1000 * tentative, 10000))
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
// `creer(uploadId)` : fourni par le métier, qui sait où ranger la vidéo
// (ex. dans une chorégraphie, voir api/choregraphies.js : ajouterVideo).
export async function finaliserTeleversement(uploadId, creer) {
  let video = await creer(uploadId)
  const etat = sessions.get(uploadId)
  if (etat) {
    if (etat.complet) {
      // L'envoi s'est terminé avant la réponse à "Ajouter" — le backend a
      // tout finalisé. Mais si "Ajouter" est arrivé au serveur AVANT le
      // dernier bloc, sa réponse dit encore 'en_cours', et envoyerBlocs
      // n'a rien rafraîchi (videoId pas encore connu à ce moment-là) :
      // sans ce rappel, la vidéo restait affichée « Envoi… » jusqu'au
      // rechargement (bug vu le 2026-10-15).
      sessions.delete(uploadId)
      if (video.statut === 'en_cours') video = await videosApi.obtenir(video.id)
      garderCopieLocale(video, etat.previewUrl)
    } else {
      sessions.set(uploadId, { ...etat, videoId: video.id })
      videoIdVersUploadId.set(video.id, uploadId)
      if (etat.garder) {
        const garde = (await envoisGardes()).find((e) => e.uploadId === uploadId)
        if (garde) await garderEnvoi({ ...garde, videoId: video.id })
      }
    }
    notifierProgression()
  }
  return video
}

// À l'ouverture de l'appli : reprendre les envois gardés sur ce téléphone
// (voir demarrerTeleversement, `garder`). Le serveur dit où il en est (409
// au premier bloc). Un envoi jamais rattaché à une vidéo ne sert à rien.
async function reprendreEnvois() {
  for (const { uploadId, fichier, videoId } of await envoisGardes()) {
    if (sessions.has(uploadId)) continue
    if (!videoId) {
      oublierEnvoi(uploadId)
      continue
    }
    sessions.set(uploadId, {
      octetsEnvoyes: 0,
      octetsTotal: fichier.size,
      complet: false,
      videoId,
      previewUrl: URL.createObjectURL(fichier),
      garder: true,
    })
    videoIdVersUploadId.set(videoId, uploadId)
    notifierProgression()
    envoyerBlocs(uploadId, fichier)
  }
}

if (typeof indexedDB !== 'undefined') reprendreEnvois()
