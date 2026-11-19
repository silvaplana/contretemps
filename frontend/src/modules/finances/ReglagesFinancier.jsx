import QuiPaie from '../notes-frais/QuiPaie.jsx'
import Salaries from '../notes-frais/Salaries.jsx'
import NiveauComptable from './compta/NiveauComptable.jsx'

// Réglages de la ligne Financier de Fonctionnalités : le niveau des
// documents comptables (§8.1), « Qui paie » (§8.3 bis) et « L'association a
// des salariés » (§8.11, non par défaut).
export default function ReglagesFinancier(props) {
  return (
    <>
      <NiveauComptable {...props} />
      <QuiPaie {...props} />
      <Salaries />
    </>
  )
}
