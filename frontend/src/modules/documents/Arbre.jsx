import { useCallback, useEffect, useState } from 'react'
import { FolderIcon } from './icons.jsx'

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

export default function Arbre({ api, spaces, space, folder, breadcrumb, version, onOpen }) {
  const [enfants, setEnfants] = useState({}) // clé -> dossiers enfants
  // Choix de l'utilisateur (déplier / replier) ; sans choix, seul le chemin
  // du dossier ouvert est déplié.
  const [choix, setChoix] = useState({}) // clé -> true (déplié) / false (replié)

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

  function ligne({ s, id, nom, profondeur, actif, icone }) {
    const k = cle(s, id)
    const ouvert = estOuvert(k)
    const liste = enfants[k]
    const vide = liste && liste.length === 0
    return (
      <li key={k}>
        <div className={`dx-arbre__ligne${actif ? ' is-active' : ''}`} style={{ paddingLeft: 8 + profondeur * 18 }}>
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
                actif: s === space && d.id === folder,
                icone: <FolderIcon restricted={d.restricted} />,
              }),
            )}
          </ul>
        )}
      </li>
    )
  }

  return (
    <nav className="dx-arbre" aria-label="Dossiers">
      <ul>
        {spaces.map((sp) =>
          ligne({
            s: sp.key,
            id: null,
            nom: sp.label,
            profondeur: 0,
            actif: sp.key === space && folder == null,
            icone: <IconeEspace espace={sp.key} />,
          }),
        )}
      </ul>
    </nav>
  )
}
