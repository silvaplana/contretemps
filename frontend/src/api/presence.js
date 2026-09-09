// Domaine "présence" (Présence + Comptage d'heures, voir spec/SPEC.md
// §6.6) — voir api/README.md pour le principe général.
//
// ⚠️ Le modèle mock (`{dates, parEleve, parProf}`, des tableaux parallèles
// SANS année — voir data/mockData.js et HeuresScreen.jsx) est plus simple
// que le modèle backend (des séances normalisées, une vraie date par
// séance, voir backend/src/presence/models.py). La couche réelle fait le
// pont : elle reconstruit ce même objet `{dates, parEleve, parProf}` à
// partir des séances, `dates` perdant l'année (limite déjà documentée
// dans HeuresScreen.jsx — "à corriger le jour où les dates portent une
// année"). Les écrans ne voient jamais la différence.

import { presencesParCours } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : copie mutable en mémoire, jamais l'objet original de
// mockData.js (voir eleves.js pour la même logique, plus détaillée). ---
let magasin = null
function copieProfonde(donnees) {
  return {
    dates: [...donnees.dates],
    parEleve: Object.fromEntries(Object.entries(donnees.parEleve).map(([id, l]) => [id, [...l]])),
    parProf: Object.fromEntries(
      Object.entries(donnees.parProf).map(([id, l]) => [id, l.map((h) => ({ ...h }))]),
    ),
  }
}
function lireMagasin() {
  if (magasin === null) {
    magasin = Object.fromEntries(
      Object.entries(presencesParCours).map(([coursId, d]) => [coursId, copieProfonde(d)]),
    )
  }
  return magasin
}
function coursMaquette(coursId) {
  const m = lireMagasin()
  if (!m[coursId]) m[coursId] = { dates: [], parEleve: {}, parProf: {} }
  return m[coursId]
}

// 'YYYY-MM-DD' -> 'JJ/MM' (voir PresenceScreen.jsx : même format déjà
// utilisé pour les colonnes de la table).
function versLabelAffiche(dateIso) {
  const [, mois, jour] = dateIso.split('-')
  return `${jour}/${mois}`
}

async function listerToutMaquette() {
  return lireMagasin()
}

async function ajouterDateMaquette(coursId, dateIso) {
  const c = coursMaquette(coursId)
  const label = versLabelAffiche(dateIso)
  if (!c.dates.includes(label)) c.dates.push(label)
  return c
}

async function definirStatutEleveMaquette(coursId, eleveId, index, statut) {
  const c = coursMaquette(coursId)
  const historique = c.parEleve[eleveId] ?? c.dates.map(() => 'present')
  historique[index] = statut
  c.parEleve[eleveId] = historique
  return c
}

async function definirHeureProfMaquette(coursId, profId, index, champ, valeur) {
  const c = coursMaquette(coursId)
  const historique =
    c.parProf[profId] ?? c.dates.map(() => ({ heureDebutReelle: '', heureFinReelle: '', depassementMinutes: '' }))
  historique[index] = { ...historique[index], [champ]: valeur }
  c.parProf[profId] = historique
  return c
}

// --- Réel : voir backend/src/presence/receiver.py. Pas encore exercé
// (mode démo par défaut, voir mode.js) mais tenu à jour avec les vraies
// routes — plus coûteux en requêtes (N+1, un cours a plusieurs séances,
// chacune a ses élèves/profs à part) mais correct, la performance n'est
// pas le sujet tant que ce chemin n'est pas vraiment utilisé.

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// Séances d'un cours, triées du plus ancien au plus récent (déjà l'ordre
// renvoyé par le backend, voir Presence.lister_seances) — l'ORDRE fait
// foi pour les `index` utilisés partout ailleurs dans ce fichier.
async function seancesDuCours(coursId) {
  return requete(`/cours/${coursId}/seances`)
}

async function coursReel(coursId) {
  const seances = await seancesDuCours(coursId)
  const dates = seances.map((s) => versLabelAffiche(s.date))
  const parEleve = {}
  const parProf = {}
  for (const seance of seances) {
    const eleves = await requete(`/seances/${seance.id}/eleves`)
    for (const pe of eleves) {
      if (!parEleve[pe.eleve_id]) parEleve[pe.eleve_id] = dates.map(() => 'present')
      parEleve[pe.eleve_id][dates.indexOf(versLabelAffiche(seance.date))] = pe.statut
    }
    const profs = await requete(`/seances/${seance.id}/profs`)
    for (const pp of profs) {
      if (!parProf[pp.professeur_id]) {
        parProf[pp.professeur_id] = dates.map(() => ({
          heureDebutReelle: '',
          heureFinReelle: '',
          depassementMinutes: '',
        }))
      }
      parProf[pp.professeur_id][dates.indexOf(versLabelAffiche(seance.date))] = {
        heureDebutReelle: pp.heure_debut_reelle ?? '',
        heureFinReelle: pp.heure_fin_reelle ?? '',
        depassementMinutes: pp.depassement_minutes ?? '',
      }
    }
  }
  return { dates, parEleve, parProf }
}

async function listerToutReel(coursIds) {
  const resultat = {}
  for (const coursId of coursIds) {
    resultat[coursId] = await coursReel(coursId)
  }
  return resultat
}

async function ajouterDateReel(coursId, dateIso) {
  await requete(`/cours/${coursId}/seances`, { method: 'POST', body: JSON.stringify({ date: dateIso }) })
  return coursReel(coursId)
}

async function definirStatutEleveReel(coursId, eleveId, index, statut) {
  const seances = await seancesDuCours(coursId)
  const seance = seances[index]
  if (!seance) throw new Error('Séance introuvable')
  await requete(`/seances/${seance.id}/eleves/${eleveId}`, {
    method: 'PUT',
    body: JSON.stringify({ statut }),
  })
  return coursReel(coursId)
}

async function definirHeureProfReel(coursId, profId, index, champ, valeur) {
  const seances = await seancesDuCours(coursId)
  const seance = seances[index]
  if (!seance) throw new Error('Séance introuvable')
  const correspondance = {
    heureDebutReelle: 'heure_debut_reelle',
    heureFinReelle: 'heure_fin_reelle',
    depassementMinutes: 'depassement_minutes',
  }
  await requete(`/seances/${seance.id}/profs/${profId}`, {
    method: 'PUT',
    body: JSON.stringify({ [correspondance[champ]]: valeur }),
  })
  return coursReel(coursId)
}

// --- Point d'entrée unique, appelé par App.jsx (voir PresenceScreen.jsx
// et HeuresScreen.jsx, qui consomment `presences[coursId]`). ---

export async function listerTout(coursIds) {
  return estModeDemo() ? listerToutMaquette() : listerToutReel(coursIds)
}

export async function ajouterDate(coursId, dateIso) {
  return estModeDemo() ? ajouterDateMaquette(coursId, dateIso) : ajouterDateReel(coursId, dateIso)
}

export async function definirStatutEleve(coursId, eleveId, index, statut) {
  return estModeDemo()
    ? definirStatutEleveMaquette(coursId, eleveId, index, statut)
    : definirStatutEleveReel(coursId, eleveId, index, statut)
}

export async function definirHeureProf(coursId, profId, index, champ, valeur) {
  return estModeDemo()
    ? definirHeureProfMaquette(coursId, profId, index, champ, valeur)
    : definirHeureProfReel(coursId, profId, index, champ, valeur)
}
