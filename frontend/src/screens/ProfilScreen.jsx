import { useState } from 'react'
import Icon from '../components/Icon.jsx'

const ROLE_LABEL = { admin: 'Administrateur', professeur: 'Professeur', parent: 'Parent' }

// Écran Profil (tous les rôles — voir spec/SPEC.md 5.6 et images/profil.png).
// ⚠️ Écran non maquetté en détail dans la spec : proposition, comme indiqué
// dans le document. "Mes enfants" ne s'affiche que pour un parent.
export default function ProfilScreen({ user, onLogout }) {
  const [notifications, setNotifications] = useState(true)

  return (
    <div className="screen profil-screen">
      <div className="profil-screen__identity">
        <span className="avatar avatar--lg">{user.initiales}</span>
        <h2>
          {user.prenom} {user.nom}
        </h2>
        <p className="muted">{user.email}</p>
        <span className="badge">{ROLE_LABEL[user.type]}</span>
      </div>

      <section>
        <h3 className="section-label">Paramètres</h3>
        <div className="settings-row">
          <span>Notifications</span>
          <button
            type="button"
            className={`switch ${notifications ? 'is-on' : ''}`}
            onClick={() => setNotifications((n) => !n)}
            aria-pressed={notifications}
            aria-label="Activer les notifications"
          >
            <span className="switch__knob" />
          </button>
        </div>
        <button type="button" className="settings-row settings-row--button">
          <span>Changer le code d’accès</span>
          <Icon name="chevronRight" size={18} />
        </button>
      </section>

      <button type="button" className="btn btn--danger btn--block" onClick={onLogout}>
        Se déconnecter
      </button>
    </div>
  )
}
