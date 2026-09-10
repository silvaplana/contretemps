// Connexion — un seul point d'entrée (`login`) appelé par LoginScreen.
// Le mode n'est plus un interrupteur séparé : c'est le bouton cliqué qui
// décide, une fois pour toute la session — "Se connecter" (login) est
// TOUJOURS réel, "Voir une maquette" (voirMaquette) est TOUJOURS la
// maquette. Chacun fixe mode.js lui-même (voir activerModeReel/
// activerModeDemo) avant que les autres domaines (api/eleves.js etc.)
// ne consultent estModeDemo().

import { currentUser } from '../data/mockData.js'
import { activerModeDemo, activerModeReel } from './mode.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// --- Maquette : ne contacte jamais le réseau, toujours disponible. ---
async function loginMaquette() {
  return { compte: currentUser, ecole: null, modeDemo: true }
}

// --- Réel : POST /auth/login (voir backend/src/auth/receiver.py). ---

// Traduit une EcoleSortie (backend) vers la forme attendue par App.jsx
// (voir data/mockData.js : ecoleActuelle).
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
// attendue par App.jsx pour `activeUser` (voir data/mockData.js :
// familleActuelle/currentUser — même forme : id/type/nom/prenom/
// initiales). Sans ça, `activeUser` restait TOUJOURS le mock en mode
// réel (le compte réel n'avait jamais cette forme) — `uploaderId` et
// consorts envoyaient un id fictif au backend (bug trouvé en testant le
// premier vrai upload vidéo).
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
// prévu mais pas encore dans l'IHM) : en mode réel, on prend la
// première école du backend plutôt que de demander à l'utilisateur de
// la choisir — cohérent avec "Nouvelle école ?" qui n'en crée qu'une à
// la fois en pratique aujourd'hui.
async function resoudreEcoleReelle() {
  const reponse = await fetch(`${BASE_URL}/ecoles`)
  if (!reponse.ok) throw new Error('Impossible de contacter le backend')
  const ecoles = await reponse.json()
  if (ecoles.length === 0) {
    throw new Error('Aucune école côté backend (voir backend/README.md : python -m app.seed)')
  }
  return ecoles[0]
}

async function loginReel({ identifiant, code }) {
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
  return { compte: versActiveUserEcran(compte), ecole: versEcoleEcran(ecole), modeDemo: false }
}

export async function login(identifiants) {
  const resultat = await loginReel(identifiants)
  activerModeReel()
  return resultat
}

export async function voirMaquette() {
  activerModeDemo()
  return loginMaquette()
}

// --- "Code oublié ?" (voir spec §2.2/§2.3 et LoginScreen.jsx :
// CodeOublieModal) — réel uniquement : "Se connecter" et "Code oublié ?"
// parlent tous les deux toujours au vrai backend, il n'y a plus de bouton
// "Voir une maquette" pour entrer dans la maquette depuis cet écran.

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
  activerModeReel()
  return { compte: versActiveUserEcran(compte), ecole: versEcoleEcran(ecole), modeDemo: false }
}
