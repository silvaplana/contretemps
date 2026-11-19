import { useState } from 'react'
import { documentsApi } from '../../api/documents.js'

// « Documents spécifiques » (Seb, 19 novembre) : sous Photo, Lien, Document,
// la liste des documents à part de Docs, à joindre sans chercher dans les
// dossiers. Le premier : la convocation à l'AG (Docs › + › Convoquer l'AG),
// un fichier à remplir dont le nom commence par « Convocation ».
const SPECIFIQUES = [
  {
    cle: 'convocation-ag',
    nom: 'Convocation à l’AG',
    cherche: 'convocation',
    garder: (x) => x.kind === 'app' && x.name.startsWith('Convocation'),
    aucun: 'Aucune convocation d’AG dans Docs. Préparez-la dans Docs › + › Convoquer l’AG.',
  },
]

// Les fichiers de cette nature dans tous les espaces de Docs que la personne
// voit, le plus récent d'abord.
async function trouver(docs, specifique) {
  const espaces = await docs.spaces()
  const listes = await Promise.all(espaces.map((e) => docs.search(e.key, specifique.cherche)))
  return listes
    .flat()
    .filter(specifique.garder)
    .sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''))
}

export default function DocumentsSpecifiques({ ecoleId, onChoisir }) {
  const docs = useState(() => documentsApi(ecoleId))[0]
  const [ouvert, setOuvert] = useState(null) // la clé du document spécifique déroulé
  const [trouves, setTrouves] = useState(null)
  const [erreur, setErreur] = useState('')

  async function derouler(specifique) {
    if (ouvert === specifique.cle) return setOuvert(null)
    setOuvert(specifique.cle)
    setTrouves(null)
    setErreur('')
    try {
      setTrouves(await trouver(docs, specifique))
    } catch (e) {
      setErreur(e.message)
    }
  }

  return (
    <div className="specifiques">
      {SPECIFIQUES.map((s) => (
        <div key={s.cle} className="specifiques__groupe">
          <button type="button" className="choix__ligne" aria-expanded={ouvert === s.cle} onClick={() => derouler(s)}>
            <span>{s.nom}</span>
            <span className="choix__chevron" aria-hidden="true">
              {ouvert === s.cle ? '⌄' : '›'}
            </span>
          </button>
          {ouvert === s.cle && (
            <div className="specifiques__fichiers">
              {erreur && <p className="actus__vide">{erreur}</p>}
              {!erreur && trouves === null && <p className="actus__vide">Un instant…</p>}
              {trouves?.length === 0 && <p className="actus__vide">{s.aucun}</p>}
              {trouves?.map((x) => (
                <button key={x.id} type="button" className="choix__ligne" onClick={() => onChoisir({ id: x.id, name: x.name })}>
                  <span>{x.name}</span>
                </button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
