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

// « Nouvelle convocation » (Seb, 20 novembre : « tu dois créer un document
// Convoquer l'AG et l'ouvrir en édition ») : les deux questions de Docs ›
// + › Convoquer l'AG (procurations.md §1.3), puis `onCreer` joint la
// convocation à l'actu et l'ouvre dans Docs, en Brouillon, pour la corriger.
function NouvelleConvocation({ docs, onCreer }) {
  const [kind, setKind] = useState('ordinary')
  const [jour, setJour] = useState('')
  const [heure, setHeure] = useState('14:00')
  const [dossiers, setDossiers] = useState(null) // { folders, new_name } : où la ranger ?
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState('')

  async function preparer(folderId = null, nouveau = false) {
    setEnvoi(true)
    setErreur('')
    try {
      const r = await docs.convene(kind, `${jour}T${heure}`, folderId, nouveau)
      if (r.folders) setDossiers(r)
      else await onCreer({ id: r.id, name: r.name })
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  if (dossiers) {
    return (
      <div className="specifiques__nouvelle">
        <p>Où ranger la convocation ?</p>
        {dossiers.folders.map((f) => (
          <button key={f.id} type="button" className="choix__ligne" disabled={envoi} onClick={() => preparer(f.id)}>
            <span>Réunions › {f.name}</span>
          </button>
        ))}
        <button type="button" className="choix__ligne" disabled={envoi} onClick={() => preparer(null, true)}>
          <span>Nouveau dossier « {dossiers.new_name} »</span>
        </button>
        {erreur && <p className="actus__vide">{erreur}</p>}
      </div>
    )
  }
  return (
    <div className="specifiques__nouvelle">
      <div className="specifiques__choix" role="radiogroup" aria-label="Quelle assemblée ?">
        {[
          ['ordinary', 'Ordinaire'],
          ['extraordinary', 'Extraordinaire'],
        ].map(([cle, texte]) => (
          <button key={cle} type="button" role="radio" aria-checked={kind === cle} onClick={() => setKind(cle)}>
            {texte}
          </button>
        ))}
      </div>
      <div className="specifiques__quand">
        <input type="date" aria-label="Date de l’assemblée" value={jour} onChange={(e) => setJour(e.target.value)} />
        <input type="time" aria-label="Heure de l’assemblée" value={heure} onChange={(e) => setHeure(e.target.value)} />
      </div>
      {erreur && <p className="actus__vide">{erreur}</p>}
      <button type="button" className="specifiques__preparer" disabled={!jour || !heure || envoi} onClick={() => preparer()}>
        {envoi ? 'Préparation…' : 'Préparer la convocation'}
      </button>
    </div>
  )
}

export default function DocumentsSpecifiques({ ecoleId, onChoisir, onCreer }) {
  const docs = useState(() => documentsApi(ecoleId))[0]
  const [ouvert, setOuvert] = useState(null) // la clé du document spécifique déroulé
  const [trouves, setTrouves] = useState(null)
  const [erreur, setErreur] = useState('')
  const [nouvelle, setNouvelle] = useState(false)

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
              {trouves?.map((x) => (
                <button key={x.id} type="button" className="choix__ligne" onClick={() => onChoisir({ id: x.id, name: x.name })}>
                  <span>{x.name}</span>
                </button>
              ))}
              {trouves !== null && !nouvelle && (
                <button type="button" className="choix__ligne specifiques__ajouter" onClick={() => setNouvelle(true)}>
                  <span>+ Nouvelle convocation</span>
                </button>
              )}
              {nouvelle && <NouvelleConvocation docs={docs} onCreer={onCreer} />}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
