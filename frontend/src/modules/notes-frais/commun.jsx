import { useEffect, useState } from 'react'
import * as api from '../../api/notesFrais.js'
import Icon from '../../components/Icon.jsx'

// Vignette d'un justificatif : lu avec la session puis affiché par une URL
// locale (jamais d'URL publique). Un clic l'ouvre en grand.
export function Vignette({ piece, onSupprimer }) {
  const [url, setUrl] = useState(null)
  const [grand, setGrand] = useState(false)
  const estImage = piece.type_mime?.startsWith('image/')

  useEffect(() => {
    let annule = false
    let local = null
    api
      .urlPiece(piece.id)
      .then((u) => {
        local = u
        if (annule) URL.revokeObjectURL(u)
        else setUrl(u)
      })
      .catch(() => {})
    return () => {
      annule = true
      if (local) URL.revokeObjectURL(local)
    }
  }, [piece.id])

  return (
    <div className="nf-vignette">
      <button
        type="button"
        className="nf-vignette__ouvrir"
        onClick={() => (estImage ? setGrand(true) : url && window.open(url, '_blank'))}
        aria-label={`Voir ${piece.nom || 'le justificatif'}`}
      >
        {estImage && url ? <img src={url} alt="" /> : <Icon name="fileCheck" size={26} />}
      </button>
      {onSupprimer && (
        <button type="button" className="nf-vignette__retirer" onClick={onSupprimer} aria-label="Retirer la photo">
          <Icon name="x" size={14} />
        </button>
      )}
      {grand && url && (
        <div className="nf-plein-ecran" onClick={() => setGrand(false)}>
          <img src={url} alt={piece.nom || 'Justificatif'} />
        </div>
      )}
    </div>
  )
}

export function Pieces({ pieces }) {
  if (!pieces?.length) return <span className="badge badge--warning">sans justificatif</span>
  return (
    <div className="nf-vignettes">
      {pieces.map((p) => (
        <Vignette key={p.id} piece={p} />
      ))}
    </div>
  )
}

export function BadgeStatut({ note }) {
  const classe =
    note.statut === 'refusee'
      ? 'badge--danger'
      : note.statut === 'envoyee'
        ? 'badge--warning'
        : note.statut === 'remboursee' || note.don
          ? 'badge--success'
          : ''
  return <span className={`badge ${classe}`}>{note.libelle_statut}</span>
}

// Machine commune (§8.3 bis) : les états d'une dépense, vus du trésorier.
const ETATS = {
  envoyee: ['À valider', 'badge--warning'],
  refusee: ['Refusé', 'badge--danger'],
  validee: ['À payer', ''],
  preparee: ['Préparé', ''],
  viree: ['Envoyé', ''],
  remboursee: ['Payé', 'badge--success'],
}

export function BadgeEtat({ note }) {
  const [label, classe] = note.don && note.statut === 'validee' ? ['Don', 'badge--success'] : ETATS[note.statut]
  return <span className={`badge ${classe}`}>{label}</span>
}

// Pastille ronde du nombre de choses à faire (sous-onglet Pièces et ses
// puces) ; rien quand il n'y a rien à faire.
export function Compte({ n }) {
  if (!n) return null
  return (
    <span className="nf-compte" aria-label={`${n} à faire`}>
      {n}
    </span>
  )
}

export const NATURES = { frais: 'Note de frais', honoraires: 'Honoraires', achat: 'Achat' }

// Pourquoi l'appli propose cette nature (notes-de-frais.md §7 quinquies) :
// un prof lu sur la pièce = honoraires, une autre personne = note de frais,
// personne = achat de l'association.
export function raisonProposee(note) {
  if (!note.depenses[0]?.lue_par_ia) return null
  if (note.nature === 'achat') return 'aucun nom connu sur la pièce, payée par l’association.'
  if (!note.personne) return 'nom illisible ou inconnu, choisissez pour qui.'
  if (note.nature === 'honoraires') return `${note.personne.nom} est prof.`
  return `${note.personne.nom} est ${note.personne.role || 'membre'}.`
}

// Qui est derrière une pièce : la personne, ou le fournisseur d'un achat.
export function qui(note) {
  if (note.nature === 'achat') return note.fournisseur || 'Fournisseur à lire'
  return note.personne?.nom ?? 'Pour qui ?'
}

// « Vu sur le compte » (financier.md §8.3 bis) : l'opération qui semble payer
// la pièce, proposée par l'appli ; rien n'est rattaché sans « Confirmer ».
export function PaiementVu({ note, onConfirme }) {
  const op = note.paiement_propose
  if (!op) return null
  return (
    <div className="nf-ligne nf-paiement-vu">
      <span className="nf-ligne__corps">
        <span className="nf-ligne__titre">Vu sur le compte</span>
        <span className="muted">
          {op.libelle} · {api.euros(op.montant_centimes)} le {api.dateCourte(op.date)}
          {op.compte ? ` · ${op.compte}` : ''}
        </span>
      </span>
      <button type="button" className="btn btn--primary" onClick={() => onConfirme(op)}>
        C’est payé
      </button>
    </div>
  )
}

// Champs du RIB (Profil > Mon RIB et fenêtre d'envoi, spec §4.4 et §4.5).
export function ChampsRib({ rib, onChange }) {
  return (
    <>
      <label htmlFor="nf-titulaire">Titulaire du compte</label>
      <input
        id="nf-titulaire"
        value={rib.titulaire}
        onChange={(e) => onChange({ ...rib, titulaire: e.target.value })}
        autoComplete="name"
      />
      <label htmlFor="nf-iban">IBAN</label>
      <input
        id="nf-iban"
        value={rib.iban}
        onChange={(e) => onChange({ ...rib, iban: e.target.value.toUpperCase() })}
        placeholder="FR76 …"
        autoCapitalize="characters"
        spellCheck={false}
      />
      <label htmlFor="nf-bic">BIC (facultatif)</label>
      <input
        id="nf-bic"
        value={rib.bic}
        onChange={(e) => onChange({ ...rib, bic: e.target.value.toUpperCase() })}
        autoCapitalize="characters"
        spellCheck={false}
      />
    </>
  )
}

export const ribVide = (rib) => ({ titulaire: rib?.titulaire ?? '', iban: rib?.iban ?? '', bic: rib?.bic ?? '' })

export const EXPLICATION_RIB =
  'Facultatif. Sert uniquement à vous rembourser vos notes de frais ; seuls les trésoriers de l’association le voient.'
