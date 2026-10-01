// Connexion par mot de passe (voir spec/SPEC.md §2.2) : connexion, reprise
// de session, bascule de profil famille, liens reçus par mail (invitation,
// mot de passe oublié), changement de mot de passe.

import { isSuperuser } from '../data/roles.js'
import * as session from './session.js'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

// Traduit une EcolePublique (backend, GET /ecoles) vers la forme attendue
// par App.jsx.
function versEcoleEcran(e) {
  return {
    id: e.id,
    nom: e.nom,
    codePostal: e.code_postal,
  }
}

// Traduit un compte (backend) vers la forme attendue par App.jsx pour
// `activeUser` (id/type/nom/prenom/initiales).
function versActiveUserEcran(compte) {
  return {
    id: compte.id,
    ecoleId: compte.ecole_id,
    // `type` = rôle principal (libellé, rang) ; `roles` = tous ses rôles,
    // à tester via data/roles.js (isAdmin, isProf...) pour les droits.
    type: compte.role,
    roles: compte.roles,
    nom: compte.nom,
    prenom: compte.prenom,
    initiales: `${(compte.prenom[0] ?? '').toUpperCase()}${(compte.nom[0] ?? '').toUpperCase()}`,
    email: compte.email,
    telephone: compte.telephone,
  }
}

async function poster(chemin, corps) {
  return fetch(`${BASE_URL}${chemin}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(corps),
  })
}

// Message lisible renvoyé par le serveur, sinon `defaut`.
async function messageErreur(reponse, defaut) {
  const corps = await reponse.json().catch(() => null)
  const detail = corps?.detail
  if (typeof detail === 'string') return detail
  if (typeof detail?.message === 'string') return detail.message
  return defaut
}

// --- Écoles ---

export async function listerEcoles() {
  const reponse = await fetch(`${BASE_URL}/ecoles`)
  if (!reponse.ok) throw new Error('Impossible de charger les écoles')
  return (await reponse.json()).map(versEcoleEcran)
}

// L'école d'une fiche. La connexion cherche dans TOUTES les écoles
// (§2.2) : plus question de prendre « la première du serveur ». La liste
// publique (nom et code postal seulement) suffit.
async function ecoleDe(ecoleId) {
  if (ecoleId == null) return null
  return (await listerEcoles()).find((e) => e.id === ecoleId) ?? null
}

// Session ouverte par le serveur ({ compte, jeton }) -> ce qu'attend
// App.jsx ({ compte, ecole }). Le jeton est retenu AVANT toute autre
// requête, pour que la suivante l'emporte déjà (voir api/identite.js).
async function ouvrir({ compte, jeton }) {
  const activeUser = versActiveUserEcran(compte)
  session.ouvrirSession(activeUser.id, jeton)
  // Le Superuser n'appartient à aucune école : il reprend celle qu'il
  // avait choisie, ou en choisira une (voir ChoixEcoleScreen.jsx).
  const ecoleId = isSuperuser(activeUser) ? session.lireEcoleChoisie() : activeUser.ecoleId
  return { compte: activeUser, ecole: await ecoleDe(ecoleId).catch(() => null) }
}

// --- Connexion ---

// Renvoie { compte, ecole }, ou { choix: [...] } quand plusieurs écoles
// sont possibles pour cet identifiant et ce mot de passe (« Choisissez
// votre école ») : rappeler alors avec `compteId`.
export async function login({ identifiant, motDePasse, compteId = null }) {
  const reponse = await poster('/auth/login', { identifiant, mot_de_passe: motDePasse, compte_id: compteId })
  if (!reponse.ok) throw new Error(await messageErreur(reponse, 'Identifiant ou mot de passe incorrect'))
  const resultat = await reponse.json()
  if (!resultat.compte) {
    return {
      choix: resultat.choix.map((c) => ({
        compteId: c.compte_id,
        ecoleNom: c.ecole_nom,
        prenom: c.prenom,
        nom: c.nom,
        role: c.role,
      })),
    }
  }
  return ouvrir(resultat)
}

// --- Session persistante (voir spec §2.2 : "sans reconnexion
// systématique") — App.jsx mémorise le profil actif et son jeton (voir
// api/session.js) et les relit ici au prochain démarrage de l'appli, pour
// resauter l'écran de connexion. Échoue si le jeton a expiré (30 jours
// sans usage, 12 heures pour le Superuser) ou si le mot de passe a changé.
export async function restaurerSession(compteId) {
  session.ouvrirSession(compteId, session.jetonEnCours())
  const reponse = await fetch(`${BASE_URL}/comptes/${compteId}`)
  if (!reponse.ok) throw new Error('Session expirée')
  return ouvrir({ compte: await reponse.json(), jeton: null })
}

// --- Bascule de profil famille (voir spec §2.2, Header.jsx : sélecteur
// famille). Libre vers un rang égal ou inférieur ; une montée en privilège
// redemande le mot de passe (`motDePasse`), vérifié par le serveur. La
// session prend le rang du nouveau profil : le jeton est remplacé.
export async function basculer(versCompteId, motDePasse = null) {
  const reponse = await poster('/auth/bascule', { vers_compte_id: versCompteId, mot_de_passe: motDePasse })
  if (reponse.status === 401) throw new Error('Mot de passe incorrect')
  if (!reponse.ok) throw new Error(await messageErreur(reponse, 'Impossible de basculer'))
  const { compte, jeton } = await reponse.json()
  session.remplacerJeton(jeton)
  session.ouvrirSession(compte.id, jeton)
  return versActiveUserEcran(compte)
}

// --- Mot de passe oublié, et liens reçus par mail ---

// Toujours la même réponse, qu'un compte existe ou non (§2.2).
export async function motDePasseOublie(identifiant) {
  const reponse = await poster('/auth/mot-de-passe-oublie', { identifiant })
  if (!reponse.ok) throw new Error('Demande impossible pour le moment')
}

// Ce qu'affiche « Créer mon mot de passe » / « Nouveau mot de passe ».
// L'appeler, c'est aussi signaler au serveur que l'invitation a été
// consultée (§2.2 : « Suivi de l'invitation »).
export async function lireLien(jeton) {
  const reponse = await fetch(`${BASE_URL}/auth/liens/${encodeURIComponent(jeton)}`)
  if (!reponse.ok) throw new Error(await messageErreur(reponse, "Ce lien n'est plus valable"))
  const lien = await reponse.json()
  return {
    type: lien.type,
    email: lien.email,
    destinataire: lien.destinataire,
    prenoms: lien.prenoms,
    ecoleNom: lien.ecole_nom,
  }
}

// Crée le mot de passe ; la personne est ensuite connectée directement
// (même forme de retour que login()). `null` si plus aucune fiche ne porte
// cet email dans la saison courante.
export async function definirMotDePasse(jeton, motDePasse) {
  const reponse = await poster(`/auth/liens/${encodeURIComponent(jeton)}/mot-de-passe`, {
    mot_de_passe: motDePasse,
  })
  if (!reponse.ok) throw new Error(await messageErreur(reponse, 'Mot de passe refusé'))
  const resultat = await reponse.json()
  return resultat.compte ? ouvrir(resultat) : null
}

// Depuis Profil : l'ancien mot de passe est redemandé. Les autres appareils
// sont déconnectés ; celui-ci reçoit un jeton neuf.
export async function changerMotDePasse(ancien, nouveau) {
  const reponse = await poster('/auth/mot-de-passe', { ancien, nouveau })
  if (reponse.status === 401) throw new Error('Mot de passe actuel incorrect')
  if (!reponse.ok) throw new Error(await messageErreur(reponse, 'Mot de passe refusé'))
  session.remplacerJeton((await reponse.json()).jeton)
}

// « Appli installée » (§2.2) : signalé par l'appli elle-même, voir
// api/installation.js. Sans importance si ça échoue.
export async function signalerAppliInstallee() {
  if (!session.jetonEnCours()) return
  await poster('/auth/appli-installee', {}).catch(() => {})
}

// --- Invitations et suivi de l'accès (admins, §2.2) ---

// { [compteId]: { statut, date } } pour toutes les fiches de l'école.
export async function statutsAcces(ecoleId) {
  const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}/acces`)
  if (!reponse.ok) throw new Error('Impossible de charger les statuts')
  return reponse.json()
}

// Un seul mail par adresse, même pour plusieurs profils. Renvoie
// { emails, enCours } : pour plusieurs adresses, les mails partent en tâche
// de fond et les statuts se mettent à jour au fil de l'eau.
export async function inviter(ecoleId, compteIds) {
  const reponse = await poster(`/ecoles/${ecoleId}/invitations`, { compte_ids: compteIds })
  if (!reponse.ok) throw new Error(await messageErreur(reponse, "L'invitation n'a pas pu être envoyée"))
  const resultat = await reponse.json()
  return { emails: resultat.emails, enCours: resultat.en_cours }
}

// --- Superuser (§2.5) : création d'une école ---

export async function creerEcole({ nom, codePostal }) {
  const reponse = await poster('/ecoles', { nom, code_postal: codePostal })
  if (reponse.status === 409) throw new Error('Une école avec ce nom et ce code postal existe déjà')
  if (!reponse.ok) throw new Error('Impossible de créer l’école')
  return versEcoleEcran(await reponse.json())
}
