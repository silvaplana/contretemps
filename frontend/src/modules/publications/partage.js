import * as api from './api.js'

// Partager un lien depuis une autre appli (bouton Partager de YouTube) vers
// un blog (spec/modules/actualites.md §12.11, Seb 13 novembre) : l'écran
// « Envoyer à… » propose en plus « Nouvelle publication dans <blog> » et
// « Ajouter à <brouillon> ». Le choix attend ici que le blog s'ouvre ; son
// éditeur s'ouvre alors avec le lien déjà ajouté.

const URL_DANS = /https?:\/\/\S+/i
export const lienDans = (texte) => texte?.match(URL_DANS)?.[0] ?? null

const nomDe = (b) => b.titre?.trim() || b.texte?.trim().split('\n')[0].slice(0, 40) || 'Sans nom'

// Les blogs où l'on publie, chacun suivi de ses brouillons.
export async function choixDePartage(ecoleId) {
  const blogs = (await api.lireBlogs(ecoleId)).filter((b) => b.peutPublier)
  const choix = []
  for (const blog of blogs) {
    choix.push({ cle: `n${blog.id}`, libelle: `Nouvelle publication dans ${blog.nom}`, blogId: blog.id, postId: null })
    try {
      const { brouillons } = await api.lireActus({ ecoleId, blogId: blog.id })
      for (const b of brouillons) {
        choix.push({ cle: `b${b.id}`, libelle: `Ajouter à « ${nomDe(b)} »`, detail: `Brouillon de ${blog.nom}`, blogId: blog.id, postId: b.id })
      }
    } catch {
      // Brouillons illisibles : la nouvelle publication reste proposée.
    }
  }
  return choix
}

let enAttente = null // { blogId, postId, lien }
const EVENEMENT = 'publications:partage'

export function deposer(partage) {
  enAttente = partage
  window.dispatchEvent(new CustomEvent(EVENEMENT))
}

// Le blog le prend une seule fois.
export function prendre(blogId) {
  if (enAttente?.blogId !== blogId) return null
  const partage = enAttente
  enAttente = null
  return partage
}

export function ecouter(rappel) {
  window.addEventListener(EVENEMENT, rappel)
  return () => window.removeEventListener(EVENEMENT, rappel)
}
