import { useEffect, useState } from 'react'
import { FileIcon, FolderIcon } from './icons.jsx'
import { FAMILIES } from './kinds.js'
import FamilyCards from './app/FamilyCards.jsx'

// Écran du + « Que voulez-vous faire ? » (spec documents.md §7.1 ter).
// Ordre voulu par Seb (15 octobre) : Créer un fichier, Créer un dossier,
// Importer, puis les familles Informer / Questionner / Agir.
// Les modèles sont livrés avec l'appli, chaque asso pourra les modifier.
// « Créer un fichier » demande d'abord sa nature (Informer, Questionner,
// Agir : spec fichier-de-base.md §1). Les tuiles « de l'école » viennent de
// « Faire un modèle » (fichier-de-base.md §5) : les toucher crée une copie
// en Brouillon ; les admins les renomment, les cachent ou les suppriment.

function TuileEcole({ t, admin, api, onUse, onChanged, onToast }) {
  const [reglage, setReglage] = useState(false)
  const [nom, setNom] = useState(t.name)
  const [supprimer, setSupprimer] = useState(false)
  const faire = async (action, message) => {
    try {
      await action()
      onChanged()
      if (message) onToast(message)
    } catch (e) {
      onToast(e.message)
    }
  }
  if (reglage) {
    return (
      <div className="dx-tpl dx-tpl--reglage">
        <form
          onSubmit={(e) => {
            e.preventDefault()
            faire(() => api.updateTemplate(t.id, { name: nom }), 'Modèle renommé').then(() => setReglage(false))
          }}
        >
          <input aria-label="Nom de la tuile" value={nom} onChange={(e) => setNom(e.target.value)} />
          <button type="submit" className="dx-btn dx-btn--small" disabled={!nom.trim() || nom === t.name}>Renommer</button>
        </form>
        <div className="dx-tpl__actions">
          <button type="button" className="dx-btn dx-btn--small dx-btn--ghost" onClick={() => faire(() => api.updateTemplate(t.id, { hidden: !t.hidden }), t.hidden ? 'Modèle remis dans le +' : 'Modèle caché : seuls les admins le voient')}>
            {t.hidden ? 'Montrer' : 'Cacher'}
          </button>
          <button
            type="button"
            className="dx-btn dx-btn--small dx-btn--ghost dx-btn--danger"
            onClick={() => (supprimer ? faire(() => api.deleteTemplate(t.id), 'Modèle supprimé') : setSupprimer(true))}
          >
            {supprimer ? 'Vraiment supprimer ?' : 'Supprimer'}
          </button>
          <button type="button" className="dx-btn dx-btn--small dx-btn--ghost" onClick={() => setReglage(false)}>Fermer</button>
        </div>
      </div>
    )
  }
  return (
    <div className={`dx-tpl dx-tpl--ecole${t.hidden ? ' dx-tpl--cache' : ''}`}>
      <button type="button" className="dx-tpl__main" onClick={() => onUse(t)}>
        {t.name}
      </button>
      <span className="dx-tpl__ecole">{t.hidden ? 'caché' : 'de l’école'}</span>
      {admin && (
        <button type="button" className="dx-tpl__plus" aria-label={`Régler le modèle ${t.name}`} onClick={() => setReglage(true)}>
          ⋯
        </button>
      )}
    </div>
  )
}

const MODELES = {
  inform: {
    hint: 'À lire, personne ne répond',
    tiles: [
      'Préparer le PowerPoint d’AG',
      'Préparer le bilan financier d’AG',
      'Faire un cours',
      'Faire un dossier de subvention',
      'Faire un prévisionnel financier',
      'Faire un plan marketing',
      'Faire une étude marketing',
      'Faire une publi de blog',
      'Faire une publi de photos',
      'Faire le site web public de l’asso',
      'Faire une publication web',
    ],
  },
  question: { hint: 'Chacun répond', tiles: ['Convoquer l’AG', 'Faire un sondage'] },
  act: {
    hint: 'La réponse crée une inscription, un paiement…',
    tiles: ['Ouvrir les inscriptions annuelles', 'Ouvrir les inscriptions au spectacle', 'Faire une note de frais'],
  },
}

export default function NewScreen({ api, canAdd, onClose, onNewFolder, onImport, onNewApp, onUseTemplate, onToast }) {
  // Informer, Questionner, Agir : fermés au départ (Seb, 15 octobre).
  const [ouvert, setOuvert] = useState(null)
  const [nature, setNature] = useState(false)
  const bientot = () => onToast('Bientôt : ces modèles arrivent dans une prochaine version.')
  const [ecole, setEcole] = useState({ items: [], can_manage: false })
  const [tour, setTour] = useState(0)
  useEffect(() => {
    api.templates().then(setEcole, () => {})
  }, [api, tour])
  const recharger = () => setTour((n) => n + 1)

  if (nature) {
    return (
      <div className="dx-panel dx-panel--up" role="dialog" aria-label="Créer un fichier">
        <div className="dx-top">
          <button type="button" className="dx-ico" onClick={() => setNature(false)} aria-label="Retour">←</button>
          <h2>Créer un fichier</h2>
        </div>
        <div className="dx-body">
          <p className="dx-q">Que voulez-vous faire avec ce fichier ?</p>
          <FamilyCards onPick={onNewApp} />
          <p className="dx-note">Vous pourrez changer tant que le fichier est en Brouillon.</p>
        </div>
      </div>
    )
  }

  return (
    <div className="dx-panel dx-panel--up" role="dialog" aria-label="Que voulez-vous faire ?">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Fermer">✕</button>
        <h2>Que voulez-vous faire ?</h2>
      </div>
      <div className="dx-body">
        {!canAdd && <p className="dx-note">Vous ne pouvez rien ajouter dans ce dossier. Ouvrez un dossier où vous pouvez modifier.</p>}
        <div className="dx-blank">
          <button type="button" disabled={!canAdd} onClick={() => setNature(true)}>
            <FileIcon blank />
            <span>Créer un fichier</span>
          </button>
          <button type="button" disabled={!canAdd} onClick={onNewFolder}>
            <FolderIcon />
            <span>Créer un dossier</span>
          </button>
        </div>
        <button type="button" className="dx-import" disabled={!canAdd} onClick={onImport}>
          ⤒ Importer un fichier ou une photo
        </button>

        {Object.entries(MODELES).map(([cle, m]) => {
          const f = FAMILIES[cle]
          const estOuvert = ouvert === cle
          return (
            <div key={cle} className={`dx-acc${estOuvert ? ' dx-acc--open' : ''}`}>
              <button type="button" aria-expanded={estOuvert} onClick={() => setOuvert(estOuvert ? null : cle)}>
                <span className={`dx-dot${cle === 'inform' ? ' dx-famdot--i' : ''}`} style={{ background: f.color }}>{f.glyph}</span>
                <span className="dx-meta">
                  <span className="dx-n">{f.label}</span>
                  <span className="dx-s">{m.hint}</span>
                </span>
                {ecole.items.some((t) => t.family === cle && !t.hidden) && (
                  <span className="dx-acc__n">{ecole.items.filter((t) => t.family === cle && !t.hidden).length} de l’école</span>
                )}
                <span className="dx-acc__arr">›</span>
              </button>
              {estOuvert && (
                <div className="dx-tpls">
                  {ecole.items
                    .filter((t) => t.family === cle)
                    .map((t) => (
                      <TuileEcole
                        key={t.id}
                        t={t}
                        admin={ecole.can_manage}
                        api={api}
                        onUse={(x) => (canAdd ? onUseTemplate(x) : onToast('Ouvrez un dossier où vous pouvez ajouter.'))}
                        onChanged={recharger}
                        onToast={onToast}
                      />
                    ))}
                  {m.tiles.map((t) => (
                    <button key={t} type="button" className="dx-tpl" onClick={bientot}>
                      {t}
                      <span className="dx-tpl__soon">bientôt</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
