// Fiche d'une opération bancaire (spec/modules/financier.md §8.4), EXEMPLE :
// compte du plan comptable (proposé, à confirmer), pièce, et au niveau
// Complet les écritures générées. Rien n'est enregistré.
import { useState } from 'react'
import Icon from '../../../components/Icon.jsx'
import Modal from '../../../components/Modal.jsx'
import BandeExemple from './BandeExemple.jsx'
import { NATURES, PLAN, dateFr, eur, lireNiveau, pieceDeLaLigne, proposerCompte } from './donnees.js'

export default function FicheOperation({ row, onClose }) {
  const propose = proposerCompte(row.label, row.amount)
  const [compte, setCompte] = useState(propose?.num ?? '')
  const piece = pieceDeLaLigne(row.label)
  const niveau = lireNiveau()
  const choisi = PLAN.find((c) => c.num === compte)
  const montant = Math.abs(row.amount)
  const banque = row.amount < 0 ? '5123 CIC compte 401' : '5124 CIC compte 403'

  return (
    <Modal
      title={row.label}
      onClose={onClose}
      footer={
        <button type="button" className="btn btn--primary" onClick={onClose}>
          Enregistrer
        </button>
      }
    >
      <div className="fin-ex">
        <BandeExemple />
        <p className="muted">
          {dateFr(row.date)} · {row.amount > 0 ? '+' : ''}
          {eur(row.amount)}
          {row.details ? ` · ${row.details.split('\n')[0]}` : ''}
        </p>
        <label className="fin-ex-champ">
          <span>Compte</span>
          <select className="field-input" value={compte} onChange={(e) => setCompte(e.target.value)}>
            <option value="">Compte à choisir</option>
            {['depense', 'recette'].map((nature) => (
              <optgroup key={nature} label={NATURES[nature]}>
                {PLAN.filter((c) => c.nature === nature).map((c) => (
                  <option key={c.num} value={c.num}>
                    {c.num} · {c.label}
                  </option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        {propose && compte === propose.num && (
          <p className="muted">
            Proposé d’après 2024-25 : « {propose.mots.find((m) => row.label.toUpperCase().includes(m)) ?? propose.label} » allait
            en {propose.num} dans {propose.nb} cas. <span className="badge badge--warning">À confirmer</span>
          </p>
        )}
        {!propose && !compte && <p className="muted">Aucune proposition : première fois que ce libellé apparaît.</p>}

        <div className="fin-ex-champ">
          <span>Pièce</span>
          {piece ? (
            <div className="fin-ex-carte">
              <div className="fin-ex-piece">
                <div className="fin-ex-photo">{piece.photo}</div>
                <div>
                  <b>{piece.titre}</b>
                  <span className="muted">{piece.detail}</span> <span className="badge badge--success">Lue</span>
                </div>
              </div>
              <div className="fin-ex-boutons">
                <button type="button" className="btn btn--secondary">
                  Changer la pièce
                </button>
                <button type="button" className="btn btn--secondary">
                  Détacher
                </button>
              </div>
            </div>
          ) : (
            <div className="fin-ex-boutons">
              <button type="button" className="btn btn--secondary">
                <Icon name="camera" size={18} /> Photographier la pièce
              </button>
              <button type="button" className="btn btn--secondary">
                <Icon name="docs" size={18} /> Choisir dans Docs
              </button>
            </div>
          )}
        </div>

        {niveau === 'complet' && choisi && (
          <div className="fin-ex-champ">
            <span>Écritures (niveau Complet)</span>
            <table className="fin-ex-table">
              <tbody>
                {row.amount < 0 ? (
                  <>
                    <tr>
                      <td>{piece ? `${piece.detail.split(' du ')[1]?.slice(0, 10) ?? dateFr(row.date)} · Achat` : `${dateFr(row.date)} · Achat`}</td>
                      <td>
                        {choisi.num} {choisi.label}
                      </td>
                      <td className="r">{eur(montant)}</td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>401 Fournisseurs</td>
                      <td className="r">{eur(montant)}</td>
                    </tr>
                    <tr>
                      <td>{dateFr(row.date)} · Banque</td>
                      <td>401 Fournisseurs</td>
                      <td className="r">{eur(montant)}</td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>{banque}</td>
                      <td className="r">{eur(montant)}</td>
                    </tr>
                  </>
                ) : (
                  <>
                    <tr>
                      <td>{dateFr(row.date)} · Vente</td>
                      <td>411 Adhérents</td>
                      <td className="r">{eur(montant)}</td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>
                        {choisi.num} {choisi.label}
                      </td>
                      <td className="r">{eur(montant)}</td>
                    </tr>
                    <tr>
                      <td>{dateFr(row.date)} · Banque</td>
                      <td>{banque}</td>
                      <td className="r">{eur(montant)}</td>
                    </tr>
                    <tr>
                      <td></td>
                      <td>411 Adhérents</td>
                      <td className="r">{eur(montant)}</td>
                    </tr>
                  </>
                )}
                <tr className="tot">
                  <td>Lettrage</td>
                  <td colSpan={2}>{piece ? 'CAE · pièce et paiement soldés' : 'en attente de la pièce'}</td>
                </tr>
              </tbody>
            </table>
            <p className="muted">
              Écrites par l’appli à partir de la pièce et de la ligne de banque. Au niveau Simple, seule la ligne de banque
              existe : {choisi.num} contre {banque.slice(0, 4)}.
            </p>
          </div>
        )}
      </div>
    </Modal>
  )
}
