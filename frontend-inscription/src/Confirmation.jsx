import { urlDossierPdf, urlFacturePdf } from './api/backend.js'
import { LIBELLE_PALIER } from './tarifs.js'

export default function Confirmation({ resultat, onNouvelleInscription }) {
  const montantTroisTrimestres = resultat.montant_trimestriel * 3
  const totalAnnee = resultat.montant_adhesion + montantTroisTrimestres

  return (
    <div className="section">
      <h2>Inscription enregistrée ✅</h2>
      <p>
        Merci ! L'inscription de <strong>{resultat.eleve_prenom} {resultat.eleve_nom}</strong> pour
        la saison <strong>{resultat.saison}</strong> a bien été prise en compte.
      </p>
      <p>Cours choisis : {resultat.cours_choisis.join(', ')}</p>

      {resultat.photoChoisie && !resultat.photoEnvoyee && (
        <p className="erreur-globale">
          La photo n'a pas pu être envoyée — l'inscription est bien enregistrée sans elle, vous
          pourrez la donner à l'école autrement.
        </p>
      )}

      {resultat.doublon_possible && (
        <p className="erreur-globale">
          Une inscription très similaire existe déjà pour cette saison — l'école vérifiera avec
          vous s'il ne s'agit pas d'un doublon.
        </p>
      )}

      <div className="tarif-apercu" style={{ marginBottom: 16 }}>
        <div className="tarif-apercu__ligne">
          <span>Adhésion</span>
          <span>{resultat.montant_adhesion} €</span>
        </div>
        <div className="tarif-apercu__ligne">
          <span>
            3 trimestres à {resultat.nb_cours_semaine} cours/semaine (palier «{' '}
            {LIBELLE_PALIER[resultat.palier_tarifaire] ?? resultat.palier_tarifaire} »{' '}
            {resultat.montant_trimestriel} €
            {resultat.reduction_famille_appliquee && ' — famille : -5 €'})
          </span>
          <span>{montantTroisTrimestres} €</span>
        </div>
        <div className="tarif-apercu__ligne tarif-apercu__ligne--total">
          <span>Total année</span>
          <span className="montant">{totalAnnee} €</span>
        </div>
        {resultat.alerte_palier_mixte && (
          <div className="alerte">
            Cours choisis touchant plusieurs paliers tarifaires — l'école vous confirmera le
            montant exact.
          </div>
        )}
        <div className="alerte" style={{ color: '#666' }}>
          Adhésion payée à part, par chèque.
        </div>
      </div>

      <p>
        Moyen de paiement choisi : <strong>{resultat.moyen_paiement === 'cheque' ? 'Chèque' : resultat.moyen_paiement}</strong>.
        {resultat.moyen_paiement === 'cheque' &&
          " Les chèques (adhésion, septembre, et échéances suivantes) sont à remettre à l'école."}
      </p>

      <a className="lien-pdf" href={urlDossierPdf(resultat.token_public)} target="_blank" rel="noreferrer">
        📄 Télécharger le dossier rempli (PDF)
      </a>
      <a className="lien-pdf" href={urlFacturePdf(resultat.token_public)} target="_blank" rel="noreferrer">
        🧾 Télécharger la facture (PDF)
      </a>

      <p>
        {resultat.email_envoye
          ? 'Un email récapitulatif (avec ces 2 PDF en pièces jointes) vous a été envoyé.'
          : "Conservez cette page ou téléchargez les PDF ci-dessus : l'email de confirmation n'a pas pu être envoyé."}
      </p>

      <button className="bouton bouton--secondaire" type="button" onClick={onNouvelleInscription}>
        Inscrire un autre élève
      </button>
    </div>
  )
}
