// Apparence de l'école (spec §2.7, §5.1.1) : couleurs, police, logo, nom,
// slogan, nom sous l'icône. Lue avant toute connexion d'après l'adresse
// visitée (`chargerParAdresse`), puis celle de l'école du compte connecté
// (`chargerEcole`). Appliquée à toute l'appli : variables CSS de `:root`,
// et lue par Logo.jsx et LoginScreen.jsx.

import { useSyncExternalStore } from 'react'

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export const POLICES = [
  { cle: '', nom: 'Système', famille: "system-ui, 'Segoe UI', Roboto, sans-serif" },
  { cle: 'montserrat', nom: 'Montserrat', famille: "'Montserrat', system-ui, sans-serif" },
  { cle: 'poppins', nom: 'Poppins', famille: "'Poppins', system-ui, sans-serif" },
  { cle: 'nunito', nom: 'Nunito', famille: "'Nunito', system-ui, sans-serif" },
  { cle: 'josefin-sans', nom: 'Josefin Sans', famille: "'Josefin Sans', system-ui, sans-serif" },
  { cle: 'playfair-display', nom: 'Playfair Display', famille: "'Playfair Display', Georgia, serif" },
]

// Police du nom de l'école écrit en texte : vide = celle de l'appli. En plus
// des précédentes, une écriture manuscrite (celle du site de l'école),
// réservée au nom : illisible pour des textes courants.
export const POLICES_NOM = [
  { cle: '', nom: 'Comme l’appli', famille: null },
  { cle: 'great-vibes', nom: 'Great Vibes', famille: "'Great Vibes', cursive" },
  ...POLICES.slice(1),
]

export function familleDuNom(apparence) {
  const police = POLICES_NOM.find((p) => p.cle === (apparence.policeNom ?? ''))
  return police?.famille ?? undefined
}

export const DEFAUT = {
  ecoleId: null,
  nom: 'Contretemps',
  nomAppli: 'Contretemps',
  nomMode: 'texte',
  slogan: "Gestion d'école de danse du cours au gala",
  couleurFond: '#FDECD8',
  couleurTexte: '#3A2410',
  couleurAccent: '#D8722A',
  police: null,
  policeNom: null,
  logoPersonnalise: false,
  nomImage: false,
  version: 0,
  sousDomaine: null,
  adresse: null,
}

export function versEcran(v) {
  return {
    ecoleId: v.ecole_id,
    nom: v.nom,
    nomAppli: v.nom_appli,
    nomMode: v.nom_mode,
    slogan: v.slogan,
    couleurFond: v.couleur_fond,
    couleurTexte: v.couleur_texte,
    couleurAccent: v.couleur_accent,
    police: v.police,
    policeNom: v.police_nom,
    logoPersonnalise: v.logo_personnalise,
    nomImage: v.nom_image,
    version: v.version,
    sousDomaine: v.sous_domaine,
    adresse: v.adresse,
    redirigeVers: v.redirige_vers ?? null,
    detouragesDisponibles: v.detourages_disponibles,
  }
}

// --- Adresses des images ---

export function urlFichier(ecoleId, fichier, version) {
  return `${BASE_URL}/ecoles/${ecoleId}/personnalisation/${fichier}${version ? `?v=${version}` : ''}`
}

export function urlLogo(apparence) {
  if (!apparence.logoPersonnalise || !apparence.ecoleId) return `${import.meta.env.BASE_URL}images/logo-contretemps.png`
  return urlFichier(apparence.ecoleId, 'logo.png', apparence.version)
}

export function urlNomImage(apparence) {
  return apparence.nomImage && apparence.ecoleId ? urlFichier(apparence.ecoleId, 'nom.png', apparence.version) : null
}

// --- Application à toute l'appli ---

function rgba(hex, alpha) {
  const n = parseInt(hex.slice(1), 16)
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`
}

export function appliquer(apparence) {
  const racine = document.documentElement.style
  racine.setProperty('--bg', apparence.couleurFond)
  racine.setProperty('--text', apparence.couleurTexte)
  racine.setProperty('--accent', apparence.couleurAccent)
  racine.setProperty('--accent-bg', rgba(apparence.couleurAccent, 0.14))
  const police = POLICES.find((p) => p.cle === (apparence.police ?? ''))
  racine.setProperty('--sans', (police ?? POLICES[0]).famille)
}

let actuelle = DEFAUT
const abonnes = new Set()

function definir(apparence) {
  actuelle = { ...DEFAUT, ...apparence }
  appliquer(actuelle)
  for (const f of abonnes) f()
}

export function useApparence() {
  return useSyncExternalStore(
    (f) => {
      abonnes.add(f)
      return () => abonnes.delete(f)
    },
    () => actuelle,
  )
}

// Avant toute connexion : l'école de l'adresse visitée (rien sur
// l'adresse générique, ni en développement).
export async function chargerParAdresse() {
  try {
    const reponse = await fetch(`${BASE_URL}/par-host/personnalisation`)
    if (!reponse.ok) return null
    const apparence = versEcran(await reponse.json())
    if (apparence.ecoleId) definir(apparence)
    return apparence
  } catch {
    return null
  }
}

// Une fois connecté : l'école du compte.
export async function chargerEcole(ecoleId) {
  if (!ecoleId) return
  try {
    const reponse = await fetch(`${BASE_URL}/ecoles/${ecoleId}/apparence`)
    if (reponse.ok) definir(versEcran(await reponse.json()))
  } catch {
    // Pas grave : l'apparence par défaut reste.
  }
}

// Après une modification dans Admin > École.
export function mettreAJour(apparence) {
  definir(apparence)
}
