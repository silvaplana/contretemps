import { useState } from 'react'
import * as notificationsApi from '../api/notifications.js'

// Bandeau "Activer les notifications" (demande du 2026-09-21 : notifications
// activées par défaut). Aucun navigateur ne laisse un site les activer seul :
// ce bandeau fournit le geste qu'il exige, tant qu'elles n'ont été ni
// acceptées ni refusées sur cet appareil (voir api/notifications.js :
// bandeauAProposer). "Plus tard" le masque 7 jours.
export default function BandeauNotifications({ compteId }) {
  const [visible, setVisible] = useState(notificationsApi.bandeauAProposer)
  const [enCours, setEnCours] = useState(false)

  if (!visible) return null

  async function activer() {
    setEnCours(true)
    try {
      await notificationsApi.abonner(compteId)
    } catch (err) {
      // Refus ou échec : le téléphone ne reproposera pas la demande, le
      // bouton de Profil reste là pour réessayer.
      console.warn('Notifications non activées :', err.message)
    }
    setVisible(false)
  }

  return (
    <div className="bandeau-notifications" role="status">
      <p>Activez les notifications pour être prévenu des nouveaux messages, même appli fermée.</p>
      <div className="bandeau-notifications__actions">
        <button
          type="button"
          className="btn btn--link"
          onClick={() => {
            notificationsApi.reporterBandeau()
            setVisible(false)
          }}
        >
          Plus tard
        </button>
        <button type="button" className="btn btn--primary" disabled={enCours} onClick={activer}>
          Activer
        </button>
      </div>
    </div>
  )
}
