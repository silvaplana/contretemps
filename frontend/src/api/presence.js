// Domaine "présence" (Présence + Comptage d'heures, voir spec/SPEC.md
// §6.6) — voir api/README.md pour le principe général.
//
// ⚠️ Le modèle attendu par les écrans (`{dates, parEleve, parProf}`, des
// tableaux parallèles SANS année — voir HeuresScreen.jsx) est plus
// simple que le modèle backend (des séances normalisées, une vraie date
// par séance, voir backend/src/presence/models.py). Ce module fait le
// pont : il reconstruit ce même objet `{dates, parEleve, parProf}` à
// partir des séances, `dates` perdant l'année (limite déjà documentée
// dans HeuresScreen.jsx — "à corriger le jour où les dates portent une
// année"). Les écrans ne voient jamais la différence.
//
// Plus coûteux en requêtes (N+1, un cours a plusieurs séances, chacune a
// ses élèves/profs à part) mais correct — la performance n'est pas le
// sujet tant que ce chemin n'est pas massivement utilisé.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// 'YYYY-MM-DD' -> 'JJ/MM' (voir PresenceScreen.jsx : même format déjà
// utilisé pour les colonnes de la table).
function versLabelAffiche(dateIso) {
  const [, mois, jour] = dateIso.split('-')
  return `${jour}/${mois}`
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

// --- Point d'entrée unique, appelé par App.jsx (voir PresenceScreen.jsx
// et HeuresScreen.jsx, qui consomment `presences[coursId]`). ---

export async function listerTout(coursIds) {
  const resultat = {}
  for (const coursId of coursIds) {
    resultat[coursId] = await coursReel(coursId)
  }
  return resultat
}

export async function ajouterDate(coursId, dateIso) {
  await requete(`/cours/${coursId}/seances`, { method: 'POST', body: JSON.stringify({ date: dateIso }) })
  return coursReel(coursId)
}

export async function definirStatutEleve(coursId, eleveId, index, statut) {
  const seances = await seancesDuCours(coursId)
  const seance = seances[index]
  if (!seance) throw new Error('Séance introuvable')
  await requete(`/seances/${seance.id}/eleves/${eleveId}`, {
    method: 'PUT',
    body: JSON.stringify({ statut }),
  })
  return coursReel(coursId)
}

export async function definirHeureProf(coursId, profId, index, champ, valeur) {
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
