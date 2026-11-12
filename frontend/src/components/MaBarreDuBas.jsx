import { useState } from 'react'
import { mots } from '../api/mots.js'
import { LARGEUR_ONGLET, ongletsVisibles } from '../data/nav.js'
import Icon from './Icon.jsx'
import Modal from './Modal.jsx'

// Profil › Ma barre du bas (spec/core.md §10.4, Seb, 12 novembre 2026) :
// chacun range ses onglets avec ↑ ↓. Les premiers vont dans la barre, la
// suite passe sous « Plus ». Chaque flèche enregistre tout de suite, et la
// barre du bas suit sous la fenêtre.
export default function MaBarreDuBas({ user, tabs, eteints, onRanger, onClose }) {
  const onglets = ongletsVisibles(user, eteints, tabs)
  const [erreur, setErreur] = useState('')
  // Même calcul que BottomNav.jsx : quand tout ne tient pas, « Plus » prend
  // la dernière place.
  const largeur = document.querySelector('.bottom-nav')?.clientWidth ?? window.innerWidth
  const places = Math.max(2, Math.floor(largeur / LARGEUR_ONGLET))
  const dansLaBarre = onglets.length > places ? places - 1 : onglets.length

  function ranger(ordre) {
    setErreur('')
    onRanger(ordre).catch(() => setErreur("L'ordre n'a pas pu être enregistré. Réessayez."))
  }

  function bouger(index, sens) {
    const cles = onglets.map((tab) => tab.key)
    ;[cles[index], cles[index + sens]] = [cles[index + sens], cles[index]]
    ranger(cles)
  }

  return (
    <Modal title="Ma barre du bas" onClose={onClose}>
      <p className="ma-barre__aide">
        {dansLaBarre < onglets.length
          ? `Les ${dansLaBarre} premiers sont dans la barre. Les autres sont sous « Plus ».`
          : 'Montez ou descendez un onglet avec les flèches.'}
      </p>
      <div className="ma-barre__liste">
        {onglets.map((tab, index) => (
          <div key={tab.key}>
            {index === dansLaBarre && <p className="ma-barre__plus">Sous « Plus »</p>}
            <div className="ma-barre__ligne">
              <Icon name={tab.icon} size={22} />
              <span className="ma-barre__nom">{tab.label}</span>
              <button
                type="button"
                className="ma-barre__fleche"
                aria-label={`Monter ${tab.label}`}
                disabled={index === 0}
                onClick={() => bouger(index, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                className="ma-barre__fleche"
                aria-label={`Descendre ${tab.label}`}
                disabled={index === onglets.length - 1}
                onClick={() => bouger(index, 1)}
              >
                ↓
              </button>
            </div>
          </div>
        ))}
      </div>
      {erreur && <p className="login-screen__erreur">{erreur}</p>}
      {user.tabOrder?.length > 0 && (
        <button type="button" className="btn btn--secondary btn--block" onClick={() => ranger([])}>
          Remettre l'ordre {mots().deLEcole}
        </button>
      )}
    </Modal>
  )
}
