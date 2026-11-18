import { ouvrirConnexions } from '../../app/connexions.js'
import MenuEntete from '../../components/MenuEntete.jsx'
import * as api from './api.js'
import Boite from './Boite.jsx'
import { FOURNISSEURS } from './fournisseurs.js'
import './mail.css'

// Messages › Mail (spec/modules/mail.md §4 à §6) : la boîte du club
// (Boite.jsx). Elle se connecte dans Admin › École › Connexions
// (MailReglages.jsx ; Seb, 18 novembre ; spec/core.md, « Connexions »).

export default function MailScreen({ ecoleId, etat, onEtat }) {
  let corps = null
  if (!etat.connected) {
    corps = (
      <div className="mail__pile">
        <p>La boîte mail du club n'est pas encore connectée.</p>
        {etat.can_connect ? (
          <button type="button" className="btn btn--primary btn--block" onClick={ouvrirConnexions}>
            Connecter la boîte mail
          </button>
        ) : (
          <p className="mail__discret">Seul l’Administrateur principal peut la connecter.</p>
        )}
      </div>
    )
  } else if (etat.cut) {
    corps = (
      <div className="mail__pile">
        <div className="mail__alerte" role="alert">
          <strong>La boîte mail n'est plus connectée</strong>
          {FOURNISSEURS[etat.provider]?.nom ?? 'Le fournisseur'} a coupé l'accès, souvent après un changement du mot
          de passe du compte.{' '}
          {etat.can_connect ? '' : 'L’Administrateur principal doit la reconnecter.'}
        </div>
        {etat.can_connect && (
          <button type="button" className="btn btn--primary btn--block" onClick={ouvrirConnexions}>
            Reconnecter la boîte mail
          </button>
        )}
      </div>
    )
  }

  const menuBoite = etat.connected && (
    <MenuEntete label="Plus d'actions" actions={[{ label: etat.address, icon: 'mail', onClick: () => {} }]} />
  )
  // Accès coupé pendant la lecture : relire l'état (bandeau).
  const coupee = () => api.etat(ecoleId).then(onEtat, () => null)

  return (
    <div className="mail">
      {corps ?? <Boite ecoleId={ecoleId} etat={etat} menuBoite={menuBoite} onCoupee={coupee} />}
      {corps && menuBoite}
    </div>
  )
}
