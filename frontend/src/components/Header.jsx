import { useState } from 'react'
import { ROLE_LABEL, estMonteeEnPrivilege } from '../data/roles.js'
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
}) {
  const [coursOpen, setCoursOpen] = useState(false)
  const [familleOpen, setFamilleOpen] = useState(false)
  const [menuOpen, setMenuOpen] = useState(false)
  const [profilVise, setProfilVise] = useState(null)
  const activeCours = cours.find((c) => c.id === selectedCoursId)

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
          {famille.length > 1 && (
            <div className="famille-selector">
              <button
                type="button"
                className="famille-selector__button"
                onClick={() => setFamilleOpen((o) => !o)}
                aria-label="Changer de profil"
              >
                <span className="avatar avatar--sm">{user.initiales}</span>
                <Icon name="chevronDown" size={14} />
              </button>
              {familleOpen && (
                <div className="cours-selector__menu famille-selector__menu">
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
