import { useCallback, useEffect, useState } from 'react'
import Emargement from './app/Emargement.jsx'
import './app/app.css'

// « Produire le PV d'AG » (spec proces-verbal-ag.md §1) : l'assemblée passée
// qui attend son PV (une question si plusieurs), d'abord la liste des
// présents (photo ou feuille d'émargement), le quorum, puis « Proposer le
// procès-verbal » : le PV s'ouvre en Brouillon, c'est l'aperçu modifiable.
// `folderId` : depuis le bandeau du dossier de l'AG.

const QUORUM = { quarter: 'un quart', third: 'un tiers', half: 'la moitié' }

export default function ProduirePV({ api, folderId, onClose, onCreated, onToast }) {
  const [liste, setListe] = useState(null)
  const [choisie, setChoisie] = useState(null)
  const [feuille, setFeuille] = useState(null)
  const [emargement, setEmargement] = useState(false)
  const [envoi, setEnvoi] = useState(false)
  const [erreur, setErreur] = useState('')

  const choisir = useCallback(
    (ag) => {
      setChoisie(ag)
      api.attendance(ag.id).then(setFeuille, (e) => setErreur(e.message))
    },
    [api],
  )

  useEffect(() => {
    api.minutesPending(folderId).then(
      (r) => {
        setListe(r.items)
        if (r.items.length === 1) choisir(r.items[0])
      },
      (e) => setErreur(e.message),
    )
  }, [api, folderId, choisir])

  async function proposer() {
    setEnvoi(true)
    try {
      onCreated(await api.draftMinutes(choisie.id))
    } catch (e) {
      setErreur(e.message)
    } finally {
      setEnvoi(false)
    }
  }

  if (emargement) {
    return (
      <Emargement
        file={{ id: choisie.id, name: choisie.name }}
        api={api}
        onToast={onToast}
        onClose={async () => {
          setEmargement(false)
          choisir(choisie)
        }}
      />
    )
  }

  const plusieurs = liste && liste.length > 1
  const q = feuille?.quorum
  let corps
  if (erreur) corps = <p className="dx-error" role="alert">{erreur}</p>
  else if (!liste) corps = <p className="dx-note">Chargement…</p>
  else if (!liste.length) {
    corps = (
      <p className="dx-note">
        Aucune assemblée passée n’attend son procès-verbal. Il faut une convocation validée et envoyée, dont la date est passée.
      </p>
    )
  } else if (!choisie) {
    corps = (
      <>
        <p className="dx-q">Quelle assemblée ?</p>
        {liste.map((a) => (
          <button key={a.id} type="button" className="dx-act" onClick={() => choisir(a)}>
            <i>📁</i>
            <span>{a.title}</span>
          </button>
        ))}
      </>
    )
  } else if (!feuille) corps = <p className="dx-note">Chargement…</p>
  else {
    corps = (
      <>
        <p className="dx-q">{choisie.title}</p>
        <div className="em-chiffres">
          <span><b>{feuille.present}</b> présents</span>
          <span><b>{feuille.represented}</b> représentés</span>
          <span><b>{feuille.votes}</b> voix</span>
        </div>
        <p className={`em-quorum${q?.reached ? ' em-quorum--ok' : ''}`}>
          {q
            ? `Quorum : ${q.votes} voix sur ${q.needed} nécessaires (${QUORUM[q.rule]} des ${feuille.convoked} membres). ${q.reached ? 'Atteint.' : 'Pas atteint : ce sera écrit tel quel dans le procès-verbal.'}`
            : `${feuille.votes} voix présentes ou représentées sur ${feuille.convoked} membres convoqués.`}
          {feuille.lost > 0 && ` ${feuille.lost} pouvoir${feuille.lost > 1 ? 's' : ''} perdu${feuille.lost > 1 ? 's' : ''}.`}
        </p>
        {feuille.present === 0 ? (
          <>
            <p className="dx-note">D’abord la liste des présents : prenez en photo la feuille signée à l’entrée, ou cochez les présents.</p>
            <button type="button" className="dx-btn" onClick={() => setEmargement(true)}>
              📷 La liste des présents
            </button>
          </>
        ) : (
          <>
            <p className="dx-note">
              Le procès-verbal reprend ces chiffres, l’ordre du jour et le plan de celui de l’an dernier. Vous écrivez ensuite ce qui a été dit et les votes.
            </p>
            <button type="button" className="dx-btn" disabled={envoi} onClick={proposer}>
              {envoi ? 'Préparation…' : 'Proposer le procès-verbal'}
            </button>
            <button type="button" className="dx-btn dx-btn--ghost" onClick={() => setEmargement(true)}>
              Corriger la liste des présents
            </button>
          </>
        )}
      </>
    )
  }

  return (
    <div className="dx-panel dx-panel--up" role="dialog" aria-label="Produire le PV d’AG">
      <div className="dx-top">
        <button
          type="button"
          className="dx-ico"
          onClick={choisie && plusieurs ? () => (setChoisie(null), setFeuille(null)) : onClose}
          aria-label="Retour"
        >
          ←
        </button>
        <h2>Produire le PV d’AG</h2>
      </div>
      <div className="dx-body pv-corps">{corps}</div>
    </div>
  )
}
