// Domaine "école" (Admin > École, voir spec/SPEC.md §5.1.1 et §6.1) — voir
// api/README.md pour le principe général.
//
// L'appli reste mono-école côté écran (voir auth.js : resoudreEcoleReelle),
// donc pas de lister()/creer() ici — juste modifier() et tout ce qui
// touche à "Sauvegarder École" (voir SauvegardeEcoleMenu.jsx) : les 2
// exports (humain + technique), la sauvegarde programmée, son historique
// serveur, la suppression et la restauration des données.

import { envoyerFichierVersDrive, telechargerFichier } from '../utils/telechargement.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

function versEcran(e) {
  return {
    id: e.id,
    nom: e.nom,
    codePostal: e.code_postal,
    codeAccesAdmin: e.code_acces_admin,
    codeAccesProf: e.code_acces_prof,
    codeAccesEleve: e.code_acces_eleve,
    sauvegardeActive: e.sauvegarde_active,
    sauvegardePeriodicite: e.sauvegarde_periodicite,
    sauvegardeJourSemaine: e.sauvegarde_jour_semaine,
    sauvegardeHeure: e.sauvegarde_heure,
    sauvegardeDerniereExecution: e.sauvegarde_derniere_execution,
  }
}

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// École COMPLÈTE (codes d'accès, réglages de sauvegarde) — réservée aux
// admins de l'école côté serveur. La liste publique utilisée à la
// connexion (voir api/auth.js) ne les donne plus : elle les exposait à
// n'importe qui jusqu'au 2026-09-21.
export async function obtenir(ecoleId) {
  return versEcran(await requete(`/ecoles/${ecoleId}`))
}

export async function modifier(ecoleId, patch) {
  const corps = {
    ...(patch.nom !== undefined && { nom: patch.nom }),
    ...(patch.codePostal !== undefined && { code_postal: patch.codePostal }),
    ...(patch.codeAccesAdmin !== undefined && { code_acces_admin: patch.codeAccesAdmin }),
    ...(patch.codeAccesProf !== undefined && { code_acces_prof: patch.codeAccesProf }),
    ...(patch.codeAccesEleve !== undefined && { code_acces_eleve: patch.codeAccesEleve }),
  }
  return versEcran(await requete(`/ecoles/${ecoleId}`, { method: 'PUT', body: JSON.stringify(corps) }))
}

// --- "Sauvegarder École" (menu ⋮, voir SauvegardeEcoleMenu.jsx) ---

// Les 2 fichiers (voir ecoles/excel_export.py — humain — et
// ecoles/backup_technique.py — technique). `destination` : 'local'
// (choix de l'emplacement, voir utils/telechargement.js) ou 'drive' (voir
// utils/googleDrive.js — compte Google PERSONNEL de l'admin, décision
// utilisateur explicite ; distinct du compte de service utilisé côté
// serveur pour la sauvegarde programmée) — mémorisé dans le navigateur,
// voir SauvegardeEcoleMenu.jsx.
export async function telechargerExportHumain(ecoleId, destination = 'local') {
  const url = `${BASE_URL}/ecoles/${ecoleId}/export`
  if (destination === 'drive') await envoyerFichierVersDrive(url, 'export.xlsx')
  else await telechargerFichier(url, 'export.xlsx')
}

export async function telechargerExportTechnique(ecoleId, destination = 'local') {
  const url = `${BASE_URL}/ecoles/${ecoleId}/export-technique`
  if (destination === 'drive') await envoyerFichierVersDrive(url, 'sauvegarde_technique.xlsx')
  else await telechargerFichier(url, 'sauvegarde_technique.xlsx')
}

// --- "Programmer sauvegarde École" ---

export async function programmerSauvegarde(ecoleId, { active, periodicite, jourSemaine, heure }) {
  return versEcran(
    await requete(`/ecoles/${ecoleId}/sauvegarde-programmee`, {
      method: 'PUT',
      body: JSON.stringify({
        active,
        periodicite,
        jour_semaine: jourSemaine ?? null,
        heure: heure ?? null,
      }),
    }),
  )
}

// Historique des sauvegardes générées par le worker programmé (filet de
// sécurité serveur, voir backend/src/app/sauvegarde_worker.py) —
// téléchargeables à la demande, même mécanisme de choix d'emplacement.
export async function listerSauvegardesServeur(ecoleId) {
  const liste = await requete(`/ecoles/${ecoleId}/sauvegardes`)
  return liste.map((s) => ({ nom: s.nom, date: s.date, tailleOctets: s.taille_octets }))
}

export async function telechargerSauvegardeServeur(ecoleId, nomFichier) {
  await telechargerFichier(`${BASE_URL}/ecoles/${ecoleId}/sauvegardes/${nomFichier}`, nomFichier)
}

// --- "Supprimer Données École" ---

export async function supprimerDonnees(ecoleId) {
  const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}/donnees`, { method: 'DELETE' })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
}

// --- "Importer sauvegarde" ---

export async function restaurer(ecoleId, fichier) {
  const donnees = new FormData()
  donnees.append('fichier', fichier)
  const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}/restaurer`, { method: 'POST', body: donnees })
  if (!reponse.ok) {
    const detail = await reponse.json().catch(() => null)
    throw new Error(detail?.detail ?? `Requête échouée (${reponse.status})`)
  }
}
