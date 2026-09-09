import { DOMAINES_MIGRES, estAffichageMigrationActif } from '../api/etatMigration.js'

// Entoure un écran/une section pas encore branchée à api/<domaine>.js
// (voir api/README.md) d'un liseré bleu — visible seulement si l'admin a
// activé l'affichage (Admin > École, mode dev). Un seul endroit qui
// décide, jamais de `if` dispersé dans les écrans eux-mêmes : chaque
// écran s'enveloppe juste dans <ZoneMigration domaine="...">.
export default function ZoneMigration({ domaine, children }) {
  const pasEncoreBranche = estAffichageMigrationActif() && !DOMAINES_MIGRES[domaine]
  return <div className={pasEncoreBranche ? 'zone-non-branchee' : undefined}>{children}</div>
}
