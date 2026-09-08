import { useEffect } from 'react'

// Ferme un menu/popover dès qu'on clique/touche en dehors de son conteneur
// — sans ça un menu ouvert (sélecteur de cours, menu 3 points...) ne se
// refermait qu'en re-cliquant sur son propre bouton, jamais en touchant
// ailleurs sur l'écran (vécu sur Présence et Messagerie).
export function useFermerAuClicExterieur(ref, actif, onFermer) {
  useEffect(() => {
    if (!actif) return
    function gerer(e) {
      if (ref.current && !ref.current.contains(e.target)) onFermer()
    }
    // pointerdown (pas click) : se déclenche dès le début du toucher, avant
    // qu'un éventuel autre bouton en dessous ne reçoive lui-même son clic.
    document.addEventListener('pointerdown', gerer)
    return () => document.removeEventListener('pointerdown', gerer)
  }, [actif, onFermer, ref])
}
