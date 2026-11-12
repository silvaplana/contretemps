import { useRef, useState } from 'react'
import { mots } from '../api/mots.js'
import { LARGEUR_ONGLET, ongletsVisibles } from '../data/nav.js'
import Icon from './Icon.jsx'
import Modal from './Modal.jsx'

// Profil › Ma barre du bas (spec/core.md §10.4, Seb, 12 novembre 2026) :
// une seule liste d'onglets, qu'on range en glissant la poignée ⠿ à gauche
// (au doigt ou à la souris, flèches du clavier aussi), comme Admin › Affichage.
// Les premiers vont dans la barre, la suite sous « Plus » : un trait le
// montre, ce n'est pas un sous-dossier, on y glisse un onglet ou on l'en sort.
// L'ordre est enregistré au lâcher.
export default function MaBarreDuBas({ user, tabs, eteints, onRanger, onClose }) {
  const enregistres = ongletsVisibles(user, eteints, tabs)
  const [erreur, setErreur] = useState('')
  // Pendant un glisser : l'ordre en cours, avant enregistrement.
  const [glisse, setGlisse] = useState(null)
  const lignes = useRef({})
  const onglets = glisse ? glisse.ordre : enregistres
  // Même calcul que BottomNav.jsx : quand tout ne tient pas, « Plus » prend
  // la dernière place.
  const largeur = document.querySelector('.bottom-nav')?.clientWidth ?? window.innerWidth
  const places = Math.max(2, Math.floor(largeur / LARGEUR_ONGLET))
  const dansLaBarre = onglets.length > places ? places - 1 : onglets.length

  function ranger(liste) {
    setErreur('')
    onRanger(liste.map((tab) => tab.key)).catch(() => setErreur("L'ordre n'a pas pu être enregistré. Réessayez."))
  }

  function deplacer(liste, de, vers) {
    const copie = [...liste]
    const [tab] = copie.splice(de, 1)
    copie.splice(vers, 0, tab)
    return copie
  }

  // Glisser : on suit le pointeur et on prend la place de la ligne survolée.
  function commencer(e, index) {
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    setGlisse({ index, ordre: enregistres, bouge: false })
  }

  function suivre(e) {
    if (!glisse) return
    const survolee = glisse.ordre.findIndex((tab) => {
      const boite = lignes.current[tab.key]?.getBoundingClientRect()
      return boite && e.clientY >= boite.top && e.clientY <= boite.bottom
    })
    if (survolee < 0 || survolee === glisse.index) return
    setGlisse({ index: survolee, ordre: deplacer(glisse.ordre, glisse.index, survolee), bouge: true })
  }

  function lacher() {
    if (!glisse) return
    setGlisse(null)
    if (glisse.bouge) ranger(glisse.ordre)
  }

  function clavier(e, index) {
    const vers = e.key === 'ArrowUp' ? index - 1 : e.key === 'ArrowDown' ? index + 1 : null
    if (vers === null || vers < 0 || vers >= onglets.length) return
    e.preventDefault()
    const cle = onglets[index].key
    ranger(deplacer(onglets, index, vers))
    requestAnimationFrame(() => lignes.current[cle]?.querySelector('.ma-barre__poignee')?.focus())
  }

  return (
    <Modal title="Ma barre du bas" onClose={onClose}>
      <p className="ma-barre__aide">Glissez la poignée ⠿ pour changer l’ordre.</p>
      <div className="ma-barre__liste">
        {onglets.map((tab, index) => (
          <div key={tab.key}>
            {index === dansLaBarre && <p className="ma-barre__plus">Plus bas, sous « Plus » ⋯</p>}
            <div
              ref={(noeud) => {
                lignes.current[tab.key] = noeud
              }}
              className={`ma-barre__ligne ${glisse?.index === index ? 'is-glissee' : ''}`}
            >
              <span
                className="ma-barre__poignee"
                role="button"
                tabIndex={0}
                aria-label={`Déplacer ${tab.label}`}
                onPointerDown={(e) => commencer(e, index)}
                onPointerMove={suivre}
                onPointerUp={lacher}
                onPointerCancel={lacher}
                onKeyDown={(e) => clavier(e, index)}
              >
                ⠿
              </span>
              <Icon name={tab.icon} size={22} />
              <span className="ma-barre__nom">{tab.label}</span>
            </div>
          </div>
        ))}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {user.tabOrder?.length > 0 && (
        <button type="button" className="btn btn--secondary btn--block" onClick={() => onRanger([]).catch(() => {})}>
          Remettre l'ordre {mots().deLEcole}
        </button>
      )}
    </Modal>
  )
}
