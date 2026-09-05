import { useState } from 'react'
import Icon from './Icon.jsx'
import Logo from './Logo.jsx'

// En-tête d'écran (voir spec/SPEC.md section 4).
// - mode="simple" : logo + titre (écrans Admin et Profil, non "scopés cours").
// - mode="course" : logo + sélecteur de cours + avatar + menu hamburger
//   (Présence, Chorégraphie, Vidéo, Messagerie). L'admin voit tous les cours.
export default function Header({
  mode = 'simple',
  title,
  cours = [],
  selectedCoursId,
  onSelectCours,
  user,
  onNavigate,
  onLogout,
}) {
  const [coursOpen, setCoursOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const activeCours = cours.find((c) => c.id === selectedCoursId)

  return (
    <header className="app-header">
      <div className="app-header__left">
        <Logo size={36} />
        {mode === 'simple' && <h1 className="app-header__title">{title}</h1>}
        {mode === 'course' && (
          <div className="cours-selector">
            <button
              type="button"
              className="cours-selector__button"
              onClick={() => setCoursOpen((o) => !o)}
            >
              <span>{activeCours ? activeCours.nom : title}</span>
              <Icon name="chevronDown" size={16} />
            </button>
            {coursOpen && (
              <div className="cours-selector__menu">
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
          <button
            type="button"
            className="avatar avatar--sm"
            onClick={() => onNavigate('profil')}
            aria-label="Profil"
          >
            {user.initiales}
          </button>
          <div className="header-menu">
            <button
              type="button"
              className="icon-btn"
              onClick={() => setMenuOpen((o) => !o)}
              aria-label="Menu"
            >
              <Icon name="moreVertical" />
            </button>
            {menuOpen && (
              <div className="header-menu__panel">
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
    </header>
  )
}
