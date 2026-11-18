import { useEffect, useState } from 'react'
import { ouvrirConnexions } from '../../app/connexions.js'
import * as api from './api.js'

// Onglet FFST (spec/modules/ffst.md §6, maquette
// https://claude.ai/artifact/4tizDZ6Br2WxGL5MYwSQfy) : les trois listes du
// site de la FFST telles que lues la dernière fois. Rafraîchir relit le site.

const LISTES = [
  { key: 'drafts', label: 'Brouillons', vide: 'Aucune demande en brouillon.' },
  { key: 'validated', label: 'Validées', vide: 'Aucune demande validée à payer.' },
  { key: 'licensees', label: 'Licenciés', vide: 'Aucun licencié cette saison.' },
]

// Colonnes du site (noms tels que le site les donne, Sambo Admin).
const COLONNES = {
  drafts: [['Demandé le', 'Demandé le '], ['État', 'Etat']],
  validated: [['N° demande', 'IDDemande'], ['État', 'Etat']],
  licensees: [],
}

// « 10 h 52 », précédé de la date si ce n'est pas aujourd'hui.
function heureLecture(iso) {
  // Le serveur donne une heure UTC sans fuseau.
  const date = new Date(/[zZ+]/.test(iso.slice(10)) ? iso : `${iso}Z`)
  const heure = `${date.getHours()} h ${String(date.getMinutes()).padStart(2, '0')}`
  const jour = date.toDateString() === new Date().toDateString() ? '' : `le ${date.toLocaleDateString('fr-FR')} `
  return `${jour}à ${heure}`
}

export default function FfstOnglet({ ecoleId, peutConnecter = false }) {
  const [lu, setLu] = useState(null)
  const [liste, setListe] = useState('drafts')
  const [lecture, setLecture] = useState(false)
  const [erreur, setErreur] = useState(null)

  useEffect(() => {
    api
      .listes(ecoleId)
      .then(setLu)
      .catch((e) => setErreur(e.message))
  }, [ecoleId])

  async function rafraichir() {
    setLecture(true)
    try {
      setLu(await api.lire(ecoleId))
      setErreur(null)
    } catch (e) {
      setErreur(e.message)
    } finally {
      setLecture(false)
    }
  }

  if (!lu) return <div className="ffst">{erreur && <p className="ffst__erreur">{erreur}</p>}</div>
  if (!lu.connected) {
    return (
      <div className="ffst">
        <p className="ffst__vide">Le site de la FFST n’est pas encore connecté.</p>
        {/* Raccourci vers Admin › École › Connexions (spec/core.md, « Connexions »). */}
        {peutConnecter ? (
          <button type="button" className="btn btn--primary btn--block" onClick={ouvrirConnexions}>
            Connecter le site de la FFST
          </button>
        ) : (
          <p className="ffst__vide">L’Administrateur principal peut le connecter dans Admin › École › Connexions.</p>
        )}
      </div>
    )
  }

  const lignes = lu.lists[liste] ?? []
  const actuelle = LISTES.find((l) => l.key === liste)
  const message = lu.error ?? erreur

  return (
    <div className="ffst">
      <div className="segmented ffst__listes">
        {LISTES.map((l) => (
          <button
            key={l.key}
            type="button"
            className={`segmented__option ${liste === l.key ? 'is-active' : ''}`}
            onClick={() => setListe(l.key)}
          >
            {l.label} ({(lu.lists[l.key] ?? []).length})
          </button>
        ))}
      </div>
      <div className="ffst__source">
        <span>{lu.read_at ? `Lu sur le site de la FFST ${heureLecture(lu.read_at)}` : 'Pas encore lu sur le site de la FFST'}</span>
        <button type="button" className="btn btn--secondary" disabled={lecture} onClick={rafraichir}>
          {lecture ? 'Lecture…' : 'Rafraîchir'}
        </button>
      </div>
      {message && (
        <p className="ffst__erreur" role="alert">
          {message}{' '}
          <a href="https://ffst-licences.com/GESTION_LICENCES_FFST" target="_blank" rel="noreferrer">
            Ouvrir le site de la FFST ↗
          </a>
        </p>
      )}
      {lignes.length ? (
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Nom et prénom</th>
                <th>Né(e) le</th>
                <th>Nature</th>
                <th>Licence n°</th>
                {COLONNES[liste].map(([titre]) => (
                  <th key={titre}>{titre}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {lignes.map((r, i) => (
                <tr key={i}>
                  <td className="data-table__name">{r['Nom et Prénom']}</td>
                  <td>{r['Né(e) le']}</td>
                  <td>{r.Type}</td>
                  <td>{r['Licence n°']}</td>
                  {COLONNES[liste].map(([titre, cle]) => (
                    <td key={titre}>{r[cle]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="ffst__vide">{actuelle.vide}</p>
      )}
      {liste === 'drafts' && (
        <p className="ffst__note">Valider le panier et payer les licences se fait sur le site de la FFST.</p>
      )}
    </div>
  )
}
