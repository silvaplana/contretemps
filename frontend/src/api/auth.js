// Connexion — un seul point d'entrée (`login`) appelé par LoginScreen.

import { isSuperuser } from '../data/roles.js'
import { lireEcoleChoisie, sauvegarderJeton } from './session.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Traduit une EcolePublique (backend, GET /ecoles) vers la forme attendue
// par App.jsx. Pas de codes d'accès : la liste publique ne les donne plus
// (ils ne sont chargés que par Admin > École, voir api/ecoles.js : obtenir).
function versEcoleEcran(e) {
  return {
    id: e.id,
    nom: e.nom,
    codePostal: e.code_postal,
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
    // `type` = rôle principal (libellé, rang) ; `roles` = tous ses rôles,
    // à tester via data/roles.js (isAdmin, isProf...) pour les droits.
    type: compte.role,
    roles: compte.roles,
    nom: compte.nom,
    prenom: compte.prenom,
    initiales: `${(compte.prenom[0] ?? '').toUpperCase()}${(compte.nom[0] ?? '').toUpperCase()}`,
    email: compte.email,
    telephone: compte.telephone,
    // Profil admin (voir ProfilScreen.jsx) : le serveur ne renvoie JAMAIS
    // la valeur du code de récupération (elle suffit à se connecter en
    // admin via "Code oublié ?"), seulement s'il est défini.
    codeRecuperationDefini: compte.code_recuperation_defini,
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
  // Jeton signé du Superuser (§2.5) — enregistré AVANT toute autre
  // requête, pour que la suivante l'emporte déjà (voir api/identite.js).
  // Effacé pour un compte d'école : pas de vieux jeton qui traîne.
  sauvegarderJeton(compte.jeton ?? null)
  const activeUser = versActiveUserEcran(compte)
  // Le Superuser n'appartient à aucune école : il en choisira une (voir
  // ChoixEcoleScreen.jsx), `ecole: null` en attendant.
  if (isSuperuser(activeUser)) return { compte: activeUser, ecole: null }
  return { compte: activeUser, ecole: versEcoleEcran(ecole) }
}

// --- Superuser (§2.5) : choix et création d'une école ---

export async function listerEcoles() {
  const reponse = await fetch(`${BASE_URL}/ecoles`)
  if (!reponse.ok) throw new Error('Impossible de charger les écoles')
  return (await reponse.json()).map(versEcoleEcran)
}

async function chargerEcole(ecoleId) {
  const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}`)
  if (!reponse.ok) throw new Error('École introuvable')
  return versEcoleEcran(await reponse.json())
}

// Réservé au Superuser côté serveur. Les codes d'accès sont libres, comme à
// la création d'une école depuis l'écran de connexion (§2.3).
export async function creerEcole({ nom, codePostal, codeAccesAdmin, codeAccesProf, codeAccesEleve }) {
  const reponse = await fetch(`${BASE_URL}/ecoles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      nom,
      code_postal: codePostal,
      code_acces_admin: codeAccesAdmin,
      code_acces_prof: codeAccesProf,
      code_acces_eleve: codeAccesEleve,
    }),
  })
  if (reponse.status === 409) throw new Error('Une école avec ce nom et ce code postal existe déjà')
  if (!reponse.ok) throw new Error('Impossible de créer l’école')
  return versEcoleEcran(await reponse.json())
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
  // Toujours un compte d'école ici : aucun jeton Superuser ne doit rester.
  sauvegarderJeton(null)
  return { compte: versActiveUserEcran(compte), ecole: versEcoleEcran(ecole) }
}

// --- Bascule de profil famille (voir spec §2.2, Header.jsx : sélecteur
// famille) — le backend (auth.py) sait déjà tout faire, restait juste à
// l'appeler depuis l'écran (avant ça, cliquer un profil de la famille ne
// faisait littéralement rien en mode réel, signalé).

async function recupererCompteActiveUser(compteId) {
  const reponse = await fetch(`${BASE_URL}/comptes/${compteId}`)
  if (!reponse.ok) throw new Error('Compte introuvable')
  return versActiveUserEcran(await reponse.json())
}

// Vers un rôle égal ou inférieur (voir data/roles.js : estMonteeEnPrivilege,
// même règle qu'ici côté backend) : pas de code à redemander, juste
// relire le compte visé — voir backend/src/comptes/receiver.py: obtenir.
export async function basculerLibre(versCompteId) {
  return recupererCompteActiveUser(versCompteId)
}

// --- Session persistante (voir spec §2.2 : "sans reconnexion
// systématique") — App.jsx enregistre l'id du profil actif à chaque
// connexion/bascule (voir api/session.js) et le relit ici au prochain
// démarrage de l'appli, pour resauter l'écran de connexion. Même forme
// de retour que login() ({compte, ecole}) : App.jsx traite les deux cas
// de façon identique.
export async function restaurerSession(compteId) {
  // Superuser : son compte n'est lisible qu'avec un jeton valide (voir
  // backend comptes/receiver.py) — jeton expiré (12 h) = retour à l'écran
  // de connexion, comme voulu. Son école est celle qu'il avait choisie.
  const compte = await recupererCompteActiveUser(compteId)
  if (isSuperuser(compte)) {
    const ecoleId = lireEcoleChoisie()
    return { compte, ecole: ecoleId ? await chargerEcole(ecoleId).catch(() => null) : null }
  }
  const ecole = await resoudreEcoleReelle()
  return { compte, ecole: versEcoleEcran(ecole) }
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
