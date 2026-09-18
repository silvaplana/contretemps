import { useRef, useState } from 'react'
import { ROLE_LABEL, estMonteeEnPrivilege, trierParRole } from '../data/roles.js'
import { useFermerAuClicExterieur } from '../hooks/useFermerAuClicExterieur.js'
import { correspond } from '../utils/recherche.js'
import CodeConfirmModal from './CodeConfirmModal.jsx'
import Icon from './Icon.jsx'
import Logo from './Logo.jsx'
import Modal from './Modal.jsx'

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
  // Modale plein écran (voir plus bas) plutôt qu'un menu déroulant
  // classique — bug signalé : avec beaucoup de cours, le menu débordait
  // de l'écran et les derniers cours restaient inatteignables (rien pour
  // le faire défiler, contrairement à .modal-panel qui est bornée en
  // hauteur ET défile, voir App.css).
  const [coursOpen, setCoursOpen] = useState(false)
  const [coursSearch, setCoursSearch] = useState('')
  const [familleOpen, setFamilleOpen] = useState(false)
  const [familleMenuTop, setFamilleMenuTop] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const [profilVise, setProfilVise] = useState(null)
  const activeCours = cours.find((c) => c.id === selectedCoursId)
  const familleBoutonRef = useRef(null)
  const familleSelectorRef = useRef(null)
  const headerMenuRef = useRef(null)

  // Referme le menu ouvert dès qu'on touche ailleurs sur l'écran — sinon
  // il restait ouvert indéfiniment (vécu sur Présence et Messagerie).
  useFermerAuClicExterieur(familleSelectorRef, familleOpen, () => setFamilleOpen(false))
  useFermerAuClicExterieur(headerMenuRef, menuOpen, () => setMenuOpen(false))

  function fermerCoursModal() {
    setCoursOpen(false)
    setCoursSearch('')
  }

  const coursFiltres = cours.filter((c) => correspond(c.nom, coursSearch))

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
          <div className="cours-selector">
            <button
              type="button"
              className="cours-selector__button"
              onClick={() => setCoursOpen(true)}
            >
              <span>{activeCours ? activeCours.nom : title}</span>
              <Icon name="chevronDown" size={16} />
            </button>
          </div>
        )}
      </div>

      {(famille.length > 1 || mode === 'course') && (
        <div className="app-header__right">
          {/* Sélecteur familial : toujours visible dès qu'il y a plus d'1
              profil (voir spec §4), pas seulement en mode "course" — sans
              ça, impossible de changer de profil depuis Admin/Profil/Heures
              (signalé : absent de Profil). Le menu "..." ci-dessous, lui,
              reste réservé au mode "course" : "Profil"/"Se déconnecter" y
              feraient doublon sur l'écran Profil, qui a déjà son propre
              bouton de déconnexion. */}
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
                  {trierParRole(famille).map((p) => (
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
          {mode === 'course' && (
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
          )}
        </div>
      )}

      {profilVise && (
        <CodeConfirmModal
          profil={profilVise}
          onClose={() => setProfilVise(null)}
          onConfirm={async (code) => {
            // Pas de try/catch ici : une erreur (code incorrect) doit
            // remonter jusqu'à CodeConfirmModal, qui l'affiche et reste
            // ouverte — surtout ne pas fermer/basculer sur un échec.
            await onSwitchProfil(profilVise.id, code)
            setProfilVise(null)
          }}
        />
      )}

      {coursOpen && (
        <Modal title="Sélectionner un cours" onClose={fermerCoursModal}>
          <div className="search-bar">
            <Icon name="search" size={18} />
            <input
              autoFocus
              value={coursSearch}
              onChange={(e) => setCoursSearch(e.target.value)}
              placeholder="Rechercher un cours"
            />
          </div>
          <div className="cours-picker-list">
            {coursFiltres.map((c) => (
              <button
                key={c.id}
                type="button"
                className={`cours-picker-list__item ${c.id === selectedCoursId ? 'is-active' : ''}`}
                onClick={() => {
                  onSelectCours(c.id)
                  fermerCoursModal()
                }}
              >
                {c.nom}
              </button>
            ))}
            {coursFiltres.length === 0 && <p className="muted">Aucun cours ne correspond.</p>}
          </div>
        </Modal>
      )}
    </header>
  )
}
