import { useCallback, useEffect, useState } from 'react'
import { FolderIcon, PlusIcon, TrayIcon } from './icons.jsx'

// Arborescence à gauche, sur ordinateur seulement (façon Google Drive, Seb
// 15 octobre) : les espaces, et leurs dossiers à déplier. Un clic sur un nom
// ouvre le dossier à droite ; la flèche déplie ou replie sans l'ouvrir. Le
// chemin du dossier ouvert est toujours déplié. Seuls les dossiers y
// figurent, chargés à la demande (un appel par dossier déplié).

const cle = (space, id) => `${space}:${id ?? 'racine'}`

// Petits dessins des espaces (pas d'émoji : rendu différent selon l'appareil).
const DESSINS = {
  public: (
    <>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M3.5 12h17M12 3.5c2.6 2.6 2.6 14.4 0 17M12 3.5c-2.6 2.6-2.6 14.4 0 17" />
    </>
  ),
  private: (
    <>
      <rect x="5" y="10.5" width="14" height="10" rx="2" />
      <path d="M8 10.5V7.5a4 4 0 0 1 8 0v3" />
    </>
  ),
  personal: (
    <>
      <circle cx="12" cy="8" r="3.8" />
      <path d="M4.5 20.5c1.2-4 4.2-6 7.5-6s6.3 2 7.5 6" />
    </>
  ),
}

function IconeEspace({ espace }) {
  return (
    <svg className="dx-arbre__espace" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {DESSINS[espace] ?? DESSINS.private}
    </svg>
  )
}

function IconeLigne({ children }) {
  return (
    <svg className="dx-arbre__espace" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {children}
    </svg>
  )
}

export default function Arbre({
  api, spaces, space, folder, breadcrumb, version, onOpen, recentsActif, onRecents, onAccueil, onNouveau, onDropOn,
}) {
  const [enfants, setEnfants] = useState({}) // clé -> dossiers enfants
  // Choix de l'utilisateur (déplier / replier) ; sans choix, seul le chemin
  // du dossier ouvert est déplié.
  const [choix, setChoix] = useState({}) // clé -> true (déplié) / false (replié)
  const [survol, setSurvol] = useState(null) // clé de la ligne survolée en glissant

  const charger = useCallback(
    (s, id) =>
      api.browse(s, id).then(
        (x) => setEnfants((e) => ({ ...e, [cle(s, id)]: x.items.filter((i) => i.kind === 'folder') })),
        () => setEnfants((e) => ({ ...e, [cle(s, id)]: [] })),
      ),
    [api],
  )

  const surChemin = new Set([null, ...(breadcrumb ?? []).map((b) => b.id)].map((id) => cle(space, id)))
  const estOuvert = (k) => choix[k] ?? surChemin.has(k)
  const ouverts = [...new Set([...surChemin, ...Object.keys(choix)])].filter(estOuvert).sort()
  const ouvertsCle = ouverts.join('|')

  // Dossiers dépliés : chargés, et rechargés après chaque changement
  // (`version` : création, déplacement, suppression…).
  useEffect(() => {
    for (const k of ouvertsCle.split('|').filter(Boolean)) {
      const [s, id] = k.split(':')
      charger(s, id === 'racine' ? null : Number(id))
    }
  }, [ouvertsCle, version, charger])

  function basculer(s, id) {
    const k = cle(s, id)
    setChoix((c) => ({ ...c, [k]: !estOuvert(k) }))
  }

  // On peut lâcher sur une ligne des éléments de la liste ou des fichiers de
  // l'ordinateur (déplacer, ou copier dans le bac Échanges : voir Explorer).
  const glisseQuelqueChose = (e) =>
    ['application/x-dx-node', 'Files'].some((t) => Array.from(e.dataTransfer?.types ?? []).includes(t))

  function ligne({ s, id, nom, profondeur, actif, icone, bac = false }) {
    const k = cle(s, id)
    const ouvert = estOuvert(k)
    const liste = enfants[k]
    const vide = liste && liste.length === 0
    return (
      <li key={k}>
        <div
          className={`dx-arbre__ligne${actif ? ' is-active' : ''}${survol === k ? ' is-drop' : ''}`}
          style={{ paddingLeft: 8 + profondeur * 18 }}
          onDragOver={(e) => {
            if (!onDropOn || !glisseQuelqueChose(e)) return
            e.preventDefault()
            e.dataTransfer.dropEffect = bac || !e.dataTransfer.types.includes('application/x-dx-node') ? 'copy' : 'move'
            setSurvol(k)
          }}
          onDragLeave={() => setSurvol((x) => (x === k ? null : x))}
          onDrop={(e) => {
            if (!onDropOn) return
            e.preventDefault()
            setSurvol(null)
            onDropOn(s, id, bac, e)
          }}
        >
          <button
            type="button"
            className="dx-arbre__fleche"
            aria-label={ouvert ? `Replier ${nom}` : `Déplier ${nom}`}
            aria-expanded={ouvert}
            onClick={() => basculer(s, id)}
            style={{ visibility: vide ? 'hidden' : 'visible' }}
          >
            {ouvert ? '▾' : '▸'}
          </button>
          <button type="button" className="dx-arbre__nom" onClick={() => onOpen(s, id)} title={nom}>
            {icone}
            <span>{nom}</span>
          </button>
        </div>
        {ouvert && liste && liste.length > 0 && (
          <ul>
            {liste.map((d) =>
              ligne({
                s,
                id: d.id,
                nom: d.name,
                profondeur: profondeur + 1,
                actif: !recentsActif && s === space && d.id === folder,
                icone: d.system_kind === 'exchange' ? <TrayIcon /> : <FolderIcon restricted={d.restricted} />,
                bac: d.system_kind === 'exchange',
              }),
            )}
          </ul>
        )}
      </li>
    )
  }

  return (
    <nav className="dx-arbre" aria-label="Dossiers">
      {/* « Nouveau » en haut à gauche, comme dans Google Drive (sur
          ordinateur, à la place du bouton rond en bas, Seb 15 octobre).
          L'assistant est dans l'en-tête de l'appli (16 octobre). */}
      <div className="dx-arbre__boutons">
        <button type="button" className="dx-arbre__nouveau" onClick={onNouveau}>
          <PlusIcon />
          Nouveau
        </button>
      </div>
      {/* Accueil (revenir au départ) et Récents, comme dans Google Drive. */}
      <ul className="dx-arbre__raccourcis">
        <li>
          <div className={`dx-arbre__ligne${!recentsActif && space === 'private' && folder == null ? ' is-active' : ''}`}>
            <button type="button" className="dx-arbre__nom" onClick={onAccueil}>
              <IconeLigne>
                <path d="M4 11l8-6.5 8 6.5" />
                <path d="M6 9.5V20h12V9.5" />
              </IconeLigne>
              <span>Accueil</span>
            </button>
          </div>
        </li>
        <li>
          <div className={`dx-arbre__ligne${recentsActif ? ' is-active' : ''}`}>
            <button type="button" className="dx-arbre__nom" onClick={onRecents}>
              <IconeLigne>
                <circle cx="12" cy="12" r="8.5" />
                <path d="M12 7.5V12l3 2" />
              </IconeLigne>
              <span>Récents</span>
            </button>
          </div>
        </li>
      </ul>
      <ul>
        {spaces.map((sp) =>
          ligne({
            s: sp.key,
            id: null,
            nom: sp.label,
            profondeur: 0,
            actif: !recentsActif && sp.key === space && folder == null,
            icone: <IconeEspace espace={sp.key} />,
          }),
        )}
      </ul>
    </nav>
  )
}
