import { useEffect, useRef, useState } from 'react'
import { TABS } from '../data/nav.js'
import { aUnDesRoles } from '../data/roles.js'
import Icon from './Icon.jsx'

// Largeur minimale d'un onglet lisible (icône + libellé à 10 px) : en
// dessous, les libellés se chevauchent.
const LARGEUR_ONGLET = 64

// Barre de navigation basse fixe (voir spec/SPEC.md §3 et §4) : les onglets
// visibles dépendent du rôle du profil actif (Admin est réservé à l'Admin,
// Présence à l'Admin/Professeur — voir data/nav.js).
//
// Trop d'onglets pour la largeur (Super User, demande de Seb du
// 2026-10-18) : les derniers passent sous « Plus » (⋯) en bas à droite, qui
// les ouvre dans un petit menu.
//
// `alertes` : { [tabKey]: nombre } — badge numéroté sur l'icône de cet
// onglet (pour l'instant, seule la messagerie l'utilise : total des
// messages non lus toutes conversations confondues, voir App.jsx :
// compterNonLus). Objet plutôt qu'un simple nombre "messagerie" pour
// rester générique si un jour un autre onglet en a besoin.
//
// `eteints` : les modules éteints dans l'école (spec/core.md §9 bis.3), dont
// les onglets sont cachés.
export default function BottomNav({ active, onChange, profil, eteints = new Set(), alertes = {} }) {
  // Un profil à plusieurs rôles voit l'union de leurs onglets (spec §3).
  const visibles = TABS.filter((tab) => aUnDesRoles(profil, tab.roles) && !eteints.has(tab.module))
  const navRef = useRef(null)
  const [place, setPlace] = useState(visibles.length)
  const [menuOuvert, setMenuOuvert] = useState(false)

  useEffect(() => {
    const nav = navRef.current
    if (!nav || typeof ResizeObserver === 'undefined') return undefined
    const mesurer = () => setPlace(Math.max(2, Math.floor(nav.clientWidth / LARGEUR_ONGLET)))
    mesurer()
    const observateur = new ResizeObserver(mesurer)
    observateur.observe(nav)
    return () => observateur.disconnect()
  }, [])

  const deborde = visibles.length > place
  const dansLaBarre = deborde ? visibles.slice(0, place - 1) : visibles
  const dansLeMenu = deborde ? visibles.slice(place - 1) : []
  const actifDansLeMenu = dansLeMenu.some((tab) => tab.key === active)
  const alertesDuMenu = dansLeMenu.reduce((total, tab) => total + (alertes[tab.key] ?? 0), 0)

  function choisir(key) {
    setMenuOuvert(false)
    onChange(key)
  }

  function contenu(tab) {
    return (
      <>
        <span className="bottom-nav__icon">
          <Icon name={tab.icon} size={20} />
          {alertes[tab.key] > 0 && <span className="bottom-nav__badge">{alertes[tab.key]}</span>}
        </span>
        <span>{tab.label}</span>
      </>
    )
  }

  return (
    <nav className={`bottom-nav ${deborde && menuOuvert ? 'bottom-nav--menu-ouvert' : ''}`} ref={navRef}>
      {dansLaBarre.map((tab) => (
        <button
          key={tab.key}
          type="button"
          className={`bottom-nav__item ${active === tab.key ? 'is-active' : ''}`}
          onClick={() => choisir(tab.key)}
        >
          {contenu(tab)}
        </button>
      ))}
      {deborde && (
        <button
          type="button"
          className={`bottom-nav__item ${actifDansLeMenu ? 'is-active' : ''}`}
          onClick={() => setMenuOuvert((ouvert) => !ouvert)}
          aria-expanded={menuOuvert}
        >
          <span className="bottom-nav__icon">
            <Icon name="moreHorizontal" size={20} />
            {alertesDuMenu > 0 && <span className="bottom-nav__badge">{alertesDuMenu}</span>}
          </span>
          <span>Plus</span>
        </button>
      )}
      {deborde && menuOuvert && (
        <>
          <button type="button" className="bottom-nav__voile" aria-label="Fermer" onClick={() => setMenuOuvert(false)} />
          <div className="bottom-nav__menu" role="menu">
            {dansLeMenu.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="menuitem"
                className={`bottom-nav__menu-item ${active === tab.key ? 'is-active' : ''}`}
                onClick={() => choisir(tab.key)}
              >
                {contenu(tab)}
              </button>
            ))}
          </div>
        </>
      )}
    </nav>
  )
}
