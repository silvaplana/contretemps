import { useState } from 'react'
import CodeConfirmModal from '../components/CodeConfirmModal.jsx'
import Icon from '../components/Icon.jsx'
import { ROLE_LABEL, estMonteeEnPrivilege } from '../data/roles.js'

// Écran Profil (tous les rôles — voir spec/SPEC.md §5.6 et images/profil.png).
// ⚠️ Proposition non validée dans la spec. Affiche les autres profils de la
// famille (§2.1) quand il y en a plus d'un, avec bascule sans reconnexion.
export default function ProfilScreen({ user, famille = [], onSwitchProfil, onLogout, onOpenMesHeures }) {
  const [notifications, setNotifications] = useState(true)
  const [profilVise, setProfilVise] = useState(null)
  const autresProfils = famille.filter((p) => p.id !== user.id)

  function demanderProfil(profil) {
    if (estMonteeEnPrivilege(user.type, profil.type)) {
      setProfilVise(profil)
    } else {
      onSwitchProfil(profil.id)
    }
  }

  return (
    <div className="screen profil-screen">
      <div className="profil-screen__identity">
        <span className="avatar avatar--lg">{user.initiales}</span>
        <h2>
          {user.prenom} {user.nom}
        </h2>
        {user.email && <p className="muted">{user.email}</p>}
        <span className="badge">{ROLE_LABEL[user.type]}</span>
      </div>

      {autresProfils.length > 0 && (
        <section>
          <h3 className="section-label">Ma famille</h3>
          <div className="profil-famille-list">
            {autresProfils.map((p) => (
              <button
                type="button"
                key={p.id}
                className="profil-famille-list__item"
                onClick={() => demanderProfil(p)}
              >
                <span className="avatar avatar--sm">{p.initiales}</span>
                <span className="profil-famille-list__nom">
                  {p.prenom} {p.nom}
                </span>
                <span className="muted">{ROLE_LABEL[p.type]}</span>
                <Icon name="chevronRight" size={18} />
              </button>
            ))}
          </div>
        </section>
      )}

      {user.type === 'professeur' && (
        <section>
          <h3 className="section-label">Travail</h3>
          <button type="button" className="settings-row settings-row--button" onClick={onOpenMesHeures}>
            <span>Mes heures</span>
            <Icon name="chevronRight" size={18} />
          </button>
        </section>
      )}

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
    </div>
  )
}
