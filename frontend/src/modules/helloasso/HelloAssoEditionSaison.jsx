import { useEffect, useState } from 'react'
import * as api from './api.js'
import HelloAssoSaison from './HelloAssoSaison.jsx'
import { useToast } from './Contact.jsx'

// Dans « Éditer la saison » (`seasonEditor` du module.js, Seb 18 novembre
// 2026 : une campagne par saison) : comment la saison utilise HelloAsso,
// campagne comprise. Rien si HelloAsso est éteint ou pas connecté, ou pour
// qui ne peut pas le changer (administrateur principal).
export default function HelloAssoEditionSaison({ ecoleId }) {
  const [lu, setLu] = useState(null)
  const [toast, montrer] = useToast()
  useEffect(() => {
    api
      .saison(ecoleId)
      .then(setLu)
      .catch(() => setLu(null))
  }, [ecoleId])
  if (!lu?.connected || !lu.can_change) return null
  return (
    <div className="helloasso__edition-saison">
      <HelloAssoSaison ecoleId={ecoleId} onToast={montrer} />
      {toast}
    </div>
  )
}
