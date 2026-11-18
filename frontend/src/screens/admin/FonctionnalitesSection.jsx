import { useState } from 'react'
import * as modulesApi from '../../api/modules.js'
import { MODULES } from '../../app/modules.js'
import { ongletsVisibles } from '../../data/nav.js'
import { isOwner, isSuperuser } from '../../data/roles.js'
import OrdreBarreDuBas from './OrdreBarreDuBas.jsx'

// « Fonctionnalités » (Admin > École > Personnalisation de l'application ;
// Seb, 24 octobre) : une case par module (spec/core.md §9 bis.3). Décocher
// cache l'onglet et les actions de l'assistant, sans rien effacer. Seuls
// l'Administrateur principal et le Super User changent les cases et voient
// les réglages qu'un module déclare (`settings` dans son module.js).
// `barre` : { tabs, ordre, onRanger }, l'ordre de la barre du bas (sous les cases).
export default function FonctionnalitesSection({ ecole, activeUser, modules, onModulesChange, barre }) {
  const [erreur, setErreur] = useState(null)
  const peutChanger = isOwner(activeUser) || isSuperuser(activeUser)

  async function cocher(key, enabled) {
    setErreur(null)
    try {
      onModulesChange(await modulesApi.changer(ecole.id, key, enabled))
    } catch (e) {
      setErreur(e.message)
    }
  }

  return (
    <div className="checkbox-list perso__sous-partie">
      {modules.map((m) => {
        const declaration = MODULES.find((x) => x.key === m.key)
        const Reglages = peutChanger && declaration?.settings
        // Un sous-module (Mail) en retrait sous son module (spec/modules/mail.md §2).
        const sous = declaration?.sousModule ? ' fonctionnalites__module--sous' : ''
        return (
          <label key={m.key} className={`checkbox-list__item fonctionnalites__module${sous}`}>
            <input
              type="checkbox"
              checked={m.enabled}
              disabled={!peutChanger}
              onChange={(e) => cocher(m.key, e.target.checked)}
            />
            {Reglages ? (
              <span className="fonctionnalites__nom">
                {m.label}
                <Reglages ecole={ecole} enabled={m.enabled} onEnabledChange={(on) => cocher(m.key, on)} />
              </span>
            ) : (
              m.label
            )}
          </label>
        )
      })}
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {peutChanger && barre && (
        <OrdreBarreDuBas
          // Tous les onglets des modules allumés, quels que soient les rôles
          // (Supervision, propre au Super User, à part).
          onglets={ongletsVisibles(
            { roles: ['admin', 'owner', 'tresorier', 'professeur', 'eleve'] },
            new Set(modules.filter((m) => !m.enabled).map((m) => m.key)),
            barre.tabs,
            barre.ordre,
          )}
          onRanger={barre.onRanger}
        />
      )}
    </div>
  )
}
