import { useState } from 'react'
import { FileIcon, FolderIcon } from './icons.jsx'
import { FAMILIES } from './kinds.js'

// Écran du + « Que voulez-vous faire ? » (spec documents.md §7.1 ter).
// Ordre voulu par Seb (15 octobre) : Créer un fichier, Créer un dossier,
// Importer, puis les familles Informer / Questionner / Agir.
// Les modèles sont livrés avec l'appli, chaque asso pourra les modifier.
// Pour l'instant seuls « Créer un dossier » et « Importer » marchent : les
// fichiers de l'appli (Informer / Questionner / Agir) arrivent ensuite.

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

export default function NewScreen({ canAdd, onClose, onNewFolder, onImport, onToast }) {
  // Informer, Questionner, Agir : fermés au départ (Seb, 15 octobre).
  const [ouvert, setOuvert] = useState(null)
  const bientot = () => onToast('Bientôt : ces fichiers arrivent dans une prochaine version.')

  return (
    <div className="dx-panel dx-panel--up" role="dialog" aria-label="Que voulez-vous faire ?">
      <div className="dx-top">
        <button type="button" className="dx-ico" onClick={onClose} aria-label="Fermer">✕</button>
        <h2>Que voulez-vous faire ?</h2>
      </div>
      <div className="dx-body">
        {!canAdd && <p className="dx-note">Vous ne pouvez rien ajouter dans ce dossier. Ouvrez un dossier où vous pouvez modifier.</p>}
        <div className="dx-blank">
          <button type="button" onClick={bientot}>
            <FileIcon blank />
            <span>Créer un fichier</span>
            <span className="dx-tpl__soon">bientôt</span>
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
                <span className="dx-acc__arr">›</span>
              </button>
              {estOuvert && (
                <div className="dx-tpls">
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
