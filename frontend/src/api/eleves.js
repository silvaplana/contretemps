// Domaine "élèves" (Admin > Élèves, voir spec/SPEC.md §6.4) — voir
// README.md pour le principe général (maquette/réel choisis une seule
// fois par fonction, jamais dans les écrans).
//
// ⚠️ Les champs `cellulesRouges`/`ligneRouge` (surlignage en rouge, voir
// AdminEleves.jsx) ne sont PAS gérés ici : ce n'est pas une donnée
// métier, le backend n'en a aucune notion — ça reste un état purement
// local à l'écran, jamais envoyé/lu via cette couche.

import { eleves as elevesInitiaux } from '../data/mockData.js'
import { estModeDemo } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : copie mutable en mémoire, jamais le tableau original de
// mockData.js (pour repartir à l'identique à chaque rechargement de page,
// comme le useState(initialEleves) que ça remplace dans App.jsx). ---
let magasin = null
function copieProfonde(eleve) {
  return {
    ...eleve,
    coursIds: [...eleve.coursIds],
    // `id` ajouté ici (absent de mockData.js) : les écrans identifient
    // toujours un contact par `contact.id`, jamais par sa position dans
    // le tableau — même contrat qu'en mode réel (voir contacts_eleves.id
    // côté backend), pour que AdminEleves.jsx n'ait pas à distinguer les
    // deux modes.
    contactsEleve: eleve.contactsEleve.map((c, i) => ({ id: `${eleve.id}-c${i}`, ...c })),
  }
}
function lireMagasin() {
  if (magasin === null) magasin = elevesInitiaux.map(copieProfonde)
  return magasin
}
function trouverOuLever(eleveId) {
  const eleve = lireMagasin().find((e) => e.id === eleveId)
  if (!eleve) throw new Error('Élève introuvable')
  return eleve
}

async function listerMaquette() {
  return lireMagasin()
}

async function creerMaquette({ nom, prenom }) {
  const nouveau = {
    id: crypto.randomUUID(),
    nom,
    prenom,
    coursIds: [],
    statutPaiement: 'en_cours',
    montantTotalAnnee: 0,
    montantPaye: 0,
    commentaireAdmin: '',
    dateNaissance: '',
    contactsEleve: [],
    telephone: '',
    email: '',
    adresse: '',
    allergies: '',
    traitementMedical: '',
    informationsImportantes: '',
    certificatMedical: false,
  }
  lireMagasin().push(nouveau)
  return nouveau
}

async function modifierMaquette(eleveId, patch) {
  const liste = lireMagasin()
  const index = liste.findIndex((e) => e.id === eleveId)
  if (index === -1) throw new Error('Élève introuvable')
  liste[index] = { ...liste[index], ...patch }
  return liste[index]
}

async function supprimerMaquette(eleveId) {
  magasin = lireMagasin().filter((e) => e.id !== eleveId)
}

async function basculerCoursMaquette(eleveId, coursId) {
  const eleve = trouverOuLever(eleveId)
  const inscrit = eleve.coursIds.includes(coursId)
  eleve.coursIds = inscrit
    ? eleve.coursIds.filter((id) => id !== coursId)
    : [...eleve.coursIds, coursId]
  return eleve
}

async function ajouterContactMaquette(eleveId, contact) {
  const eleve = trouverOuLever(eleveId)
  eleve.contactsEleve = [...eleve.contactsEleve, { id: crypto.randomUUID(), ...contact }]
  return eleve
}

async function modifierContactMaquette(eleveId, contactId, patch) {
  const eleve = trouverOuLever(eleveId)
  eleve.contactsEleve = eleve.contactsEleve.map((c) => (c.id === contactId ? { ...c, ...patch } : c))
  return eleve
}

async function supprimerContactMaquette(eleveId, contactId) {
  const eleve = trouverOuLever(eleveId)
  eleve.contactsEleve = eleve.contactsEleve.filter((c) => c.id !== contactId)
  return eleve
}

// --- Réel : voir backend/src/eleves/receiver.py + cours/receiver.py
// (GET /eleves/{id}/cours). Pas encore exercé (mode démo par défaut,
// voir mode.js) mais tenu à jour avec les vraies routes du backend.

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// Fusionne l'élève (GET /eleves renvoie déjà nom/prenom/contacts...) avec
// ses cours (route séparée, voir GET /eleves/{id}/cours) pour reproduire
// la même forme que côté maquette (un seul objet avec coursIds).
async function avecCoursIds(eleve) {
  const cours = await requete(`/eleves/${eleve.id}/cours`)
  return {
    ...eleve,
    dateNaissance: eleve.date_naissance ?? '',
    montantTotalAnnee: eleve.montant_total_annee ?? 0,
    montantPaye: eleve.montant_paye ?? 0,
    commentaireAdmin: eleve.commentaire_admin ?? '',
    traitementMedical: eleve.traitement_medical ?? '',
    informationsImportantes: eleve.informations_importantes ?? '',
    statutPaiement: eleve.statut_paiement,
    contactsEleve: eleve.contacts,
    coursIds: cours.map((c) => c.id),
  }
}

async function listerReel(ecoleId) {
  const eleves = await requete(`/eleves?ecole_id=${ecoleId}`)
  return Promise.all(eleves.map(avecCoursIds))
}

async function creerReel(ecoleId, { nom, prenom }) {
  const eleve = await requete(`/eleves?ecole_id=${ecoleId}`, {
    method: 'POST',
    body: JSON.stringify({ nom, prenom }),
  })
  return avecCoursIds(eleve)
}

// Traduit les champs camelCase de l'écran vers les noms attendus par
// EleveModification (voir backend/src/eleves/schemas.py).
function versChampsBackend(patch) {
  const correspondance = {
    dateNaissance: 'date_naissance',
    montantTotalAnnee: 'montant_total_annee',
    montantPaye: 'montant_paye',
    commentaireAdmin: 'commentaire_admin',
    traitementMedical: 'traitement_medical',
    informationsImportantes: 'informations_importantes',
    statutPaiement: 'statut_paiement',
  }
  const resultat = {}
  for (const [cle, valeur] of Object.entries(patch)) {
    resultat[correspondance[cle] ?? cle] = valeur
  }
  return resultat
}

async function modifierReel(eleveId, patch) {
  const eleve = await requete(`/eleves/${eleveId}`, {
    method: 'PUT',
    body: JSON.stringify(versChampsBackend(patch)),
  })
  return avecCoursIds(eleve)
}

async function supprimerReel(eleveId) {
  await requete(`/eleves/${eleveId}`, { method: 'DELETE' })
}

async function basculerCoursReel(eleveId, coursId) {
  const cours = await requete(`/eleves/${eleveId}/cours`)
  const inscrit = cours.some((c) => c.id === coursId)
  await requete(`/cours/${coursId}/eleves/${eleveId}`, { method: inscrit ? 'DELETE' : 'POST' })
  const eleve = await requete(`/eleves/${eleveId}`)
  return avecCoursIds(eleve)
}

async function ajouterContactReel(eleveId, contact) {
  await requete(`/eleves/${eleveId}/contacts`, { method: 'POST', body: JSON.stringify(contact) })
  return avecCoursIds(await requete(`/eleves/${eleveId}`))
}

async function modifierContactReel(eleveId, contactId, patch) {
  await requete(`/contacts/${contactId}`, { method: 'PUT', body: JSON.stringify(patch) })
  return avecCoursIds(await requete(`/eleves/${eleveId}`))
}

async function supprimerContactReel(eleveId, contactId) {
  await requete(`/contacts/${contactId}`, { method: 'DELETE' })
  return avecCoursIds(await requete(`/eleves/${eleveId}`))
}

// --- Point d'entrée unique, appelé par les écrans (voir AdminEleves.jsx) ---

export async function lister(ecoleId) {
  return estModeDemo() ? listerMaquette() : listerReel(ecoleId)
}

export async function creer(ecoleId, donnees) {
  return estModeDemo() ? creerMaquette(donnees) : creerReel(ecoleId, donnees)
}

export async function modifier(eleveId, patch) {
  return estModeDemo() ? modifierMaquette(eleveId, patch) : modifierReel(eleveId, patch)
}

export async function supprimer(eleveId) {
  return estModeDemo() ? supprimerMaquette(eleveId) : supprimerReel(eleveId)
}

export async function basculerCours(eleveId, coursId) {
  return estModeDemo() ? basculerCoursMaquette(eleveId, coursId) : basculerCoursReel(eleveId, coursId)
}

export async function ajouterContact(eleveId, contact) {
  return estModeDemo() ? ajouterContactMaquette(eleveId, contact) : ajouterContactReel(eleveId, contact)
}

// `contactId` : toujours `contact.id` (voir copieProfonde/ajouterContact*
// côté maquette, contacts_eleves.id côté réel) — jamais une position
// dans le tableau, pour que AdminEleves.jsx n'ait rien à distinguer.
export async function modifierContact(eleveId, contactId, patch) {
  return estModeDemo()
    ? modifierContactMaquette(eleveId, contactId, patch)
    : modifierContactReel(eleveId, contactId, patch)
}

export async function supprimerContact(eleveId, contactId) {
  return estModeDemo()
    ? supprimerContactMaquette(eleveId, contactId)
    : supprimerContactReel(eleveId, contactId)
}
