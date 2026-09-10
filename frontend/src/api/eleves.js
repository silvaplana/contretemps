// Domaine "élèves" (Admin > Élèves, voir spec/SPEC.md §6.4) — voir
// README.md pour le principe général.
//
// ⚠️ Les champs `cellulesRouges`/`ligneRouge` (surlignage en rouge, voir
// AdminEleves.jsx) ne sont PAS gérés ici : ce n'est pas une donnée
// métier, le backend n'en a aucune notion — ça reste un état purement
// local à l'écran, jamais envoyé/lu via cette couche.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

async function requete(chemin, options) {
  const reponse = await fetch(`${BASE_URL}${chemin}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!reponse.ok) throw new Error(`Requête échouée (${reponse.status})`)
  return reponse.status === 204 ? null : reponse.json()
}

// Fusionne l'élève (GET /eleves renvoie déjà nom/prenom/contacts...) avec
// ses cours (route séparée, voir GET /eleves/{id}/cours) en un seul objet
// avec coursIds.
async function avecCoursIds(eleve) {
  const cours = await requete(`/eleves/${eleve.id}/cours`)
  return {
    ...eleve,
    // Champs texte optionnels côté backend (nullable) : `?? ''` partout,
    // sinon un champ contrôlé (EditableText, voir AdminEleves.jsx) reçoit
    // `null` et React se plaint ("value prop should not be null").
    email: eleve.email ?? '',
    telephone: eleve.telephone ?? '',
    adresse: eleve.adresse ?? '',
    allergies: eleve.allergies ?? '',
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

export async function lister(ecoleId) {
  const eleves = await requete(`/eleves?ecole_id=${ecoleId}`)
  return Promise.all(eleves.map(avecCoursIds))
}

export async function creer(ecoleId, { nom, prenom }) {
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

export async function modifier(eleveId, patch) {
  const eleve = await requete(`/eleves/${eleveId}`, {
    method: 'PUT',
    body: JSON.stringify(versChampsBackend(patch)),
  })
  return avecCoursIds(eleve)
}

export async function supprimer(eleveId) {
  await requete(`/eleves/${eleveId}`, { method: 'DELETE' })
}

export async function basculerCours(eleveId, coursId) {
  const cours = await requete(`/eleves/${eleveId}/cours`)
  const inscrit = cours.some((c) => c.id === coursId)
  await requete(`/cours/${coursId}/eleves/${eleveId}`, { method: inscrit ? 'DELETE' : 'POST' })
  const eleve = await requete(`/eleves/${eleveId}`)
  return avecCoursIds(eleve)
}

export async function ajouterContact(eleveId, contact) {
  await requete(`/eleves/${eleveId}/contacts`, { method: 'POST', body: JSON.stringify(contact) })
  return avecCoursIds(await requete(`/eleves/${eleveId}`))
}

// `contactId` : toujours `contact.id` (contacts_eleves.id côté backend) —
// jamais une position dans le tableau.
export async function modifierContact(eleveId, contactId, patch) {
  await requete(`/contacts/${contactId}`, { method: 'PUT', body: JSON.stringify(patch) })
  return avecCoursIds(await requete(`/eleves/${eleveId}`))
}

export async function supprimerContact(eleveId, contactId) {
  await requete(`/contacts/${contactId}`, { method: 'DELETE' })
  return avecCoursIds(await requete(`/eleves/${eleveId}`))
}
