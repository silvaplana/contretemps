import { useCallback, useEffect, useRef, useState } from 'react'
import * as authApi from '../../api/auth.js'

// Invitation et suivi de l'accès à l'appli (voir spec/SPEC.md §2.2 :
// « Invitation » et « Suivi de l'invitation ») — colonnes « Inviter » et
// « Statut » des tableaux Admin > Élèves, Profs et Administrateurs.
// Le statut appartient à l'adresse email : tous les profils d'une même
// famille affichent le même. Toutes les étapes sont déclarées au serveur
// par l'appli elle-même : l'admin n'a rien à saisir.

const LIBELLES = {
  pas_email: 'Pas d’email',
  pas_invite: 'Pas invité',
  invite: 'Invité',
  consultee: 'Invitation consultée',
  finalise: 'Profil finalisé',
  installee: 'Appli installée',
}

// "02/10". Le serveur donne une date UTC sans fuseau.
function jourMois(dateIso) {
  if (!dateIso) return ''
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(dateIso) ? dateIso : `${dateIso}Z`)
  return date.toLocaleDateString('fr-FR', { day: '2-digit', month: '2-digit' })
}

// État d'accès de toutes les fiches de l'école, et de quoi inviter.
// `actif` : faux tant que l'écran qui s'en sert n'est pas affiché.
export function useAcces(ecoleId) {
  const [statuts, setStatuts] = useState({})
  const [message, setMessage] = useState(null) // { texte, erreur }
  const [envoiEnCours, setEnvoiEnCours] = useState(false)
  const minuteursRef = useRef([])

  const recharger = useCallback(() => {
    if (!ecoleId) return Promise.resolve()
    return authApi
      .statutsAcces(ecoleId)
      .then(setStatuts)
      .catch((err) => console.error(err))
  }, [ecoleId])

  useEffect(() => {
    recharger()
    const minuteurs = minuteursRef.current
    return () => minuteurs.forEach(clearTimeout)
  }, [recharger])

  async function inviter(compteIds) {
    setMessage(null)
    setEnvoiEnCours(true)
    try {
      const { emails, enCours } = await authApi.inviter(ecoleId, compteIds)
      setMessage({
        texte: enCours
          ? `Envoi de ${emails} invitations en cours : les statuts se mettent à jour au fur et à mesure.`
          : 'Invitation envoyée.',
      })
      await recharger()
      // Plusieurs adresses : les mails partent en tâche de fond côté
      // serveur, on relit les statuts à intervalles croissants.
      if (enCours) {
        minuteursRef.current = [3, 8, 15, 30, 60, 120].map((s) => setTimeout(recharger, s * 1000))
      }
    } catch (err) {
      setMessage({ texte: err.message, erreur: true })
    } finally {
      setEnvoiEnCours(false)
    }
  }

  return { statuts, inviter, message, envoiEnCours, recharger }
}

export function StatutAcces({ acces, compteId }) {
  const etat = acces.statuts[compteId]
  if (!etat) return <span className="muted">—</span>
  const date = jourMois(etat.date)
  return (
    <span className={`acces-statut acces-statut--${etat.statut}`}>
      {LIBELLES[etat.statut] ?? etat.statut}
      {date && ` le ${date}`}
    </span>
  )
}

// Disponible à chaque étape (un nouveau lien annule le précédent), grisé
// seulement sans email.
export function BoutonInviter({ acces, compteId, prenom }) {
  const etat = acces.statuts[compteId]
  const sansEmail = !etat || etat.statut === 'pas_email'
  return (
    <button
      type="button"
      className="btn btn--secondary acces-inviter"
      disabled={sansEmail || acces.envoiEnCours}
      title={sansEmail ? 'Pas d’email : ajoutez-en un pour pouvoir inviter' : undefined}
      onClick={() => acces.inviter([compteId])}
      aria-label={`Inviter ${prenom}`}
    >
      {etat && !['pas_email', 'pas_invite'].includes(etat.statut) ? 'Réinviter' : 'Inviter'}
    </button>
  )
}

// En-tête de la colonne « Inviter » : invite d'un coup toutes les fiches
// affichées qui ont un email et n'ont jamais été invitées (un seul mail par
// adresse). Évite de cliquer ligne par ligne le jour de la coupure.
export function InviterTous({ acces, compteIds }) {
  const aInviter = compteIds.filter((id) => acces.statuts[id]?.statut === 'pas_invite')
  return (
    <button
      type="button"
      className="btn btn--secondary acces-inviter"
      disabled={aInviter.length === 0 || acces.envoiEnCours}
      onClick={() => {
        if (window.confirm(`Envoyer une invitation aux ${aInviter.length} personnes pas encore invitées ?`)) {
          acces.inviter(aInviter)
        }
      }}
    >
      Inviter tous les non-invités{aInviter.length > 0 ? ` (${aInviter.length})` : ''}
    </button>
  )
}

export function MessageAcces({ acces }) {
  if (!acces.message) return null
  return (
    <p className={acces.message.erreur ? 'login-screen__erreur' : 'muted'} role="status">
      {acces.message.texte}
    </p>
  )
}
