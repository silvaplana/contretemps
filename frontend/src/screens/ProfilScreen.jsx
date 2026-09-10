import { useState } from 'react'
import {
  definirAffichageMigration,
  DOMAINES_MIGRES,
  estAffichageMigrationActif,
  INFOS_DOMAINES,
} from '../api/etatMigration.js'
import { estModeDemo } from '../api/mode.js'
import Badge from '../components/Badge.jsx'
import CodeConfirmModal from '../components/CodeConfirmModal.jsx'
import Icon from '../components/Icon.jsx'
import Modal from '../components/Modal.jsx'
import { ROLE_LABEL, estMonteeEnPrivilege, trierParRole } from '../data/roles.js'

// Écran Profil (tous les rôles — voir spec/SPEC.md §5.6 et images/profil.png).
// ⚠️ Proposition non validée dans la spec. Affiche les autres profils de la
// famille (§2.1) quand il y en a plus d'un, avec bascule sans reconnexion.
export default function ProfilScreen({ user, famille = [], onSwitchProfil, onLogout, onOpenMesHeures }) {
  const [notifications, setNotifications] = useState(true)
  const [profilVise, setProfilVise] = useState(null)
  const autresProfils = trierParRole(famille.filter((p) => p.id !== user.id))

  // Suivi de la migration vers le vrai backend (voir api/etatMigration.js)
  // — outil de dev, réservé à l'admin, à retirer une fois tous les
  // domaines branchés.
  const [afficherMigration, setAfficherMigration] = useState(estAffichageMigrationActif())
  const [showEtatModules, setShowEtatModules] = useState(false)
  // Le mode (voir api/mode.js) n'est plus un interrupteur ici : c'est le
  // bouton cliqué au login qui décide pour toute la session ("Se
  // connecter" = réel, "Voir une maquette" = démo, voir api/auth.js) —
  // ceci n'est qu'un rappel en lecture seule de celui actuellement actif.
  const modeReel = !estModeDemo()
  function toggleAffichageMigration(actif) {
    setAfficherMigration(actif)
    definirAffichageMigration(actif)
    // Simplification volontaire : voir ZoneMigration.jsx, lu au rendu de
    // chaque écran — un rechargement garantit que tout le reflète.
    window.location.reload()
  }

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
        {/* Admin uniquement (voir §6.3) — "Code oublié ?" à l'écran de
            connexion, voir LoginScreen.jsx: CodeOublieModal. */}
        {user.type === 'admin' && user.codeRecuperation && (
          <p className="muted">Code de récupération : {user.codeRecuperation}</p>
        )}
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

      {user.type === 'admin' && (
        <section>
          <h3 className="section-label">Développement</h3>
          {/* Le seul endroit de toute l'appli qui dit dans quel mode on
              est — "pas bleu" (voir ZoneMigration.jsx) veut juste dire
              que l'écran EST PRÊT à parler au vrai backend, pas qu'il le
              fait vraiment : ça dépend du bouton cliqué au login
              ("Se connecter" = réel, "Voir une maquette" = démo). */}
          <p className={modeReel ? 'profil-mode-actuel profil-mode-actuel--reel' : 'profil-mode-actuel'}>
            Mode actuel : <strong>{modeReel ? 'Réel (vraie base de données)' : 'Démo (données fictives, remises à zéro à chaque rechargement)'}</strong>
          </p>
          <div className="settings-row">
            <span>Repérer en bleu les écrans pas encore branchés au vrai backend</span>
            <button
              type="button"
              className={`switch ${afficherMigration ? 'is-on' : ''}`}
              onClick={() => toggleAffichageMigration(!afficherMigration)}
              aria-pressed={afficherMigration}
              aria-label="Repérer en bleu les écrans pas encore branchés"
            >
              <span className="switch__knob" />
            </button>
          </div>
          <button
            type="button"
            className="settings-row settings-row--button"
            onClick={() => setShowEtatModules(true)}
          >
            <span>État des modules</span>
            <Icon name="chevronRight" size={18} />
          </button>
        </section>
      )}

      <button type="button" className="btn btn--danger btn--block" onClick={onLogout}>
        Se déconnecter
      </button>

      {showEtatModules && (
        <Modal title="État des modules" onClose={() => setShowEtatModules(false)}>
          <p className="muted">
            Le backend expose déjà tous ces modules (testés côté serveur). "Branché" veut dire
            que l'écran est prêt à leur parler pour de vrai ; "En dur" veut dire qu'il n'utilise
            même pas encore ce code, juste les données fictives du frontend.
          </p>
          <p className="muted">
            ⚠️ En mode "démo" ("Voir une maquette" au login), même un module "Branché" tourne
            sur une copie en mémoire des données fictives, pas sur la vraie base : les
            modifications ne survivent pas à un rechargement de la page. Se connecter pour de
            vrai ("Se connecter", avec un identifiant/code réels) utilise la vraie base — voir
            "Mode actuel" ci-dessus.
          </p>
          <div className="checkbox-list">
            {Object.entries(INFOS_DOMAINES).map(([cle, { label, ecran }]) => (
              <div key={cle} className="checkbox-list__item checkbox-list__item--etat">
                <span>
                  <strong>{label}</strong> — {ecran}
                </span>
                {DOMAINES_MIGRES[cle] ? (
                  <Badge tone="success">Branché</Badge>
                ) : (
                  <Badge tone="info">En dur</Badge>
                )}
              </div>
            ))}
          </div>
        </Modal>
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
    </div>
  )
}
