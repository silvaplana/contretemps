import { useEffect, useState } from 'react'
import * as comptesApi from '../../api/comptes.js'
import * as profsApi from '../../api/profs.js'
import { normaliserRecherche } from '../../utils/recherche.js'
import FusionnerAvec from './FusionnerAvec.jsx'

const cle = (c) => normaliserRecherche(`${c.prenom} ${c.nom}`.trim().replace(/\s+/g, ' '))

// Bandeau « X a deux fiches » en haut d'Admin › Élèves (spec/core.md §4) :
// une élève ajoutée au nom d'un admin avec un autre email reçoit sa propre
// fiche (l'appli ne donne pas seule les droits d'un admin à une adresse
// nouvelle). Le bandeau le signale et propose de fusionner ; un admin décide.
export default function DeuxFiches({ ecoleId, eleves, onFusionnee }) {
  const [autres, setAutres] = useState([])
  const [fiche, setFiche] = useState(null)
  const ids = eleves.map((e) => e.id).join(',')

  useEffect(() => {
    Promise.all([comptesApi.listerAdmins(ecoleId), profsApi.lister(ecoleId)])
      .then(([admins, profs]) => setAutres([...admins.filter((a) => a.role !== 'superuser'), ...profs]))
      .catch(() => setAutres([]))
  }, [ecoleId, ids])

  const parNom = new Map()
  for (const c of [...eleves, ...autres]) {
    const groupe = parNom.get(cle(c)) ?? new Map()
    groupe.set(c.id, c)
    parNom.set(cle(c), groupe)
  }
  const eleveIds = new Set(eleves.map((e) => e.id))
  const doublons = [...parNom.values()]
    .filter((groupe) => groupe.size > 1)
    .map((groupe) => [...groupe.values()].find((c) => eleveIds.has(c.id)))
    .filter(Boolean)

  if (doublons.length === 0) return null
  return (
    <>
      {doublons.map((eleve) => (
        <div key={eleve.id} className="deux-fiches" role="status">
          <span>
            {eleve.prenom} {eleve.nom} a deux fiches.
          </span>
          <button type="button" className="btn btn--primary" onClick={() => setFiche(eleve)}>
            Fusionner
          </button>
        </div>
      ))}
      {fiche && (
        <FusionnerAvec
          ecoleId={ecoleId}
          fiche={fiche}
          onClose={() => setFiche(null)}
          onFait={() => {
            setFiche(null)
            onFusionnee()
          }}
        />
      )}
    </>
  )
}
