import { useEffect } from 'react'

// Où est la personne dans l'appli, pour l'assistant (Seb, 20/11 : « qu'il ait
// le contexte de où on est »). Chaque écran affiché dit son chemin, avec les
// libellés de l'écran (sans l'onglet de la barre du bas), et ce qui y est
// ouvert : { nature, id, nom }. L'assistant le lit au moment d'envoyer une
// question (lieuActuel). Le chemin le plus long gagne (l'écran le plus
// profond) ; ce qui est ouvert s'additionne (une fiche par-dessus un écran).
//
//   useLieu(['Bilan', 'Préparer', 'étape 3'], { nature: 'transaction', id: 12, nom: 'VIR SEPA…' })
//
// `chemin` : libellés (les vides sont ignorés) ; [] pour une fiche qui ne
// dit que ce qu'elle ouvre. `ouvert` : un objet, une liste, ou null.

const lieux = new Set()

export function useLieu(chemin, ouvert = null) {
  const cle = JSON.stringify([
    (chemin ?? []).filter(Boolean).map(String),
    [ouvert].flat().filter((o) => o && (o.id != null || o.nom)),
  ])
  useEffect(() => {
    const [c, o] = JSON.parse(cle)
    const lieu = { chemin: c, ouvert: o }
    lieux.add(lieu)
    return () => {
      lieux.delete(lieu)
    }
  }, [cle])
}

export function lieuActuel() {
  let chemin = []
  const ouvert = []
  for (const lieu of lieux) {
    if (lieu.chemin.length > chemin.length) chemin = lieu.chemin
    ouvert.push(...lieu.ouvert)
  }
  return { chemin, ouvert }
}
