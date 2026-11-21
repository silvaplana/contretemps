import { useEffect, useState } from 'react'
import * as miseAJour from '../utils/miseAJour.js'

// Bandeau du haut pendant une mise en ligne (voir utils/miseAJour.js) : au
// lieu d'écrans vides, l'appli dit ce qui se passe, puis se recharge seule.
export default function BandeauMiseAJour() {
  const [visible, setVisible] = useState(miseAJour.estInjoignable)
  useEffect(() => miseAJour.surChangement(setVisible), [])
  if (!visible) return null
  return (
    <div className="bandeau-mise-a-jour" role="status">
      Mise à jour en cours, ça revient dans une minute
    </div>
  )
}
