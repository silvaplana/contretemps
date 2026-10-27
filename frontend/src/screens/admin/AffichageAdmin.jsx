import { useEffect, useRef, useState } from 'react'
import * as champsApi from '../../api/champs.js'
import Modal from '../../components/Modal.jsx'
import { ordonner } from '../../data/colonnesEleves.js'

// L'affichage dans Admin (spec/core.md §4.3, niveau 2 ; maquette « Champs des
// membres ») : les colonnes du tableau des élèves, dans l'ordre, chacune
// avec sa case Afficher. L'ordre se change en glissant la poignée ⠿ (au
// doigt ou à la souris, flèches du clavier aussi), jamais de flèches à
// l'écran. Chaque changement est enregistré aussitôt ; la case a Annuler 10 s.

const ANNULER_MS = 10000

export default function AffichageAdmin({ ecoleId, champs, onRetour, onClose }) {
  const [colonnes, setColonnes] = useState(null)
  const [erreur, setErreur] = useState('')
  const [toast, setToast] = useState(null)
  const [glissee, setGlissee] = useState(null)
  const minuteur = useRef(null)
  const lignes = useRef({})

  useEffect(() => {
    champsApi
      .colonnes(ecoleId)
      .then((enregistrees) => setColonnes(ordonner(enregistrees, champs)))
      .catch(() => setErreur('Impossible de charger les colonnes : vérifiez la connexion.'))
    return () => clearTimeout(minuteur.current)
  }, [ecoleId, champs])

  async function enregistrer(liste) {
    setColonnes(liste)
    try {
      await champsApi.changerColonnes(ecoleId, liste)
      setErreur('')
    } catch (e) {
      setErreur(e.message)
    }
  }

  function basculer(index) {
    const avant = colonnes
    const colonne = { ...colonnes[index], shown: !colonnes[index].shown }
    enregistrer(colonnes.map((c, i) => (i === index ? colonne : c)))
    clearTimeout(minuteur.current)
    setToast({ texte: `${colonne.label} ${colonne.shown ? 'affichée' : 'masquée'}`, annuler: () => enregistrer(avant) })
    minuteur.current = setTimeout(() => setToast(null), ANNULER_MS)
  }

  function deplacer(liste, de, vers) {
    const copie = [...liste]
    const [colonne] = copie.splice(de, 1)
    copie.splice(vers, 0, colonne)
    return copie
  }

  // Glisser : on suit le pointeur et on échange avec la ligne survolée.
  function commencer(e, index) {
    e.preventDefault()
    e.currentTarget.setPointerCapture(e.pointerId)
    setGlissee({ index, depart: colonnes })
  }

  function suivre(e) {
    if (!glissee) return
    const survolee = colonnes.findIndex((c) => {
      const boite = lignes.current[c.key]?.getBoundingClientRect()
      return boite && e.clientY >= boite.top && e.clientY <= boite.bottom
    })
    if (survolee < 0 || survolee === glissee.index) return
    setColonnes(deplacer(colonnes, glissee.index, survolee))
    setGlissee({ ...glissee, index: survolee })
  }

  function lacher() {
    if (!glissee) return
    setGlissee(null)
    if (colonnes !== glissee.depart) enregistrer(colonnes)
  }

  function clavier(e, index) {
    const vers = e.key === 'ArrowUp' ? index - 1 : e.key === 'ArrowDown' ? index + 1 : null
    if (vers === null || vers < 0 || vers >= colonnes.length) return
    e.preventDefault()
    enregistrer(deplacer(colonnes, index, vers))
    requestAnimationFrame(() => lignes.current[colonnes[index].key]?.querySelector('.affichage__poignee')?.focus())
  }

  const affichees = colonnes?.filter((c) => c.shown).length ?? 0

  return (
    <Modal title="Affichage dans Admin" onClose={onClose}>
      <div className="champs">
        <button type="button" className="champs__lien champs__retour" onClick={onRetour}>
          ← La fiche d’un membre
        </button>
        <p className="champs__note champs__note--haut">
          Les colonnes du tableau des élèves, dans l’ordre. {affichees} affichées.
        </p>
        {erreur && <p className="login-screen__erreur">{erreur}</p>}
        <div className="champs__entete affichage__entete">
          <span>Colonne</span>
          <span>Afficher</span>
        </div>
        {(colonnes ?? []).map((c, index) => (
          <div
            key={c.key}
            ref={(noeud) => {
              lignes.current[c.key] = noeud
            }}
            className={`affichage__ligne ${c.shown ? '' : 'is-masquee'} ${glissee?.index === index ? 'is-glissee' : ''}`}
          >
            <span
              className="affichage__poignee"
              role="button"
              tabIndex={0}
              aria-label={`Déplacer ${c.label}`}
              onPointerDown={(e) => commencer(e, index)}
              onPointerMove={suivre}
              onPointerUp={lacher}
              onPointerCancel={lacher}
              onKeyDown={(e) => clavier(e, index)}
            >
              ⠿
            </span>
            <span className="affichage__nom">
              {c.label}
              <small>
                {c.nature === 'Saisi' ? (
                  'Saisi'
                ) : (
                  <>
                    <b>{c.nature}</b> · {c.detail}
                  </>
                )}
              </small>
            </span>
            <span className="affichage__case">
              <input
                type="checkbox"
                checked={c.shown}
                disabled={c.verrouillee}
                aria-label={`Afficher ${c.label}`}
                onChange={() => basculer(index)}
              />
            </span>
          </div>
        ))}
        <p className="champs__note">
          Glissez la poignée ⠿ pour changer l’ordre. Un calcul ou un bouton vient d’un module ; masqué, il continue
          de travailler en coulisse.
        </p>
      </div>
      {toast && (
        <div className="admin-groupes__toast" role="status">
          <span>{toast.texte}</span>
          <button
            type="button"
            onClick={() => {
              const annuler = toast.annuler
              setToast(null)
              clearTimeout(minuteur.current)
              annuler()
            }}
          >
            Annuler
          </button>
        </div>
      )}
    </Modal>
  )
}
