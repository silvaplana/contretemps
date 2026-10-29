import { useEffect } from 'react'

// Lien vers un fichier ou un dossier des Docs (spec documents.md §6.3 ter) :
// `<adresse de l'école>/docs/<id>`. Il ne donne aucun droit : il montre
// l'endroit à qui peut le voir. Ouvert de deux façons :
// - depuis une bulle de la messagerie : événement `dx-ouvrir` { id } ;
// - depuis un email ou un autre onglet : l'adresse elle-même, lue une fois
//   au chargement (l'adresse redevient celle de l'accueil).

let enAttente = lireAdresse()
const abonnes = new Set()
// Fichier ouvert depuis un autre onglet avec retour : fermer l'aperçu
// ramène à cet onglet (voir `revenirApresFichier`).
let retour = false

function lireAdresse() {
  const trouve = window.location.pathname.match(/\/docs\/(\d+)\/?$/)
  if (!trouve) return null
  window.history.replaceState(null, '', import.meta.env.BASE_URL)
  return Number(trouve[1])
}

// L'appli ouvre l'onglet Docs directement quand on arrive par un lien.
export const DOCS_AU_CHARGEMENT = enAttente != null

// L'événement peut partir avant que l'explorateur soit monté : l'id attend.
window.addEventListener('dx-ouvrir', (e) => {
  const id = Number(e.detail?.id)
  if (!id) return
  retour = !!e.detail?.retour
  if (abonnes.size) abonnes.forEach((f) => f(id))
  else enAttente = id
})

export function useOuvrirDocs(onId) {
  useEffect(() => {
    if (enAttente != null) {
      const id = enAttente
      enAttente = null
      onId(id)
    }
    abonnes.add(onId)
    return () => abonnes.delete(onId)
  }, [onId])
}

// Texte envoyé dans la messagerie : le nom, puis le lien.
export function texteDuLien(item) {
  return `${item.name}\n${window.location.origin}${import.meta.env.BASE_URL}docs/${item.id}`
}

// Depuis un autre onglet de l'appli (Financier…) : l'appli passe sur Docs
// et y ouvre le dossier ou le fichier (écouté dans App.jsx). Avec `retour`,
// fermer l'aperçu du fichier ramène à l'onglet de départ.
export function ouvrirDansDocs(id, { retour: avecRetour = false } = {}) {
  window.dispatchEvent(new CustomEvent('app-ouvrir-docs', { detail: { id, retour: avecRetour } }))
}

// Appelé par l'explorateur : un dossier ouvert ne revient pas ; un aperçu
// fermé revient à l'onglet de départ s'il a été ouvert avec retour.
export function oublierRetour() {
  retour = false
}

export function revenirApresFichier() {
  if (!retour) return
  retour = false
  window.dispatchEvent(new CustomEvent('app-retour'))
}
