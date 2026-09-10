// Connexion — un seul point d'entrée (`login`) appelé par LoginScreen.

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Traduit une EcoleSortie (backend) vers la forme attendue par App.jsx.
function versEcoleEcran(e) {
  return {
    id: e.id,
    nom: e.nom,
    codePostal: e.code_postal,
    codeAccesAdmin: e.code_acces_admin,
    codeAccesProf: e.code_acces_prof,
    codeAccesEleve: e.code_acces_eleve,
  }
}

// Traduit un CompteSortie (backend, voir POST /auth/login) vers la forme
// attendue par App.jsx pour `activeUser` (id/type/nom/prenom/initiales).
// Sans ça, `activeUser` restait TOUJOURS le mock (le compte réel n'avait
// jamais cette forme) — `uploaderId` et consorts envoyaient un id fictif
// au backend (bug trouvé en testant le premier vrai upload vidéo).
function versActiveUserEcran(compte) {
  return {
    id: compte.id,
    type: compte.role,
    nom: compte.nom,
    prenom: compte.prenom,
    initiales: `${(compte.prenom[0] ?? '').toUpperCase()}${(compte.nom[0] ?? '').toUpperCase()}`,
    email: compte.email,
    telephone: compte.telephone,
    // Affiché dans Profil, admin uniquement (voir ProfilScreen.jsx) —
    // undefined pour les autres rôles, qui n'en ont pas.
    codeRecuperation: compte.code_recuperation,
  }
}

// L'appli reste mono-école côté écran (voir spec §2.1, multi-écoles
// prévu mais pas encore dans l'IHM) : on prend la première école du
// backend plutôt que de demander à l'utilisateur de la choisir —
// cohérent avec "Nouvelle école ?" qui n'en crée qu'une à la fois en
// pratique aujourd'hui.
async function resoudreEcoleReelle() {
  const reponse = await fetch(`${BASE_URL}/ecoles`)
  if (!reponse.ok) throw new Error('Impossible de contacter le backend')
  const ecoles = await reponse.json()
  if (ecoles.length === 0) {
    throw new Error('Aucune école côté backend (voir backend/README.md : python -m app.seed)')
  }
  return ecoles[0]
}

export async function login({ identifiant, code }) {
  const ecole = await resoudreEcoleReelle()
  const reponse = await fetch(`${BASE_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ecole_id: ecole.id, identifiant, code }),
  })
  if (!reponse.ok) {
    throw new Error("Identifiant ou code d'accès incorrect")
  }
  const compte = await reponse.json()
  return { compte: versActiveUserEcran(compte), ecole: versEcoleEcran(ecole) }
}

// --- "Code oublié ?" (voir spec §2.2/§2.3 et LoginScreen.jsx : CodeOublieModal).

// 1ère étape : identifie le rôle du compte visé (voir
// backend/src/auth/receiver.py: verifier_recuperation) — admin -> la
// question de récupération suit (voir repondreRecuperation) ; prof/élève
// -> juste le contact de l'admin à qui demander directement.
export async function verifierRecuperation(identifiant) {
  const ecole = await resoudreEcoleReelle()
  const reponse = await fetch(`${BASE_URL}/auth/recuperation/verifier`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ecole_id: ecole.id, identifiant }),
  })
  if (reponse.status === 404) throw new Error('Identifiant introuvable')
  if (!reponse.ok) throw new Error('Impossible de vérifier cet identifiant')
  return reponse.json()
}

// 2e étape, admin seulement : bonne réponse -> connecté direct, même
// forme que login().
export async function repondreRecuperation(identifiant, reponseTexte) {
  const ecole = await resoudreEcoleReelle()
  const reponse = await fetch(`${BASE_URL}/auth/recuperation/repondre`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ecole_id: ecole.id, identifiant, reponse: reponseTexte }),
  })
  if (reponse.status === 401) throw new Error('Réponse incorrecte')
  if (reponse.status === 404) throw new Error('Identifiant introuvable')
  if (!reponse.ok) throw new Error('Impossible de vérifier la réponse')
  const compte = await reponse.json()
  return { compte: versActiveUserEcran(compte), ecole: versEcoleEcran(ecole) }
}

// --- Bascule de profil famille (voir spec §2.2, Header.jsx : sélecteur
// famille) — le backend (auth.py) sait déjà tout faire, restait juste à
// l'appeler depuis l'écran (avant ça, cliquer un profil de la famille ne
// faisait littéralement rien en mode réel, signalé).

// Vers un rôle égal ou inférieur (voir data/roles.js : estMonteeEnPrivilege,
// même règle qu'ici côté backend) : pas de code à redemander, juste
// relire le compte visé — voir backend/src/comptes/receiver.py: obtenir.
export async function basculerLibre(versCompteId) {
  const reponse = await fetch(`${BASE_URL}/comptes/${versCompteId}`)
  if (!reponse.ok) throw new Error('Compte introuvable')
  return versActiveUserEcran(await reponse.json())
}

// Vers un rôle supérieur : le vrai code d'accès de CE rôle est redemandé
// et vérifié côté serveur (voir Header.jsx : CodeConfirmModal) — jamais
// un code fictif toujours accepté comme avant (maquette).
export async function confirmerBascule(versCompteId, code) {
  const reponse = await fetch(`${BASE_URL}/auth/bascule/confirmer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ vers_compte_id: versCompteId, code }),
  })
  if (reponse.status === 401) throw new Error('Code incorrect')
  if (!reponse.ok) throw new Error('Impossible de basculer')
  return versActiveUserEcran(await reponse.json())
}
