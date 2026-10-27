import { useEffect, useState } from 'react'
import * as api from './api.js'

// Dans l'écran Tarifs de la saison (`seasonPrices` du module.js,
// spec/core.md §9.3 et §11.1) : avec une campagne HelloAsso, ses formules,
// options et codes promo, en lecture seule, à la place des nôtres. Rien sans
// campagne ou module éteint. `onCampaign(true)` : l'écran cache les nôtres.

const euros = (centimes) =>
  (centimes / 100).toLocaleString('fr-FR', {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  })

function prixFormule(f) {
  if (f.price === null) return f.min_amount ? `Dès ${euros(f.min_amount)}` : 'Prix libre'
  return f.price === 0 ? 'Gratuit' : euros(f.price)
}

function Ligne({ nom, detail, prix }) {
  return (
    <div className="tarifs__ligne">
      <span className="tarifs__nom">
        {nom}
        {detail && <small>{detail}</small>}
      </span>
      {prix && <span className="tarifs__prix">{prix}</span>}
    </div>
  )
}

export default function HelloAssoTarifs({ ecoleId, onCampaign }) {
  const [tarifs, setTarifs] = useState(null)

  useEffect(() => {
    api
      .tarifs(ecoleId)
      .then((lu) => {
        setTarifs(lu)
        onCampaign(lu.campaign)
      })
      .catch(() => onCampaign(false))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ecoleId])

  if (!tarifs?.campaign) return null
  return (
    <>
      <p className="creer-saison__note">
        Tarifs de la campagne HelloAsso « {tarifs.form_name} » : ils se modifient sur HelloAsso.
      </p>
      {tarifs.error && <p className="login-screen__erreur">{tarifs.error}</p>}
      <div className="creer-saison__partie">Formules</div>
      {tarifs.plans.length === 0 && <p className="creer-saison__note">Aucune.</p>}
      {tarifs.plans.map((f, i) => (
        <Ligne
          key={i}
          nom={f.name}
          detail={[f.frequency, f.description].filter(Boolean).join(' · ')}
          prix={prixFormule(f)}
        />
      ))}
      <div className="creer-saison__partie">Options et codes promo</div>
      {tarifs.options.length === 0 && tarifs.codes.length === 0 && <p className="creer-saison__note">Aucune.</p>}
      {tarifs.options.map((o, i) => (
        <Ligne key={i} nom={o.name} detail={o.required ? 'Obligatoire' : 'À cocher'} prix={`+${euros(o.price)}`} />
      ))}
      {tarifs.codes.map((c) => (
        <Ligne key={c.code} nom={`Code ${c.code}`} detail={`Utilisé ${c.uses} fois`} />
      ))}
    </>
  )
}
