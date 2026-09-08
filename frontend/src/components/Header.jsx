import { useRef, useState } from 'react'
import { ROLE_LABEL, estMonteeEnPrivilege } from '../data/roles.js'
import { useFermerAuClicExterieur } from '../hooks/useFermerAuClicExterieur.js'
import CodeConfirmModal from './CodeConfirmModal.jsx'
import Icon from './Icon.jsx'
import Logo from './Logo.jsx'

// En-tête d'écran (voir spec/SPEC.md section 4).
// - mode="simple" : logo + titre (écrans Admin et Profil, non "scopés cours").
// - mode="course" : logo + sélecteur de cours + sélecteur de profil famille
//   (si la famille a plus d'1 membre) + menu 3 points.
export default function Header({
  mode = 'simple',
  title,
  cours = [],
  selectedCoursId,
  onSelectCours,
  user,
  famille = [],
  onSwitchProfil,
  onNavigate,
  onLogout,
  // Action supplémentaire propre à l'écran affiché (ex. "Ajouter une
  // date" sur Présence — fait la même chose que le "+", juste accessible
  // aussi depuis ce menu) : { label, icon, onClick }, optionnel.
  menuExtra,
}) {
  const [coursOpen, setCoursOpen] = useState(false)
  const [familleOpen, setFamilleOpen] = useState(false)
  const [familleMenuTop, setFamilleMenuTop] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const [profilVise, setProfilVise] = useState(null)
  const activeCours = cours.find((c) => c.id === selectedCoursId)
  const familleBoutonRef = useRef(null)
  const coursSelectorRef = useRef(null)
  const familleSelectorRef = useRef(null)
  const headerMenuRef = useRef(null)

  // Referme le menu ouvert dès qu'on touche ailleurs sur l'écran — sinon
  // il restait ouvert indéfiniment (vécu sur Présence et Messagerie).
  useFermerAuClicExterieur(coursSelectorRef, coursOpen, () => setCoursOpen(false))
  useFermerAuClicExterieur(familleSelectorRef, familleOpen, () => setFamilleOpen(false))
  useFermerAuClicExterieur(headerMenuRef, menuOpen, () => setMenuOpen(false))

  // Position fixe (viewport), calée sur le bord droit de l'écran, plutôt
  // qu'absolue sur le petit bouton avatar (qui est près du bord mais pas
  // dessus — l'ancien calcul CSS coupait les noms les plus longs hors
  // écran, voir App.css). `top` calculé au clic pour suivre le bouton quel
  // que soit l'écran (mode simple vs course).
  function ouvrirFamilleMenu() {
    const rect = familleBoutonRef.current?.getBoundingClientRect()
    if (rect) setFamilleMenuTop(rect.bottom + 6)
    setFamilleOpen((o) => !o)
  }

  function demanderProfil(profil) {
    setFamilleOpen(false)
    if (estMonteeEnPrivilege(user.type, profil.type)) {
      setProfilVise(profil)
    } else {
      onSwitchProfil(profil.id)
    }
  }

  return (
    <header className="app-header">
      <div className="app-header__left">
        <Logo size={36} />
        {mode === 'simple' && <h1 className="app-header__title">{title}</h1>}
        {mode === 'course' && (
          <div className="cours-selector" ref={coursSelectorRef}>
            <button
              type="button"
              className="cours-selector__button"
              onClick={() => setCoursOpen((o) => !o)}
            >
              <span>{activeCours ? activeCours.nom : title}</span>
              <Icon name="chevronDown" size={16} />
            </button>
            {coursOpen && (
              <div className="dropdown-menu cours-selector__menu">
                {cours.map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    className={c.id === selectedCoursId ? 'is-active' : ''}
                    onClick={() => {
                      onSelectCours(c.id)
                      setCoursOpen(false)
                    }}
                  >
                    {c.nom}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {mode === 'course' && (
        <div className="app-header__right">
          {famille.length > 1 && (
            <div className="famille-selector" ref={familleSelectorRef}>
              <button
                ref={familleBoutonRef}
                type="button"
                className="famille-selector__button"
                onClick={ouvrirFamilleMenu}
                aria-label="Changer de profil"
              >
                <span className="avatar avatar--sm">{user.initiales}</span>
                <Icon name="chevronDown" size={14} />
              </button>
              {familleOpen && (
                <div
                  className="dropdown-menu famille-selector__menu"
                  style={{ top: familleMenuTop }}
                >
                  {famille.map((p) => (
                    <button
                      key={p.id}
                      type="button"
                      className={p.id === user.id ? 'is-active' : ''}
                      onClick={() => demanderProfil(p)}
                    >
                      <span className="avatar avatar--sm">{p.initiales}</span>
                      {p.prenom} {p.nom}
                      <span className="muted famille-selector__role">{ROLE_LABEL[p.type]}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
          <div className="header-menu" ref={headerMenuRef}>
            <button
              type="button"
              className="icon-btn"
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Menu"
            >
              <Icon name="moreVertical" />
            </button>
            {menuOpen && (
              <div className="dropdown-menu header-menu__panel">
                {menuExtra && (
                  <button
                    type="button"
                    onClick={() => {
                      menuExtra.onClick()
                      setMenuOpen(false)
                    }}
                  >
                    <Icon name={menuExtra.icon} size={18} /> {menuExtra.label}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => {
                    onNavigate('profil')
                    setMenuOpen(false)
                  }}
                >
                  <Icon name="profil" size={18} /> Profil
                </button>
                <button type="button" onClick={onLogout}>
                  <Icon name="logout" size={18} /> Se déconnecter
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {profilVise && (
        <CodeConfirmModal
          profil={profilVise}
          onClose={() => setProfilVise(null)}
          onConfirm={() => {
            onSwitchProfil(profilVise.id)
            setProfilVise(null)
          }}
        />
      )}
    </header>
  )
}
