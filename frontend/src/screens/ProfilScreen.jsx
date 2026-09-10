import { useEffect, useState } from 'react'
import * as notificationsApi from '../api/notifications.js'
import Icon from '../components/Icon.jsx'
import { ROLE_LABEL, trierParRole } from '../data/roles.js'

// Champ "toujours affiché, éditable via un crayon" (Profil admin
// uniquement, voir ProfilScreen.jsx : email et code de récupération) —
// clic sur le crayon -> input + coche pour valider, comme AdminGroupes.jsx
// (renommer une conversation) mais avec un état d'édition explicite
// plutôt que "toujours éditable", puisqu'ici ce n'est pas un tableau de
// gestion mais une fiche personnelle (consultation par défaut).
function ChampAdminEditable({ prefixe = '', valeur, placeholderVide, type = 'text', onSave }) {
  const [edition, setEdition] = useState(false)
  const [brouillon, setBrouillon] = useState(valeur ?? '')
  const [enCours, setEnCours] = useState(false)
  const [erreur, setErreur] = useState('')

  async function enregistrer() {
    setErreur('')
    setEnCours(true)
    try {
      await onSave(brouillon)
      setEdition(false)
    } catch (err) {
      // Sans ça, un échec (réseau coupé, etc.) ne laissait rien voir : on
      // dirait juste que "valider" ne fait rien (signalé).
      setErreur(err.message || 'Enregistrement impossible')
    } finally {
      setEnCours(false)
    }
  }

  if (edition) {
    return (
      // <form> plutôt qu'un <input> + bouton isolés : sur mobile, valider
      // en tapant "OK"/"Terminé" sur le clavier virtuel doit fonctionner
      // comme un tap sur la coche — sans ça, seule la coche (petite, et
      // parfois masquée par le clavier virtuel) permet de valider (signalé).
      <form
        className="profil-champ profil-champ--edition"
        onSubmit={(e) => {
          e.preventDefault()
          enregistrer()
        }}
      >
        {prefixe}
        <input
          type={type}
          value={brouillon}
          onChange={(e) => setBrouillon(e.target.value)}
          autoFocus
        />
        <button type="submit" className="icon-btn icon-btn--sm" disabled={enCours} aria-label="Valider">
          <Icon name="check" size={16} />
        </button>
        {erreur && <span className="login-screen__erreur">{erreur}</span>}
      </form>
    )
  }

  return (
    <p className="muted profil-champ">
      {prefixe}
      {valeur || placeholderVide}
      <button
        type="button"
        className="icon-btn icon-btn--sm"
        aria-label={`Modifier — ${prefixe || placeholderVide}`}
        onClick={() => {
          setBrouillon(valeur ?? '')
          setEdition(true)
        }}
      >
        <Icon name="edit" size={14} />
      </button>
    </p>
  )
}

// Écran Profil (tous les rôles — voir spec/SPEC.md §5.6 et images/profil.png).
// ⚠️ Proposition non validée dans la spec. Affiche les autres profils de la
// famille (§2.1) quand il y en a plus d'un, en lecture seule — pas
// cliquables (demande) : la bascule de profil se fait depuis le menu
// "Changer de profil" du Header (voir Header.jsx), pas doublée ici.
export default function ProfilScreen({ user, famille = [], onLogout, onOpenMesHeures, onUpdateUser }) {
  const autresProfils = trierParRole(famille.filter((p) => p.id !== user.id))

  // Notifications push (voir api/notifications.js) : reflète l'état RÉEL
  // de CET appareil (un abonnement navigateur existant), pas une simple
  // préférence locale — sans backend/service worker qui marche, le
  // bouton ne doit jamais prétendre être activé.
  const [notifications, setNotifications] = useState(false)
  const [notifEnCours, setNotifEnCours] = useState(false)
  const [notifErreur, setNotifErreur] = useState('')
  const notifSupportees = notificationsApi.pushSupporte()

  useEffect(() => {
    if (!notifSupportees) return
    notificationsApi.estAbonneSurCetAppareil().then(setNotifications)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function toggleNotifications() {
    setNotifErreur('')
    setNotifEnCours(true)
    try {
      if (notifications) {
        await notificationsApi.desabonner()
        setNotifications(false)
      } else {
        await notificationsApi.abonner(user.id)
        setNotifications(true)
      }
    } catch (err) {
      setNotifErreur(err.message || 'Impossible de changer ce réglage')
    } finally {
      setNotifEnCours(false)
    }
  }

  return (
    <div className="screen profil-screen">
      <div className="profil-screen__identity">
        <span className="avatar avatar--lg">{user.initiales}</span>
        <h2>
          {user.prenom} {user.nom}
        </h2>
        {/* Admin : email/téléphone/code de récupération éditables
            (crayon, demande) — les autres rôles restent en lecture
            seule, ces champs se gèrent depuis Admin > Élèves/Profs. */}
        {user.type === 'admin' ? (
          <>
            <ChampAdminEditable
              valeur={user.email}
              placeholderVide="Ajouter un email"
              type="email"
              onSave={(v) => onUpdateUser({ email: v })}
            />
            <ChampAdminEditable
              valeur={user.telephone}
              placeholderVide="Ajouter un téléphone"
              type="tel"
              onSave={(v) => onUpdateUser({ telephone: v })}
            />
            <ChampAdminEditable
              prefixe="Code de récupération : "
              valeur={user.codeRecuperation}
              placeholderVide="non défini"
              onSave={(v) => onUpdateUser({ codeRecuperation: v })}
            />
          </>
        ) : (
          // Professeur/Élève : téléphone affiché sous l'email (demande),
          // mais en lecture seule — ça se modifie depuis Admin >
          // Élèves/Profs, pas ici (pas de crayon hors admin).
          <>
            {user.email && <p className="muted">{user.email}</p>}
            {user.telephone && <p className="muted">{user.telephone}</p>}
          </>
        )}
        <span className="badge">{ROLE_LABEL[user.type]}</span>
      </div>

      {autresProfils.length > 0 && (
        <section>
          <h3 className="section-label">Ma famille</h3>
          <div className="profil-famille-list">
            {autresProfils.map((p) => (
              <div key={p.id} className="profil-famille-list__item">
                <span className="avatar avatar--sm">{p.initiales}</span>
                <span className="profil-famille-list__nom">
                  {p.prenom} {p.nom}
                </span>
                <span className="muted">{ROLE_LABEL[p.type]}</span>
              </div>
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
          <span>
            Notifications
            {!notifSupportees && <span className="muted"> (non supporté par ce navigateur)</span>}
          </span>
          <button
            type="button"
            className={`switch ${notifications ? 'is-on' : ''}`}
            onClick={toggleNotifications}
            disabled={!notifSupportees || notifEnCours}
            aria-pressed={notifications}
            aria-label="Activer les notifications"
          >
            <span className="switch__knob" />
          </button>
        </div>
        {notifErreur && <p className="login-screen__erreur">{notifErreur}</p>}
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
