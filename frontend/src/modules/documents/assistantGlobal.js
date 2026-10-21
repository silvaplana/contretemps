import { useEffect, useState } from 'react'
import { accesAssistant } from '../../api/assistant.js'

// État de l'assistant de toute l'appli (voir AssistantGlobal.jsx), partagé
// par le bouton de l'en-tête, le panneau et Docs.

const CLE_OUVERT = 'contretemps.assistant.ouvert'

export function lireStockage(cle) {
  try {
    return localStorage.getItem(cle)
  } catch {
    return null
  }
}

export function ecrireStockage(cle, valeur) {
  try {
    localStorage.setItem(cle, valeur)
  } catch {
    // stockage indisponible : vaut pour cette fois
  }
}

// Docs se branche ici quand il est affiché : ce qu'il montre (contexte) et
// comment faire une carte (recharger la liste, ouvrir le fichier créé).
let docs = null
let aOuvrir = null

export function docsBranche() {
  return docs
}

export function ouvrirDansDocs(fichier) {
  aOuvrir = fichier
}

export function brancherDocs(branche) {
  docs = branche
  return () => {
    if (docs === branche) docs = null
  }
}

// Fichier de l'appli ouvert (AppFile) : l'assistant de l'appli le lit et le
// corrige, avec Annuler (Seb, 21 octobre : plus de chat propre au fichier).
let fichier = null

export function fichierBranche() {
  return fichier
}

export function brancherFichier(branche) {
  fichier = branche
  return () => {
    if (fichier === branche) fichier = null
  }
}

// Fichier de l'appli créé depuis un autre onglet : Docs l'ouvre en arrivant.
export function prendreFichierAOuvrir() {
  const f = aOuvrir
  aOuvrir = null
  return f
}

// État partagé par l'en-tête (le bouton) et le panneau.
// `compteId` : l'accès dépend aussi du profil (essai : le Super User).
export function useAssistantGlobal(orgId, compteId) {
  const [acces, setAcces] = useState({ cle: null, permis: false, cout: null })
  const cle = `${orgId}:${compteId}`
  const [voulu, setVoulu] = useState(() => lireStockage(CLE_OUVERT) === '1')
  const [monte, setMonte] = useState(voulu)
  useEffect(() => {
    if (!orgId || compteId == null) return undefined
    let annule = false
    accesAssistant(orgId).then(
      (x) => !annule && setAcces({ cle, permis: x.autorise, cout: x.cout_saison_usd }),
      () => {},
    )
    return () => {
      annule = true
    }
  }, [orgId, compteId, cle])
  const permis = acces.cle === cle && acces.permis
  const ouvert = permis && voulu
  function changer(o) {
    setVoulu(o)
    if (o) setMonte(true)
    ecrireStockage(CLE_OUVERT, o ? '1' : '0')
  }
  return {
    orgId,
    permis,
    ouvert,
    monte: permis && monte,
    coutSaison: acces.cout,
    ouvrir: () => changer(true),
    fermer: () => changer(false),
    basculer: () => changer(!voulu),
  }
}
