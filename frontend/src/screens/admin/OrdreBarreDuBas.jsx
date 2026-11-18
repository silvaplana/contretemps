import { useRef, useState } from 'react'
import Icon from '../../components/Icon.jsx'
import { LARGEUR_ONGLET } from '../../data/nav.js'

// Admin › École › Fonctionnalités, sous les cases : l'ordre des onglets de la
// barre du bas, le même pour toute l'école (spec/core.md §10.4 ; Seb, 18
// novembre 2026, remplace Profil › Ma barre du bas). On fait glisser un
// onglet par sa poignée ; l'ordre s'enregistre au lâcher. Les premiers vont
// dans la barre, la suite passe sous « Plus ».
// `onglets` : ceux des modules allumés, dans l'ordre actuel.
export default function OrdreBarreDuBas({ onglets, onRanger }) {
  const [glisse, setGlisse] = useState(null) // { cles, index } pendant un glisser
  const [erreur, setErreur] = useState('')
  const [ouvert, setOuvert] = useState(false) // déroulant, fermé au départ (Seb, 18/11)
  const liste = useRef(null)
  const cles = glisse?.cles ?? onglets.map((t) => t.key)
  const parCle = Object.fromEntries(onglets.map((t) => [t.key, t]))
  // Même calcul que BottomNav.jsx : quand tout ne tient pas, « Plus » prend
  // la dernière place.
  const largeur = document.querySelector('.bottom-nav')?.clientWidth ?? window.innerWidth
  const places = Math.max(2, Math.floor(largeur / LARGEUR_ONGLET))
  const dansLaBarre = cles.length > places ? places - 1 : cles.length

  function commencer(e, index) {
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    setGlisse({ cles, index })
  }

  function deplacer(e) {
    if (!glisse) return
    const lignes = [...liste.current.querySelectorAll('.ordre-barre__ligne')]
    const cible = lignes.findIndex((l) => {
      const r = l.getBoundingClientRect()
      return e.clientY >= r.top && e.clientY < r.bottom
    })
    if (cible < 0 || cible === glisse.index) return
    const nouvelles = [...glisse.cles]
    const [cle] = nouvelles.splice(glisse.index, 1)
    nouvelles.splice(cible, 0, cle)
    setGlisse({ cles: nouvelles, index: cible })
  }

  function lacher() {
    if (!glisse) return
    const ordre = glisse.cles
    setGlisse(null)
    if (ordre.join() === onglets.map((t) => t.key).join()) return
    setErreur('')
    onRanger(ordre).catch(() => setErreur("L'ordre n'a pas pu être enregistré. Réessayez."))
  }

  return (
    <div className="ordre-barre">
      <h4 className="section-label perso__sous-partie">
        <button
          type="button"
          className="section-label__depliant"
          aria-expanded={ouvert}
          onClick={() => setOuvert((o) => !o)}
        >
          <Icon name={ouvert ? 'chevronDown' : 'chevronRight'} size={14} />
          Ordre des onglets dans la barre d'outils du bas
        </button>
      </h4>
      {ouvert && (
        <>
          <p className="muted ordre-barre__aide">
            Faites glisser un onglet par sa poignée. Le même ordre pour tout le monde ; chacun ne voit que ses onglets.
          </p>
          <div className="ordre-barre__liste" ref={liste}>
            {cles.map((cle, index) => (
              <div key={cle}>
                {index === dansLaBarre && <p className="ordre-barre__plus">Sous « Plus »</p>}
                <div className={`ordre-barre__ligne${glisse?.index === index ? ' ordre-barre__ligne--glisse' : ''}`}>
                  <button
                    type="button"
                    className="ordre-barre__poignee"
                    aria-label={`Déplacer ${parCle[cle].label}`}
                    onPointerDown={(e) => commencer(e, index)}
                    onPointerMove={deplacer}
                    onPointerUp={lacher}
                    onPointerCancel={lacher}
                  >
                    <Icon name="grip" size={22} />
                  </button>
                  <Icon name={parCle[cle].icon} size={22} />
                  <span>{parCle[cle].label}</span>
                </div>
              </div>
            ))}
          </div>
          {erreur && <p className="login-screen__erreur">{erreur}</p>}
        </>
      )}
    </div>
  )
}
